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
    "re-emission is the supported way to recover from a blocker.\n\n"
    "Self-check before you stop typing: scan the bottom of your reply. If the "
    "very last line is NOT the literal HARBOR-DONE line above, write it now. "
    "Forgetting it leaves harbor polling an idle pane until --bead-timeout fires "
    "(6 hours by default). A trailing summary paragraph is the most common cause "
    "of this — append the HARBOR-DONE line as the final line if anything follows it."
)


def _section(title: str, body: str) -> str:
    return f"## {title}\n\n{body.strip()}\n"


def _commit_prefix_for(bead_id: str) -> str:
    """Best-effort epic prefix for commit subjects.

    Harbor child bead ids use `<epic-id>.<child>`; finish-time PR
    reconstruction selects commits by the epic prefix.
    """
    return bead_id.split(".", 1)[0] if "." in bead_id else bead_id


def render_worker_prompt(bead: dict[str, Any]) -> str:
    """Build the prompt the agent sees when it spawns inside a tmux pane."""
    bead_id = bead.get("id", "<unknown>")
    commit_prefix = _commit_prefix_for(str(bead_id))
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
                "- Before emitting `status=ok`, commit the successful code changes with a Git commit "
                f"whose subject starts exactly `{commit_prefix}:`. Stage only files you changed within "
                "the declared `Files:` scope. If the bead is verification-only or produced no file "
                "changes, state that no commit was needed.\n"
                "- Do NOT commit when emitting `status=blocked`.\n"
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
                "4. Inspect `git status --short`, stage only your intended changes under `Files:`, "
                f"and commit them with `git commit -m \"{commit_prefix}: <short summary>\"` before "
                "reporting success. Skip this only when no files changed or the bead is "
                "verification-only.\n"
                "5. Print a short summary of what changed, the commit made or why no commit was needed, "
                "and the verify results.\n"
                "6. Print the `HARBOR-DONE` sentinel line as the very last line."
            ),
        )
    )

    parts.append(
        _section(
            "Final check (do not skip)",
            (
                f"Re-read the very last line of your reply before you stop. If it is not "
                f"`HARBOR-DONE: {bead_id} status=... classification=...`, type that line "
                f"now. Anything written after a sentinel hides it from harbor's parser."
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
