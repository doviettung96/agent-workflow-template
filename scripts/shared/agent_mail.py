#!/usr/bin/env python3
"""File-backed Agent Mail transport for Beads swarm workflows."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path, PurePosixPath
from typing import Any


VERSION = 2
LOCK_TIMEOUT_SECONDS = 10.0
LOCK_POLL_SECONDS = 0.1


class AgentMailError(Exception):
    def __init__(self, message: str, *, code: int = 1, details: Any | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def json_load(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def json_dump(path: Path, payload: Any) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def run_git(repo_root: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise AgentMailError("git is required for Agent Mail", code=2) from exc
    except subprocess.CalledProcessError as exc:
        raise AgentMailError(
            f"git {' '.join(args)} failed",
            code=3,
            details={"stderr": exc.stderr.strip(), "stdout": exc.stdout.strip()},
        ) from exc
    return completed.stdout.strip()


def resolve_repo_root(repo_hint: Path) -> Path:
    return Path(run_git(repo_hint, "rev-parse", "--show-toplevel")).resolve()


def resolve_git_common_dir(repo_root: Path) -> Path:
    raw = run_git(repo_root, "rev-parse", "--git-common-dir")
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = (repo_root / candidate).resolve()
    return candidate


class FileLock:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.fd: int | None = None

    def __enter__(self) -> "FileLock":
        deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
        ensure_dir(self.path.parent)
        while True:
            try:
                self.fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(self.fd, f"{os.getpid()}\n".encode("utf-8"))
                return self
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise AgentMailError(f"Timed out waiting for lock: {self.path}", code=4)
                time.sleep(LOCK_POLL_SECONDS)

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass


class AgentMailStore:
    def __init__(self, repo_hint: Path) -> None:
        self.repo_root = resolve_repo_root(repo_hint.resolve())
        self.git_common_dir = resolve_git_common_dir(self.repo_root)
        self.root = self.git_common_dir / "agent-swarm"
        self.threads_dir = self.root / "threads"
        self.locks_dir = self.root / "locks"
        self.state_lock = self.root / ".state.lock"
        self.agents_path = self.root / "agents.json"
        self.reservations_path = self.root / "reservations.json"

    def ensure_layout(self) -> None:
        ensure_dir(self.root)
        ensure_dir(self.threads_dir)
        ensure_dir(self.locks_dir)
        if not self.agents_path.exists():
            json_dump(self.agents_path, [])
        if not self.reservations_path.exists():
            json_dump(self.reservations_path, [])

    def with_state_lock(self) -> FileLock:
        self.ensure_layout()
        return FileLock(self.state_lock)

    def load_agents(self) -> list[dict[str, Any]]:
        return list(json_load(self.agents_path, []))

    def save_agents(self, agents: list[dict[str, Any]]) -> None:
        json_dump(self.agents_path, agents)

    def load_reservations(self) -> list[dict[str, Any]]:
        return list(json_load(self.reservations_path, []))

    def save_reservations(self, reservations: list[dict[str, Any]]) -> None:
        json_dump(self.reservations_path, reservations)

    def lock_path_for_epic(self, epic_id: str) -> Path:
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", epic_id)
        return self.locks_dir / f"epic-{safe}.json"

    def thread_path(self, thread: str) -> Path:
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", thread)
        return self.threads_dir / f"{safe}.jsonl"

    def read_epic_locks(self) -> list[dict[str, Any]]:
        self.ensure_layout()
        items: list[dict[str, Any]] = []
        for path in sorted(self.locks_dir.glob("epic-*.json")):
            try:
                items.append(json_load(path, {}))
            except json.JSONDecodeError:
                items.append({"path": path.name, "status": "invalid"})
        return items


def normalize_scope_path(raw_path: str) -> str:
    value = raw_path.replace("\\", "/").strip()
    value = re.sub(r"/+", "/", value)
    value = value.strip("/")
    if value in ("", "."):
        raise AgentMailError("Reservation path cannot be empty", code=5)
    return str(PurePosixPath(value))


def scopes_overlap(left: str, right: str) -> bool:
    if left == right:
        return True
    return left.startswith(right + "/") or right.startswith(left + "/")


def command_init(store: AgentMailStore, _args: argparse.Namespace) -> dict[str, Any]:
    store.ensure_layout()
    return {
        "ok": True,
        "repo_root": str(store.repo_root),
        "git_common_dir": str(store.git_common_dir),
        "root": str(store.root),
        "version": VERSION,
        "created_at": utc_now(),
    }


def command_register(store: AgentMailStore, args: argparse.Namespace) -> dict[str, Any]:
    with store.with_state_lock():
        agents = store.load_agents()
        now = utc_now()
        record = {
            "name": args.name,
            "session_id": args.session_id or args.name,
            "role": args.role,
            "epic_id": args.epic_id,
            "bead_id": args.bead_id,
            "status": args.status or "active",
            "repo_root": str(store.repo_root),
            "last_seen": now,
        }
        replaced = False
        for index, item in enumerate(agents):
            if item.get("name") == args.name:
                agents[index] = record
                replaced = True
                break
        if not replaced:
            agents.append(record)
        store.save_agents(agents)
    return {"ok": True, "agent": record}


def command_unregister(store: AgentMailStore, args: argparse.Namespace) -> dict[str, Any]:
    with store.with_state_lock():
        agents = [item for item in store.load_agents() if item.get("name") != args.name]
        store.save_agents(agents)
    return {"ok": True, "name": args.name}


def command_acquire_epic(store: AgentMailStore, args: argparse.Namespace) -> dict[str, Any]:
    store.ensure_layout()
    path = store.lock_path_for_epic(args.epic_id)
    now = utc_now()
    payload = {
        "version": VERSION,
        "epic_id": args.epic_id,
        "owner": args.owner,
        "session_id": args.session_id or args.owner,
        "repo_root": str(store.repo_root),
        "created_at": now,
        "updated_at": now,
    }
    with store.with_state_lock():
        existing = json_load(path, None)
        if existing and existing.get("owner") != args.owner:
            raise AgentMailError(
                f"Epic {args.epic_id} is already locked by {existing.get('owner')}",
                code=10,
                details=existing,
            )
        if existing:
            payload["created_at"] = existing.get("created_at", now)
        json_dump(path, payload)
    return {"ok": True, "lock": payload}


def command_release_epic(store: AgentMailStore, args: argparse.Namespace) -> dict[str, Any]:
    path = store.lock_path_for_epic(args.epic_id)
    with store.with_state_lock():
        existing = json_load(path, None)
        if existing and existing.get("owner") not in (None, args.owner):
            raise AgentMailError(
                f"Epic {args.epic_id} is locked by {existing.get('owner')}, not {args.owner}",
                code=11,
                details=existing,
            )
        if path.exists():
            path.unlink()
    return {"ok": True, "epic_id": args.epic_id, "owner": args.owner}


def command_reserve(store: AgentMailStore, args: argparse.Namespace) -> dict[str, Any]:
    requested = [normalize_scope_path(path) for path in args.path]
    with store.with_state_lock():
        reservations = store.load_reservations()
        conflicts: list[dict[str, Any]] = []
        for existing in reservations:
            existing_owner = existing.get("owner")
            existing_path = existing.get("path")
            if not existing_path or existing_owner == args.owner:
                continue
            if any(scopes_overlap(existing_path, path) for path in requested):
                conflicts.append(existing)
        if conflicts:
            raise AgentMailError(
                "Reservation conflict detected",
                code=12,
                details={"conflicts": conflicts},
            )

        created: list[dict[str, Any]] = []
        now = utc_now()
        for path in requested:
            match = next(
                (
                    item
                    for item in reservations
                    if item.get("owner") == args.owner
                    and item.get("epic_id") == args.epic_id
                    and item.get("bead_id") == args.bead_id
                    and item.get("path") == path
                ),
                None,
            )
            if match:
                match["updated_at"] = now
                created.append(match)
                continue
            entry = {
                "id": str(uuid.uuid4()),
                "owner": args.owner,
                "epic_id": args.epic_id,
                "bead_id": args.bead_id,
                "repo_root": str(store.repo_root),
                "path": path,
                "created_at": now,
                "updated_at": now,
            }
            reservations.append(entry)
            created.append(entry)
        store.save_reservations(reservations)
    return {"ok": True, "reservations": created}


def command_release_reservations(store: AgentMailStore, args: argparse.Namespace) -> dict[str, Any]:
    with store.with_state_lock():
        reservations = store.load_reservations()
        kept: list[dict[str, Any]] = []
        released: list[dict[str, Any]] = []
        for item in reservations:
            owner_match = item.get("owner") == args.owner
            bead_match = args.bead_id is None or item.get("bead_id") == args.bead_id
            if owner_match and bead_match:
                released.append(item)
            else:
                kept.append(item)
        store.save_reservations(kept)
    return {"ok": True, "released": released}


def command_post(store: AgentMailStore, args: argparse.Namespace) -> dict[str, Any]:
    store.ensure_layout()
    message_type = args.message_type
    if not message_type:
        try:
            parsed_body = json.loads(args.body)
        except json.JSONDecodeError:
            parsed_body = None
        if isinstance(parsed_body, dict):
            message_type = parsed_body.get("type") or parsed_body.get("message_type")
    if not message_type:
        message_type = "note"
    message = {
        "id": str(uuid.uuid4()),
        "timestamp": utc_now(),
        "thread": args.thread,
        "sender": args.sender,
        "to": args.to,
        "type": message_type,
        "epic_id": args.epic_id,
        "bead_id": args.bead_id,
        "repo_root": str(store.repo_root),
        "body": args.body,
    }
    path = store.thread_path(args.thread)
    with store.with_state_lock():
        ensure_dir(path.parent)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(message, sort_keys=True))
            handle.write("\n")
    return {"ok": True, "message": message}


def read_thread(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    items: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            items.append(json.loads(text))
    return items


def command_list(store: AgentMailStore, args: argparse.Namespace) -> dict[str, Any]:
    items = read_thread(store.thread_path(args.thread))
    if args.recipient:
        items = [item for item in items if item.get("to") in (args.recipient, "*", None)]
    return {"ok": True, "thread": args.thread, "messages": items}


def command_inbox(store: AgentMailStore, args: argparse.Namespace) -> dict[str, Any]:
    store.ensure_layout()
    messages: list[dict[str, Any]] = []
    for path in sorted(store.threads_dir.glob("*.jsonl")):
        for item in read_thread(path):
            if item.get("to") in (args.recipient, "*", None):
                messages.append(item)
    messages.sort(key=lambda item: (item.get("timestamp") or "", item.get("id") or ""))
    return {"ok": True, "recipient": args.recipient, "messages": messages}


def command_status(store: AgentMailStore, _args: argparse.Namespace) -> dict[str, Any]:
    store.ensure_layout()
    thread_count = len(list(store.threads_dir.glob("*.jsonl")))
    return {
        "ok": True,
        "version": VERSION,
        "repo_root": str(store.repo_root),
        "git_common_dir": str(store.git_common_dir),
        "root": str(store.root),
        "agents": store.load_agents(),
        "epic_locks": store.read_epic_locks(),
        "reservations": store.load_reservations(),
        "thread_count": thread_count,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Shared Agent Mail transport")
    parser.add_argument("--repo", default=".", help="Repo root or checkout path")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init")
    init_parser.set_defaults(func=command_init)

    register = subparsers.add_parser("register")
    register.add_argument("--name", required=True)
    register.add_argument("--role", required=True)
    register.add_argument("--session-id")
    register.add_argument("--epic-id")
    register.add_argument("--bead-id")
    register.add_argument("--status")
    register.set_defaults(func=command_register)

    unregister = subparsers.add_parser("unregister")
    unregister.add_argument("--name", required=True)
    unregister.set_defaults(func=command_unregister)

    acquire = subparsers.add_parser("acquire-epic")
    acquire.add_argument("--epic-id", required=True)
    acquire.add_argument("--owner", required=True)
    acquire.add_argument("--session-id")
    acquire.set_defaults(func=command_acquire_epic)

    release = subparsers.add_parser("release-epic")
    release.add_argument("--epic-id", required=True)
    release.add_argument("--owner", required=True)
    release.set_defaults(func=command_release_epic)

    reserve = subparsers.add_parser("reserve")
    reserve.add_argument("--owner", required=True)
    reserve.add_argument("--epic-id", required=True)
    reserve.add_argument("--bead-id", required=True)
    reserve.add_argument("--path", "--file", dest="path", required=True, action="append")
    reserve.set_defaults(func=command_reserve)

    release_res = subparsers.add_parser("release-reservations")
    release_res.add_argument("--owner", required=True)
    release_res.add_argument("--bead-id")
    release_res.set_defaults(func=command_release_reservations)

    post = subparsers.add_parser("post", aliases=["send"])
    post.add_argument("--thread", required=True)
    post.add_argument("--sender", "--from", dest="sender", required=True)
    post.add_argument("--to", default="*")
    post.add_argument("--type", dest="message_type")
    post.add_argument("--body", required=True)
    post.add_argument("--epic-id")
    post.add_argument("--bead-id")
    post.set_defaults(func=command_post)

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--thread", required=True)
    list_parser.add_argument("--recipient")
    list_parser.set_defaults(func=command_list)

    inbox = subparsers.add_parser("inbox")
    inbox.add_argument("--recipient", required=True)
    inbox.set_defaults(func=command_inbox)

    status = subparsers.add_parser("status")
    status.set_defaults(func=command_status)

    return parser


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        store = AgentMailStore(Path(args.repo))
        result = args.func(store, args)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except AgentMailError as exc:
        payload = {"ok": False, "error": str(exc)}
        if exc.details is not None:
            payload["details"] = exc.details
        print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
        return exc.code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
