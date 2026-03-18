---
name: executor-loop
description: "Run repeated executor cycles bead-by-bead until the ready queue is exhausted or a blocker requires user input. Use when the user wants autonomous multi-bead execution with safe stopping on blockers."
---

# Executor Loop

Run repeated executor cycles bead-by-bead until the queue is exhausted or a blocker requires user input.

## Worktree Awareness

When running inside a git worktree, `bd` must be run from the main working tree (where the Dolt database lives). Detect and handle this automatically:

```bash
main_tree=$(git worktree list --porcelain | head -1 | sed 's/worktree //')
# Run bd commands with: cd "$main_tree" && bd ...
```

If you are NOT in a worktree (main tree is the current directory), run `bd` normally.

## Steps

1. If the current repo is not initialized for Beads, stop and tell the user to run `bd init -p <prefix>` and `bd setup codex`.
2. Determine the first bead:
   - if the user supplied a bead id in the current request, start there
   - if the user supplied freeform selector text, treat it as a selector or hint for the first bead
   - otherwise inspect `bd ready --json` and choose the best ready bead autonomously
3. Run one full executor cycle for that bead by invoking:
   - `beads-claim`
   - `writing-plans`
   - implementation
   - `systematic-debugging` if blocked
   - repo-local `build-and-test` when needed
   - `verification-before-completion` or `requesting-code-review`
   - `beads-close`
4. After a successful close and local commit, inspect `bd ready --json` again and choose the next best ready bead using the same preference order.
5. Repeat until one of these stop conditions is reached:
   - no ready bead remains
   - a blocker requires user input
   - build/test or verification cannot pass
   - manual intervention is required
6. When stopping on a blocker:
   - do not auto-resume
   - summarize the current bead, the blocker, and what input or fix is needed
   - wait for the user to continue in normal chat
7. When stopping because no ready work remains, summarize the completed beads and any follow-up beads created during the loop.

## Hard Rules

- Treat each bead as its own logical executor cycle.
- Do not hold multiple claimed beads at once.
- Never continue past a blocker without user input.
