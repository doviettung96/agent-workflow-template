#!/usr/bin/env python3
"""Migrate a repo from the current br/shared-beads layout to local bd/Dolt."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
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
        )
    except FileNotFoundError as exc:
        raise MigrationError(f"required command not found: {args[0]}", code=2) from exc
    except subprocess.CalledProcessError as exc:
        raise MigrationError(
            f"{args[0]} {' '.join(args[1:])} failed:\n{exc.stdout}{exc.stderr}",
            code=3,
        ) from exc


def parse_prefix(config_path: Path, fallback: str) -> str:
    if not config_path.exists():
        return fallback
    text = config_path.read_text(encoding="utf-8", errors="ignore")
    patterns = [
        r"^\s*issue_prefix:\s*\"?([^\"#\r\n]+)",
        r"^\s*issue-prefix:\s*\"?([^\"#\r\n]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.MULTILINE)
        if match:
            return match.group(1).strip()
    return fallback


def resolve_live_root(repo_root: Path) -> Path:
    repo_beads = repo_root / ".beads"
    redirect_path = repo_beads / "redirect"
    if not redirect_path.exists():
        return repo_beads

    target_text = redirect_path.read_text(encoding="utf-8", errors="ignore").strip()
    if not target_text:
        return repo_beads

    target = Path(target_text)
    if not target.is_absolute():
        target = (repo_beads / target).resolve()
    return target


def copy_if_exists(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    if src.is_dir():
        shutil.copytree(src, dst)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Migrate a repo from br to bd")
    parser.add_argument("--repo", required=True, help="Repo path")
    parser.add_argument("--prefix", help="Optional issue prefix override")
    args = parser.parse_args(argv)

    repo_root = Path(args.repo).resolve()
    if not repo_root.exists():
        raise MigrationError(f"repo does not exist: {repo_root}", code=4)

    repo_beads = repo_root / ".beads"
    live_root = resolve_live_root(repo_root)
    issues_path = live_root / "issues.jsonl"
    if not issues_path.exists():
        raise MigrationError(f"could not find live issues.jsonl at {issues_path}", code=5)

    prefix = args.prefix or parse_prefix(repo_beads / "config.yaml", repo_root.name.lower())
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    temp_backup_root = Path(os.environ.get("TEMP") or os.environ.get("TMP") or str(repo_root.parent)) / f"bd-rollback-{repo_root.name}-{timestamp}"
    temp_backup_root.mkdir(parents=True, exist_ok=True)

    source_issues_copy = temp_backup_root / "issues.jsonl"
    shutil.copy2(issues_path, source_issues_copy)
    copy_if_exists(repo_beads, temp_backup_root / "repo-beads")
    if live_root != repo_beads:
        copy_if_exists(live_root, temp_backup_root / "live-root")

    if repo_beads.exists():
        shutil.rmtree(repo_beads)
    repo_beads.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_issues_copy, repo_beads / "issues.jsonl")

    run(
        repo_root,
        "bd",
        "init",
        "-p",
        prefix,
        "--server",
        "--from-jsonl",
        "--non-interactive",
        "--role",
        "maintainer",
        "--skip-agents",
        "--skip-hooks",
    )

    backup_dir = repo_beads / "backup" / f"pre-bd-rollback-{timestamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    copy_if_exists(temp_backup_root / "repo-beads", backup_dir / "repo-beads")
    copy_if_exists(temp_backup_root / "live-root", backup_dir / "live-root")
    copy_if_exists(source_issues_copy, backup_dir / "issues.jsonl")

    if live_root != repo_beads and live_root.exists():
        shutil.rmtree(live_root)
        live_parent = live_root.parent
        try:
            if live_parent.exists() and not any(live_parent.iterdir()):
                live_parent.rmdir()
        except OSError:
            pass

    payload = {
        "ok": True,
        "repo_root": str(repo_root),
        "prefix": prefix,
        "live_root": str(live_root),
        "source_issues": str(issues_path),
        "backup_dir": str(backup_dir),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except MigrationError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2, sort_keys=True), file=sys.stderr)
        raise SystemExit(exc.code)
