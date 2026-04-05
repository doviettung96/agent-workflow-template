"""Manage template-owned AGENTS/CLAUDE instruction blocks."""

from __future__ import annotations

import argparse
from pathlib import Path


LEGACY_BLOCKS = [
    ("<!-- BEGIN BEADS INTEGRATION -->", "<!-- END BEADS INTEGRATION -->"),
    ("<!-- br-agent-instructions-v", "<!-- end-br-agent-instructions -->"),
    ("<!-- bv-agent-instructions-v", "<!-- end-bv-agent-instructions -->"),
    ("<!-- BEGIN TEMPLATE BR WORKFLOW -->", "<!-- END TEMPLATE BR WORKFLOW -->"),
]

LEGACY_SNIPPETS = [
    "## Issue Tracking\n\nUses `"
    + chr(98)
    + chr(100)
    + "` (beads/Dolt). See `AGENTS.md` for repo rules and `BEADS_WORKFLOW.md` for the planner/executor workflow. Never use markdown TODOs or alternate task trackers.\n",
    "## Workflow Guide\n\nUse `BEADS_WORKFLOW.md` for the current planner, manual executor, and swarm executor flow.\nAll workflow skills are repo-local: Codex skills live under `.codex/skills/`, Claude skills under `.claude/skills/`.\nPreferred entry points are `plan-beads`, `validate-beads`, `start-epic-worktree`, `swarm-epic`, and `executor-once`.\nUse `executor-loop` or `executor-loop-epic` for sequential autonomy when swarm coordination is not needed.\nThe executor test skill lives at `.codex/skills/build-and-test/SKILL.md`; use it between implementation and final verification.\nUse `scripts/windows/start-epic-worktree.ps1` or `scripts/posix/start-epic-worktree.sh` to prepare epic worktrees.\nUse `scripts/windows/workflow-status.ps1` or `scripts/posix/workflow-status.sh` to inspect `.beads/workflow/` plus the shared control plane.\nUse `scripts/windows/agent-mail.ps1` or `scripts/posix/agent-mail.sh` for shared epic locks, reservations, and mailbox inspection.\n\nImportant:\n\n- keep this section outside the Beads-managed `AGENTS.md` block\n- do not edit inside `<!-- BEGIN BEADS INTEGRATION --> ... <!-- END BEADS INTEGRATION -->`\n",
    "## Workflow Guide\n\nUse `BEADS_WORKFLOW.md` for the current planner, manual executor, and swarm executor flow.\nAll workflow skills are repo-local: Codex skills live under `.codex/skills/`, Claude skills under `.claude/skills/`.\nPreferred entry points are `plan-beads`, `validate-beads`, `start-epic-worktree`, `swarm-epic`, and `executor-once`.\nUse `planner-research` only inside a planner session when `brainstorming` still leaves material factual uncertainty.\nUse `executor-loop` or `executor-loop-epic` for sequential autonomy when swarm coordination is not needed.\nThe executor test skill lives at `.codex/skills/build-and-test/SKILL.md`; use it between implementation and final verification.\nUse `scripts/windows/start-epic-worktree.ps1` or `scripts/posix/start-epic-worktree.sh` to prepare epic worktrees.\nUse `scripts/windows/workflow-status.ps1` or `scripts/posix/workflow-status.sh` to inspect `.beads/workflow/` plus the shared control plane.\nUse `scripts/windows/agent-mail.ps1` or `scripts/posix/agent-mail.sh` for shared epic locks, reservations, and mailbox inspection.\n\nImportant:\n\n- keep this section outside the Beads-managed `AGENTS.md` block\n- do not edit inside `<!-- BEGIN BEADS INTEGRATION --> ... <!-- END BEADS INTEGRATION -->`\n",
]


def strip_block(content: str, start_marker: str, end_marker: str) -> str:
    while True:
        start = content.find(start_marker)
        if start == -1:
            return content
        end = content.find(end_marker, start)
        if end == -1:
            return content
        end += len(end_marker)
        before = content[:start].rstrip("\r\n")
        after = content[end:].lstrip("\r\n")
        if before and after:
            content = before + "\n\n" + after
        else:
            content = before or after


def normalize_legacy(content: str) -> str:
    for start, end in LEGACY_BLOCKS:
        content = strip_block(content, start, end)
    for snippet in LEGACY_SNIPPETS:
        content = content.replace(snippet, "")
    return content.strip()


def parse_markers(snippet: str) -> tuple[str, str]:
    lines = [line for line in snippet.splitlines() if line.strip()]
    start = next((line for line in lines if line.startswith("<!-- BEGIN ")), None)
    end = next((line for line in lines if line.startswith("<!-- END ")), None)
    if not start or not end:
        raise ValueError("snippet must contain <!-- BEGIN ... --> and <!-- END ... --> markers")
    return start, end


def upsert(target: Path, snippet_path: Path) -> None:
    snippet = snippet_path.read_text(encoding="utf-8").strip()
    start_marker, end_marker = parse_markers(snippet)
    if target.exists():
        content = normalize_legacy(target.read_text(encoding="utf-8"))
        content = strip_block(content, start_marker, end_marker).strip()
        merged = snippet if not content else f"{content}\n\n{snippet}"
    else:
        merged = snippet
    target.write_text(merged.rstrip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("target")
    parser.add_argument("snippet")
    args = parser.parse_args()
    upsert(Path(args.target), Path(args.snippet))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
