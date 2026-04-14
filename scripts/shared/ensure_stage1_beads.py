#!/usr/bin/env python3
"""Ensure stage-1 bootstrap follow-up beads exist exactly once."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


BEADS = [
    {
        "title": "Configure target runtime for this repo",
        "description": """Stage-1 bootstrap installed the shared target-runtime helper with local execution as the default.

Create the optional repo-specific stage-2 runtime setup as a standalone bead:

## Goal
- decide whether this repo should keep using local execution or route project execution through SSH
- make runtime-dependent commands consistent across local Windows and remote POSIX/Windows targets
- keep remote bootstrap behavior separate from the shared workflow scaffold

## Requirements
- decide whether the repo needs `.beads/workflow/runtime-target.json` customized in active checkouts
- add repo-owned wrapper commands or scripts for build, run, and verification when raw shell commands differ by platform
- add repo-specific remote bootstrap steps for Docker, Conda, or other environment setup when needed
- document stable runtime setup outside the managed blocks in `AGENTS.md` or `CLAUDE.md`

## Notes
- keep this bead independent; do not nest it under the first feature epic
- if remote execution is required, make runtime-dependent feature beads depend on this bead
""",
    },
    {
        "title": "Specialize build-and-test for this repo",
        "description": """Stage-1 bootstrap installed the generic build-and-test skill.

Create the repo-specific stage-2 specialization as a standalone bead:

## Goal
- replace the generic stage-1 validation flow with project-specific build, run, and smoke-test steps
- keep the Codex and Claude build-and-test skills aligned
- switch repeated verification flows to stable repo-owned wrapper commands when helpful

## Requirements
- update `.codex/skills/build-and-test/SKILL.md`
- mirror the same behavior in `.claude/skills/build-and-test/SKILL.md`
- document any stable setup, launch, or verification steps the skill depends on
- if the repo uses SSH execution, align the specialization with the configured target runtime and wrapper commands

## Notes
- keep this bead independent; do not nest it under the first feature epic
- later epics may depend on this if stronger verification is needed
""",
    },
]


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

    existing_titles = {
        issue.get("title"): issue.get("id")
        for issue in issues
        if isinstance(issue, dict) and issue.get("title")
    }

    created_any = False
    for bead in BEADS:
        title = bead["title"]
        if title in existing_titles:
            print(f"Stage-1 follow-up bead already exists: {existing_titles[title]}")
            continue

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
            title,
            "--description",
            bead["description"],
        )
        if create_result.returncode != 0:
            sys.stderr.write(create_result.stderr)
            return create_result.returncode

        created_any = True
        sys.stdout.write(create_result.stdout)

    if not created_any:
        print("All stage-1 follow-up beads already exist.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
