"""Render a worker prompt from a bead contract.

The harbor-bead-runner injects this prompt to the agent CLI on stdin (or via
--prompt-file fallback). The prompt encodes the same fresh-worker contract the
existing `execute-bead-worker` skill uses, plus a hard rule that the final
output must include a `HARBOR-DONE: <id> status=...` sentinel line so the
runner can detect completion deterministically.
"""
from __future__ import annotations

from typing import Any

SENTINEL_INSTRUCTION = (
    "When you have finished (success OR blocker), the LAST line of your message "
    "MUST follow this exact form (literal, no angle brackets in your output):\n\n"
    "    HARBOR-DONE: BEAD-ID status=STATUS classification=CLASSIFICATION\n\n"
    "Where:\n"
    "  BEAD-ID        is exactly: {bead_id}\n"
    "  STATUS         is one of:  ok | blocked\n"
    "  CLASSIFICATION is one of:  none (when status=ok)\n"
    "                              clarify | env | contract | scope (when status=blocked)\n\n"
    "Use 'clarify' for a missing detail, 'env' for tool/environment failure, "
    "'contract' for a malformed bead description, 'scope' if the work needs splitting.\n\n"
    "Do not print anything after that line in the same message. The harbor daemon "
    "polls the pane for the most recent matching line and uses it to decide whether "
    "to close the bead. Note: harbor parses ONLY the literal HARBOR-DONE line — the "
    "placeholders above (BEAD-ID, STATUS, CLASSIFICATION) are descriptive; you must "
    "substitute real values.\n\n"
    "If you emit a `blocked` line, harbor leaves you running so a human can attach "
    "to the pane and reply directly. After they respond, address their guidance and "
    "emit a fresh HARBOR-DONE line — harbor only acts on the most recent one, so "
    "re-emission is the supported way to recover from a blocker."
)


def _section(title: str, body: str) -> str:
    return f"## {title}\n\n{body.strip()}\n"


def render_worker_prompt(bead: dict[str, Any]) -> str:
    """Build the prompt the agent sees when it spawns inside a tmux pane."""
    bead_id = bead.get("id", "<unknown>")
    title = bead.get("title", "")
    description = (bead.get("description") or "").strip()

    parts: list[str] = []
    parts.append(f"# Bead {bead_id}: {title}\n")
    parts.append(
        "You are a fresh worker spawned by the harbor runner inside a tmux pane. "
        "You have NO prior conversation context — only this prompt and the local "
        "repository. Read the bead contract below and implement it.\n"
    )

    parts.append(_section("Bead description (verbatim)", description or "(no description)"))

    parts.append(
        _section(
            "Hard rules",
            (
                "- Stay within the `Files:` scope declared in the description. Do not edit other files.\n"
                "- Do NOT call `br update` or `br close` — the harbor daemon owns bead-state mutation.\n"
                "- Run the `Verify:` commands listed in the description before you finish.\n"
                "- If the bead description is missing `Files:` or `Verify:`, stop and emit a `blocked` "
                "sentinel with classification=contract.\n"
                "- If something in the environment is broken (missing tool, failing tmux, etc.), emit "
                "a `blocked` sentinel with classification=env.\n"
                "- If the scope is wrong or work needs splitting, classification=scope.\n"
                "- If you just need a small clarification, classification=clarify."
            ),
        )
    )

    parts.append(
        _section(
            "Completion sentinel (required)",
            SENTINEL_INSTRUCTION.format(bead_id=bead_id),
        )
    )

    parts.append(
        _section(
            "Suggested workflow",
            (
                "1. Read the `Read:` files listed in the description, plus any code those files reference.\n"
                "2. Implement the change inside `Files:`.\n"
                "3. Run each `Verify:` command and fix any failures (within scope).\n"
                "4. Print a short summary of what changed and the verify results.\n"
                "5. Print the `HARBOR-DONE` sentinel line as the very last line."
            ),
        )
    )

    return "\n".join(parts).rstrip() + "\n"


def parse_sentinel(text: str, bead_id: str) -> tuple[str, str] | None:
    """Find the last `HARBOR-DONE: <id> status=... classification=...` line.

    The sentinel is matched ANYWHERE on the line, not just at the start, so
    that REPL prefixes (codex prepends `• ` to model messages, claude adds its
    own marker glyph, etc.) don't hide it. Returns (status, classification) if
    found and the bead-id matches, else None.
    """
    needle = f"HARBOR-DONE: {bead_id} "
    matches: list[tuple[str, int]] = []
    for line in text.splitlines():
        idx = line.find(needle)
        if idx != -1:
            matches.append((line, idx))
    if not matches:
        return None
    last_line, last_idx = matches[-1]
    rest = last_line[last_idx + len(needle):].strip()
    fields: dict[str, str] = {}
    for tok in rest.split():
        if "=" in tok:
            k, v = tok.split("=", 1)
            fields[k] = v
    status = fields.get("status", "")
    classification = fields.get("classification", "none")
    if status not in {"ok", "blocked"}:
        return None
    return status, classification
