#!/usr/bin/env python3
"""Create or reuse a dedicated worktree for an epic branch."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


class WorktreeError(Exception):
    def __init__(self, message: str, *, code: int = 1, details: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


def run_git(repo_root: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise WorktreeError("git is required for start-epic-worktree", code=2) from exc
    except subprocess.CalledProcessError as exc:
        raise WorktreeError(
            f"git {' '.join(args)} failed",
            code=3,
            details={"stdout": exc.stdout.strip(), "stderr": exc.stderr.strip()},
        ) from exc
    return completed.stdout.strip()


def run_bd(repo_root: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ["bd", *args],
            check=True,
            capture_output=True,
            text=True,
            cwd=str(repo_root),
        )
    except FileNotFoundError as exc:
        raise WorktreeError("bd is required for start-epic-worktree", code=4) from exc
    except subprocess.CalledProcessError as exc:
        raise WorktreeError(
            f"bd {' '.join(args)} failed",
            code=5,
            details={"stdout": exc.stdout.strip(), "stderr": exc.stderr.strip()},
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


def parse_worktrees(repo_root: Path) -> list[dict[str, str]]:
    raw = run_git(repo_root, "worktree", "list", "--porcelain")
    items: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in raw.splitlines():
        if not line:
            if current:
                items.append(current)
                current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value.strip()
    if current:
        items.append(current)
    return items


def seed_workflow_state(worktree_path: Path, epic_id: str, branch_name: str) -> None:
    workflow_root = worktree_path / ".beads" / "workflow"
    workflow_root.mkdir(parents=True, exist_ok=True)

    state_path = workflow_root / "state.json"
    if not state_path.exists():
        payload = {
            "version": 1,
            "mode": "idle",
            "epic_id": epic_id,
            "branch": branch_name,
            "worktree_path": str(worktree_path),
            "coordinator": None,
            "agent_mail": {
                "status": "unknown",
                "last_error": None,
            },
            "workers": [],
            "assignments": [],
            "reservations": [],
            "blockers": [],
            "last_action": "worktree prepared",
            "next_action": f"Run swarm-epic for {epic_id}",
        }
        state_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    handoff_path = workflow_root / "HANDOFF.json"
    if not handoff_path.exists():
        handoff = {
            "version": 1,
            "role": None,
            "epic_id": epic_id,
            "bead_id": None,
            "owner": None,
            "status": "idle",
            "summary": None,
            "next_action": f"Run swarm-epic for {epic_id}",
            "verify_commands": [],
            "updated_at": None,
        }
        handoff_path.write_text(json.dumps(handoff, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary_path = workflow_root / "STATE.md"
    if not summary_path.exists():
        summary = "\n".join(
            [
                "# Workflow State",
                "",
                "This file is maintained by `swarm-epic`.",
                "",
                "## Status",
                "",
                "- Mode: `idle`",
                f"- Epic: `{epic_id}`",
                f"- Branch: `{branch_name}`",
                f"- Worktree: `{worktree_path}`",
                "- Coordinator: `none`",
                "",
                "## Workers",
                "",
                "- None",
                "",
                "## Reservations",
                "",
                "- None",
                "",
                "## Blockers",
                "",
                "- None",
                "",
                "## Next Action",
                "",
                f"- Run `swarm-epic` for `{epic_id}` in this worktree.",
                "",
            ]
        )
        summary_path.write_text(summary, encoding="utf-8")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Create or reuse an epic worktree")
    parser.add_argument("--repo", default=".", help="Repo root or existing worktree")
    parser.add_argument("--epic-id", required=True, help="Epic identifier")
    args = parser.parse_args(argv)

    try:
        current_repo_root = resolve_repo_root(Path(args.repo).resolve())
        git_common_dir = resolve_git_common_dir(current_repo_root)
        main_repo_root = git_common_dir.parent if git_common_dir.name == ".git" else current_repo_root
        branch_name = f"epic/{args.epic_id}"
        branch_ref = f"refs/heads/{branch_name}"

        existing_worktrees = parse_worktrees(main_repo_root)
        for item in existing_worktrees:
            if item.get("branch") == branch_ref:
                existing_path = Path(item["worktree"]).resolve()
                seed_workflow_state(existing_path, args.epic_id, branch_name)
                print(
                    json.dumps(
                        {
                            "ok": True,
                            "repo_root": str(main_repo_root),
                            "git_common_dir": str(git_common_dir),
                            "worktree_path": str(existing_path),
                            "branch": branch_name,
                            "created": False,
                            "next_command": f"cd {existing_path} && swarm-epic {args.epic_id}",
                        },
                        indent=2,
                        sort_keys=True,
                    )
                )
                return 0

        raw = run_bd(main_repo_root, "worktree", "create", args.epic_id, "--branch", branch_name, "--json")
        payload = json.loads(raw)
        worktree_path = Path(payload["path"]).resolve()
        seed_workflow_state(worktree_path, args.epic_id, branch_name)
        print(
            json.dumps(
                {
                    "ok": True,
                    "repo_root": str(main_repo_root),
                    "git_common_dir": str(git_common_dir),
                    "worktree_path": str(worktree_path),
                    "branch": branch_name,
                    "created": True,
                    "next_command": f"cd {worktree_path} && swarm-epic {args.epic_id}",
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    except WorktreeError as exc:
        payload = {"ok": False, "error": str(exc)}
        if exc.details:
            payload["details"] = exc.details
        print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
        return exc.code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
