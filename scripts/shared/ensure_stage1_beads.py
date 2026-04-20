#!/usr/bin/env python3
"""Ensure stage-1 bootstrap follow-up beads exist exactly once."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


GAME_RE_BEAD = {
    "title": "Populate action catalog for this repo",
    "description": """Stage-1 bootstrap (profile=game-re) installed the game-action-harness skill and scripts/shared/harness.py.

Create the repo-specific stage-2 catalog as a standalone bead.

## Scope — WRITE side only

This bead captures *the human's* knowledge: which in-game button to click, which hotkey to press, which screen coordinate to target. That is the only information the agent cannot derive from the codebase. Everything on the READ side (memory layout, packet format, hook-log output, symbol addresses) is already solved by the project's own instrumentation and lives wherever that project keeps it.

Therefore:

- **DO** catalog actions as pseudo-human input: click/tap, key/keyevent, swipe, locate-then-click, wait.
- **DO NOT** route actions through an RPC/HTTP/TCP bridge to a launcher or wrapper process that already knows how to perform the action. That tests the bridge, not the hooked game code. The purpose of firing input through the game UI is to force the real user code path through the hook so the hook actually executes.
- **DO** leave observers unset unless the project already emits a natural event for the action. Observers are project-owned; they belong in whatever existing log/memory/packet sink the project has. The harness tails; it does not produce.

## Goal

- wire up the harness for this repo so the agent can trigger in-game actions itself during RE verification
- catalog the actions the agent will want to exercise when testing hooked functions (autopath, autoattack, skill use, UI button clicks, NPC talk, etc.)
- keep the catalog fresh-session safe so any worker can execute actions from the bead contract alone

## Requirements

- create `.harness/actions.yaml` (see skills/game-action-harness/templates/actions.yaml.example)
- populate target.platform, target.device (android) or target.window (pc); target.observe_log only if the project already writes a unified hook log
- define at least 3 actions. Each action's `invoke` must be one of: a single step or a chain of steps drawn from {adb_tap / adb_swipe / adb_keyevent / adb_text, sendinput_click / sendinput_key / postmessage_click, locate, wait}. Prefer fixed coords / hotkeys where possible; use `locate` + `template_match` for icons that move or only appear conditionally
- put any reference images under `.harness/assets/` and reference them by relative path in the locate step
- run `python scripts/shared/harness.py probe` — all bridges must report ok before catalog entries are considered working
- for each catalogued action, run `python scripts/shared/harness.py trigger <name> --json` and confirm status=ok. Invoke-only (no observer) counts as success
- do NOT add a custom backend that skips the game UI (HTTP RPC, TCP command to a launcher, etc.). If you believe you need one, stop and flag this as a design question — it is almost always the wrong answer for an RE verification harness

## Decision Gate

- before implementation, confirm with the user which actions are highest priority to catalog first
- confirm that the project's existing READ-side instrumentation (DLL logs, memory reads, packet captures) is working and will be used for verification. If the read side is not solved yet, this bead is blocked on that first

## How to work this bead — pair with the user

Catalog work is collaborative by nature: the agent owns YAML + wiring + running the harness; the user owns the game-specific knowledge (hotkeys, button coords, icon PNGs). Before asking the user anything, the agent first reads the project's own plan docs, hook scripts, and any superseded `.harness/actions.yaml.*.bak` files. Then for each new action, it proposes the candidate with a reason, asks the user only for what only-the-user knows, drafts the entry with sensible defaults, runs `harness trigger`, and iterates with the user until the in-game effect is confirmed.

The full turn-by-turn pairing protocol lives in the skill doc — follow it:

- `.codex/skills/game-action-harness/SKILL.md` → section "Pairing protocol"
- `.claude/skills/game-action-harness/SKILL.md` → same section

Do NOT guess coords, hotkeys, or icon paths. Ask.

## Notes

- keep this bead independent; do not nest it under the first feature epic
- depend on the runtime-target bead if SSH execution applies
- `.harness/actions.yaml` and `.harness/assets/` are treated the same as `runtime-target.json`: never overwritten by `update-skills`
""",
}


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

## Decision Gate
- before implementation, ask the user which runtime mode this checkout should use: `local` or `ssh`
- if the user selects `ssh`, ask for:
  - SSH host alias
  - remote platform (`posix` or `windows`)
  - remote workdir
  - preferred sync strategy if it matters
  - preferred remote Python path if Python-based commands should use a non-default interpreter on that host
- inspect checked-in docs, scripts, plans, and deployment notes for stable evidence that can help validate or fill in the user's answer, but do not skip the explicit runtime decision prompt
- do not close this bead until one of these is true:
  - the user explicitly confirmed that this checkout should stay on `local`
  - the active checkout was configured with a concrete SSH target
- do not treat "local mode remains the default" as sufficient completion without explicit user confirmation
- do not commit machine-specific SSH values under `.beads/`; configure the active checkout locally and document the exact command needed to re-apply the configuration

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


def _resolve_profile(repo: Path, cli_profile: str | None) -> str:
    if cli_profile:
        return cli_profile
    profile_file = repo / ".beads" / "workflow" / "profile.json"
    if profile_file.is_file():
        try:
            with profile_file.open("r", encoding="utf-8") as fh:
                return json.load(fh).get("profile", "generic") or "generic"
        except Exception:
            pass
    return "generic"


def main() -> int:
    parser = argparse.ArgumentParser(description="Ensure stage-1 bootstrap follow-up beads exist")
    parser.add_argument("repo", nargs="?", default=".", help="Repo root")
    parser.add_argument("--profile", choices=["generic", "game-re"], default=None,
                        help="Downstream profile. Defaults to .beads/workflow/profile.json then 'generic'.")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    profile = _resolve_profile(repo, args.profile)

    # Include closed beads AND override the default --limit=50 so a completed
    # stage-1 bead does not get re-created as a duplicate on every update-skills
    # run. Without --limit=0 any repo with >50 issues silently loses older beads
    # from the existing-title set.
    list_result = run(repo, "bd", "list", "--all", "--limit", "0", "--json")
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

    beads_to_ensure = list(BEADS)
    if profile == "game-re":
        beads_to_ensure.append(GAME_RE_BEAD)

    created_any = False
    for bead in beads_to_ensure:
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
        print(f"All stage-1 follow-up beads already exist (profile={profile}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
