#!/usr/bin/env python3
"""Migrate one downstream repo to local-only workflow files plus backup mirror sync."""

from __future__ import annotations

import argparse
import json

import workflow_backup


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate a downstream repo to workflow-backup mirroring")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--backup-repo", help="Backup repo path (default: sibling ../agentic-workflows or AGENTIC_WORKFLOWS_REPO)")
    parser.add_argument("--project-name", help="Backup subtree name (default: downstream repo folder name)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    repo_root = workflow_backup.resolve_repo_root(args.repo)
    backup_repo = workflow_backup.resolve_backup_repo(repo_root, args.backup_repo)
    project_name = args.project_name or repo_root.name

    ignore_changed = workflow_backup.ensure_ignore_block(repo_root)
    sync_result = workflow_backup.sync_workflow_backup(
        repo_root,
        backup_repo,
        project_name,
        dry_run=False,
        push=True,
    )
    removed_from_index = workflow_backup.remove_managed_files_from_index(repo_root)

    payload = {
        "repo_root": str(repo_root),
        "backup_repo": str(backup_repo),
        "project_name": project_name,
        "ignore_changed": ignore_changed,
        "backup_branch": sync_result.backup_branch,
        "backup_committed": sync_result.committed,
        "backup_pushed": sync_result.pushed,
        "backup_commit_message": sync_result.commit_message,
        "removed_from_index": removed_from_index,
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"Repo:               {repo_root}")
        print(f"Backup repo:        {backup_repo}")
        print(f"Project:            {project_name}")
        print(f"Ignore block:       {'updated' if ignore_changed else 'already current'}")
        print(f"Backup committed:   {'yes' if sync_result.committed else 'no'}")
        print(f"Backup pushed:      {'yes' if sync_result.pushed else 'no'}")
        print(f"Removed from index: {len(removed_from_index)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
