---
name: beads-task-cycle
description: Execute one Beads task from claim through completion and sync. Use when the user wants Codex to work on a chosen bead, pick the next ready bead, or follow the Beads lifecycle before and after implementation without inventing a separate tracking flow.
---

# Beads Task Cycle

Run one bead cleanly from start to finish while keeping Beads as the source of truth for task state.

## Use This Workflow

1. Before coding:
   - if no bead was specified, inspect ready work and select the next appropriate bead
   - claim the bead with `bd update <id> --claim --json`
   - inspect it with `bd show <id> --json`
   - make a short execution plan for that one bead
2. During work:
   - implement and test
   - if blocked, update the bead instead of silently stopping
   - if new work is discovered, create linked follow-up beads
3. After work:
   - close the bead when complete
   - create follow-up beads before ending the session if they are needed
   - sync Beads with `bd dolt push`
   - sync code with `git push`

## Ownership Rules

- Keep Beads mutations in the main session.
- Use subagents for implementation, testing, review, or exploration, but do not let them own the bead lifecycle unless the user explicitly asks.
- Do not create markdown TODOs or alternate task lists.
- Do not close the bead until implementation, verification, and any required follow-up beads are handled.

## Completion Rules

- Prefer `bd close <id> --reason "Completed"` for completed work.
- If execution is blocked, leave the bead open and record the blocking reason.
- If new tasks are discovered, link them with Beads dependencies before ending the session.
- Treat `bd dolt push` and `git push` as part of finishing the bead, not optional cleanup.
