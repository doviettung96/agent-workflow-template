#!/usr/bin/env python3
"""Sync downstream workflow files into the backup mirror repo."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import workflow_backup


def add_repo_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo", default=".", help="Downstream repo path (default: current directory)")
    parser.add_argument("--backup-repo", help="Backup repo path (default: sibling ../agentic-workflows or AGENTIC_WORKFLOWS_REPO)")
    parser.add_argument("--project-name", help="Backup subtree name (default: downstream repo folder name)")


def command_ensure_ignore(args: argparse.Namespace) -> int:
    repo_root = workflow_backup.resolve_repo_root(args.repo)
    changed = workflow_backup.ensure_ignore_block(repo_root)
    if args.json:
        print(json.dumps({"repo_root": str(repo_root), "changed": changed}))
    else:
        state = "updated" if changed else "already current"
        print(f"Managed workflow ignore block {state} in {repo_root / '.gitignore'}")
    return 0


def command_sync(args: argparse.Namespace) -> int:
    repo_root = workflow_backup.resolve_repo_root(args.repo)
    backup_repo = workflow_backup.resolve_backup_repo(repo_root, args.backup_repo)
    project_name = args.project_name or repo_root.name
    result = workflow_backup.sync_workflow_backup(
        repo_root,
        backup_repo,
        project_name,
        dry_run=args.dry_run,
        push=not args.no_push and not args.dry_run,
    )
    payload = {
        "repo_root": str(result.repo_root),
        "backup_repo": str(result.backup_repo),
        "project_name": result.project_name,
        "backup_branch": result.backup_branch,
        "copied": result.copied,
        "removed": result.removed,
        "committed": result.committed,
        "pushed": result.pushed,
        "commit_message": result.commit_message,
        "dry_run": args.dry_run,
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"Repo:        {result.repo_root}")
        print(f"Backup repo: {result.backup_repo}")
        print(f"Project:     {result.project_name}")
        print(f"Branch:      {result.backup_branch}")
        print(f"Copied:      {len(result.copied)}")
        print(f"Removed:     {len(result.removed)}")
        print(f"Committed:   {'yes' if result.committed else 'no'}")
        print(f"Pushed:      {'yes' if result.pushed else 'no'}")
        if result.commit_message:
            print(f"Commit:      {result.commit_message}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage downstream workflow backup mirrors")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ensure_ignore = subparsers.add_parser(
        "ensure-ignore",
        help="Install or refresh the managed workflow ignore block in the downstream repo .gitignore",
    )
    ensure_ignore.add_argument("--repo", default=".", help="Downstream repo path (default: current directory)")
    ensure_ignore.add_argument("--json", action="store_true")
    ensure_ignore.set_defaults(func=command_ensure_ignore)

    sync = subparsers.add_parser(
        "sync",
        help="Mirror managed workflow files into the backup repo subtree",
    )
    add_repo_arguments(sync)
    sync.add_argument("--dry-run", action="store_true")
    sync.add_argument("--no-push", action="store_true")
    sync.add_argument("--json", action="store_true")
    sync.set_defaults(func=command_sync)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
