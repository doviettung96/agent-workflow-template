#!/usr/bin/env python3
"""Create a git worktree and hydrate the local-only workflow surface into it."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import workflow_backup


def run(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=repo,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )


def repo_name(repo_root: Path) -> str:
    return repo_root.name


def default_worktree_path(repo_root: Path, epic_id: str) -> Path:
    return (repo_root.parent / f"{repo_name(repo_root)}-{epic_id}").resolve()


def branch_exists(repo_root: Path, branch: str) -> bool:
    result = run(repo_root, "git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}")
    return result.returncode == 0


def has_head_commit(repo_root: Path) -> bool:
    result = run(repo_root, "git", "rev-parse", "--verify", "HEAD")
    return result.returncode == 0


def ensure_beads_ready(repo_root: Path) -> None:
    result = run(repo_root, "br", "where", "--no-db")
    if result.returncode != 0:
        raise RuntimeError(
            "Source checkout is not br-ready. Run the repo bootstrap/update workflow first."
        )


def create_worktree(repo_root: Path, worktree_path: Path, branch: str, base_ref: str) -> None:
    if worktree_path.exists():
        raise RuntimeError(f"Worktree path already exists: {worktree_path}")
    if not has_head_commit(repo_root):
        raise RuntimeError(
            "Source checkout has no commits yet. Commit the current code snapshot before creating a worktree."
        )
    if branch_exists(repo_root, branch):
        result = run(repo_root, "git", "worktree", "add", str(worktree_path), branch)
    else:
        result = run(
            repo_root,
            "git",
            "worktree",
            "add",
            "-b",
            branch,
            str(worktree_path),
            base_ref,
        )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "git worktree add failed")


def verify_dest(dest_repo: Path) -> None:
    result = run(dest_repo, "br", "where", "--no-db")
    if result.returncode != 0:
        raise RuntimeError(
            "Hydrated worktree did not resolve br state correctly. "
            f"stderr: {result.stderr.strip() or '<empty>'}"
        )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Create a hydrated epic worktree")
    parser.add_argument("--source-repo", default=".", help="Current checkout that already has local workflow files")
    parser.add_argument("--epic-id", required=True, help="Epic id, used for default branch and path naming")
    parser.add_argument("--worktree-path", help="Destination worktree path")
    parser.add_argument("--branch", help="Branch name (default: epic/<epic-id>)")
    parser.add_argument("--base-ref", default="HEAD", help="Base ref for a new branch (default: HEAD)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    source_repo = workflow_backup.resolve_repo_root(args.source_repo)
    ensure_beads_ready(source_repo)

    branch = args.branch or f"epic/{args.epic_id}"
    worktree_path = Path(args.worktree_path).expanduser().resolve() if args.worktree_path else default_worktree_path(source_repo, args.epic_id)

    create_worktree(source_repo, worktree_path, branch, args.base_ref)
    copied = workflow_backup.copy_worktree_local_files(source_repo, worktree_path)
    verify_dest(worktree_path)

    payload = {
        "source_repo": str(source_repo),
        "worktree_path": str(worktree_path),
        "branch": branch,
        "base_ref": args.base_ref,
        "copied_files": copied,
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"Source repo:   {source_repo}")
        print(f"Worktree path: {worktree_path}")
        print(f"Branch:        {branch}")
        print(f"Base ref:      {args.base_ref}")
        print(f"Copied files:  {len(copied)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
