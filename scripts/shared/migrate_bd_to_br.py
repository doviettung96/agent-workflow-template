#!/usr/bin/env python3
"""Migrate a repo from local bd/Dolt state to local br JSONL state."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


class MigrationError(Exception):
    def __init__(self, message: str, *, code: int = 1) -> None:
        super().__init__(message)
        self.code = code


def run(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            list(args),
            cwd=str(repo_root),
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as exc:
        raise MigrationError(f"required command not found: {args[0]}", code=2) from exc
    except subprocess.CalledProcessError as exc:
        raise MigrationError(
            f"{args[0]} {' '.join(args[1:])} failed:\n{exc.stdout}{exc.stderr}",
            code=3,
        ) from exc


def parse_prefix(config_path: Path, fallback: str) -> str:
    if config_path.exists():
        text = config_path.read_text(encoding="utf-8", errors="ignore")
        match = re.search(r"^\s*issue_prefix:\s*\"?([^\"#\r\n]+)", text, flags=re.MULTILINE)
        if match:
            return match.group(1).strip()
    return fallback


def process_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}"],
            check=False,
            capture_output=True,
            text=True,
        )
        return str(pid) in result.stdout
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def stop_bd_server(repo_beads: Path) -> None:
    pid_path = repo_beads / "dolt-server.pid"
    port_path = repo_beads / "dolt-server.port"
    pid: int | None = None
    port: str | None = None

    if not pid_path.exists():
        pid = None
    else:
        try:
            pid = int(pid_path.read_text(encoding="utf-8").strip())
        except (TypeError, ValueError):
            pid = None

    if port_path.exists():
        port = port_path.read_text(encoding="utf-8", errors="ignore").strip() or None

    if pid and os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            check=False,
            capture_output=True,
            text=True,
        )
    elif pid:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass

    if os.name == "nt" and port:
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                (
                    "Get-CimInstance Win32_Process | "
                    "Where-Object { $_.Name -like 'dolt*' -and $_.CommandLine -like '* -P "
                    + port
                    + "*' } | "
                    "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
                ),
            ],
            check=False,
            capture_output=True,
            text=True,
        )

    deadline = time.time() + 5.0
    while pid and process_exists(pid) and time.time() < deadline:
        time.sleep(0.2)


def load_json(text: str, context: str) -> object:
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise MigrationError(f"failed to parse JSON from {context}: {exc}", code=6) from exc


def get_full_issue(repo_root: Path, issue_id: str) -> dict[str, object]:
    payload = load_json(run(repo_root, "bd", "show", issue_id, "--json").stdout, f"bd show {issue_id}")
    if isinstance(payload, list) and payload:
        issue = payload[0]
    elif isinstance(payload, dict):
        issue = payload
    else:
        raise MigrationError(f"unexpected bd show payload for {issue_id}", code=7)
    if not isinstance(issue, dict):
        raise MigrationError(f"unexpected bd show issue type for {issue_id}", code=7)
    return issue


def convert_issue(issue: dict[str, object], full_issue: dict[str, object]) -> dict[str, object]:
    result: dict[str, object] = {
        "id": issue["id"],
        "title": issue["title"],
        "status": issue["status"],
        "priority": issue["priority"],
        "issue_type": issue["issue_type"],
        "created_at": issue["created_at"],
        "created_by": issue["created_by"],
        "updated_at": issue["updated_at"],
    }

    for key in (
        "description",
        "notes",
        "assignee",
        "owner",
        "closed_at",
        "close_reason",
        "labels",
    ):
        value = issue.get(key)
        if value not in (None, "", [], {}):
            result[key] = value

    dependencies = issue.get("dependencies") or []
    if dependencies:
        edges: list[dict[str, object]] = []
        for edge in dependencies:
            if not isinstance(edge, dict):
                continue
            edges.append(
                {
                    "issue_id": edge.get("issue_id", issue["id"]),
                    "depends_on_id": edge.get("depends_on_id"),
                    "type": edge.get("type", "blocks"),
                    "created_at": edge.get("created_at", issue["created_at"]),
                    "created_by": edge.get("created_by", issue["created_by"]),
                    "metadata": edge.get("metadata", "{}"),
                    "thread_id": edge.get("thread_id", ""),
                }
            )
        if edges:
            result["dependencies"] = edges

    comments = full_issue.get("comments") or []
    if comments:
        converted_comments: list[dict[str, object]] = []
        for index, comment in enumerate(comments, start=1):
            if not isinstance(comment, dict):
                continue
            converted_comments.append(
                {
                    "id": index,
                    "issue_id": issue["id"],
                    "author": comment.get("author") or issue.get("owner") or issue["created_by"],
                    "text": comment.get("text", ""),
                    "created_at": comment.get("created_at", issue["updated_at"]),
                }
            )
        if converted_comments:
            result["comments"] = converted_comments

    return result


def remove_obsolete_bd_artifacts(repo_beads: Path) -> list[str]:
    leftovers: list[str] = []
    obsolete_paths = [
        repo_beads / "dolt",
        repo_beads / "dolt-server.lock",
        repo_beads / "dolt-server.log",
        repo_beads / "dolt-server.pid",
        repo_beads / "dolt-server.port",
        repo_beads / ".beads-credential-key",
        repo_beads / ".local_version",
        repo_beads / "interactions.jsonl",
    ]
    for path in obsolete_paths:
        if not path.exists():
            continue
        try:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
        except OSError:
            leftovers.append(str(path))
    return leftovers


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Migrate a repo from bd to br")
    parser.add_argument("--repo", required=True, help="Repo path")
    parser.add_argument("--prefix", help="Optional issue prefix override")
    args = parser.parse_args(argv)

    repo_root = Path(args.repo).resolve()
    if not repo_root.exists():
        raise MigrationError(f"repo does not exist: {repo_root}", code=4)

    repo_beads = repo_root / ".beads"
    if not repo_beads.exists():
        raise MigrationError(f"repo does not contain .beads: {repo_root}", code=5)

    issues_payload = load_json(run(repo_root, "bd", "list", "--all", "--limit", "0", "--json").stdout, "bd list")
    if not isinstance(issues_payload, list):
        raise MigrationError("unexpected bd list payload", code=6)
    issues = [issue for issue in issues_payload if isinstance(issue, dict)]
    if not issues:
        raise MigrationError("bd list returned no issues to migrate", code=8)

    fallback_prefix = str(issues[0].get("id", repo_root.name)).split("-", 1)[0]
    prefix = args.prefix or parse_prefix(repo_beads / "config.yaml", fallback_prefix)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    temp_backup_root = Path(os.environ.get("TEMP") or os.environ.get("TMP") or str(repo_root.parent)) / f"br-migration-{repo_root.name}-{timestamp}"
    temp_backup_root.mkdir(parents=True, exist_ok=True)

    stop_bd_server(repo_beads)
    shutil.copytree(repo_beads, temp_backup_root / "repo-beads")

    workflow_src = repo_beads / "workflow"
    workflow_backup = temp_backup_root / "workflow"
    if workflow_src.exists():
        shutil.copytree(workflow_src, workflow_backup)

    converted: list[dict[str, object]] = []
    for issue in issues:
        full_issue = get_full_issue(repo_root, str(issue["id"]))
        converted.append(convert_issue(issue, full_issue))

    run(repo_root, "br", "init", "--prefix", prefix, "--no-db")
    for db_artifact in repo_beads.glob("beads.db*"):
        db_artifact.unlink(missing_ok=True)
    run(repo_root, "br", "config", "set", "issue_prefix", prefix, "--no-db")
    (repo_beads / "metadata.json").write_text(
        json.dumps({"database": "beads.db", "jsonl_export": "issues.jsonl"}, indent=2) + "\n",
        encoding="utf-8",
    )
    leftover_paths = remove_obsolete_bd_artifacts(repo_beads)

    issues_path = repo_beads / "issues.jsonl"
    with issues_path.open("w", encoding="utf-8", newline="\n") as handle:
        for issue in converted:
            handle.write(json.dumps(issue, ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")

    if workflow_backup.exists():
        shutil.copytree(workflow_backup, repo_beads / "workflow", dirs_exist_ok=True)

    backup_dir = repo_beads / "backup" / f"pre-br-migration-{timestamp}"
    backup_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(temp_backup_root / "repo-beads", backup_dir)

    payload = {
        "ok": True,
        "repo_root": str(repo_root),
        "prefix": prefix,
        "issue_count": len(converted),
        "backup_dir": str(backup_dir),
        "leftover_paths": leftover_paths,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except MigrationError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2, sort_keys=True), file=sys.stderr)
        raise SystemExit(exc.code)
