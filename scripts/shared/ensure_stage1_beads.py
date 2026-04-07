#!/usr/bin/env python3
"""Ensure stage-1 bootstrap follow-up beads exist exactly once."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


TITLE = "Specialize build-and-test for this repo"
DESCRIPTION = """Stage-1 bootstrap installed the generic build-and-test skill.

Create the repo-specific stage-2 specialization as a standalone bead:

## Goal
- replace the generic stage-1 validation flow with project-specific build, run, and smoke-test steps
- keep the Codex and Claude build-and-test skills aligned

## Requirements
- update `.codex/skills/build-and-test/SKILL.md`
- mirror the same behavior in `.claude/skills/build-and-test/SKILL.md`
- document any stable setup, launch, or verification steps the skill depends on

## Notes
- keep this bead independent; do not nest it under the first feature epic
- later epics may depend on this if stronger verification is needed
"""


def run(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Ensure stage-1 bootstrap follow-up beads exist")
    parser.add_argument("repo", nargs="?", default=".", help="Repo root")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    list_result = run(repo, "bd", "list", "--json")
    if list_result.returncode != 0:
        sys.stderr.write(list_result.stderr)
        return list_result.returncode

    try:
        issues = json.loads(list_result.stdout or "[]")
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"Failed to parse `bd list --json`: {exc}\n")
        return 1

    for issue in issues:
        if isinstance(issue, dict) and issue.get("title") == TITLE:
            print(f"Stage-1 follow-up bead already exists: {issue.get('id', TITLE)}")
            return 0

    create_result = run(
        repo,
        "bd",
        "create",
        "--type",
        "chore",
        "--priority",
        "2",
        "--labels",
        "bootstrap,stage-2",
        "--title",
        TITLE,
        "--description",
        DESCRIPTION,
    )
    if create_result.returncode != 0:
        sys.stderr.write(create_result.stderr)
        return create_result.returncode

    sys.stdout.write(create_result.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
