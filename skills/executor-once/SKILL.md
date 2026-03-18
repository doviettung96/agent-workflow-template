---
name: executor-once
description: "Run exactly one full executor cycle for one bead: claim, write a local execution plan, implement, verify, and close. Use when the user wants to execute a single bead end-to-end."
---

# Executor Once

Run exactly one full executor cycle for one bead.

## Worktree Awareness

When running inside a git worktree, `bd` must be run from the main working tree (where the Dolt database lives). Detect and handle this automatically:

```bash
main_tree=$(git worktree list --porcelain | head -1 | sed 's/worktree //')
# Run bd commands with: cd "$main_tree" && bd ...
```

If you are NOT in a worktree (main tree is the current directory), run `bd` normally.

## Steps

1. If the current repo is not initialized for Beads, stop and tell the user to run `bd init -p <prefix>` and `bd setup codex`.
2. Determine the target bead:
   - if the user supplied a bead id in the current request, use that bead
   - if the user supplied freeform selector text, treat it as a selector or hint
   - otherwise inspect `bd ready --json` and choose the best ready bead autonomously
3. Preferred bead choice order:
   - first, a ready bead clearly related to the current repo context or recent planner discussion
   - otherwise, the highest-priority ready bead
4. If bead choice is ambiguous, ask before claiming.
5. Claim the bead and run the executor workflow in this order:
   - `beads-claim`
   - `writing-plans`
   - implementation
   - `systematic-debugging` if blocked
   - repo-local `build-and-test` when runtime verification is needed
   - `verification-before-completion` or `requesting-code-review`
   - `beads-close`
6. If separate work is discovered, create follow-up beads during execution or before close.
7. If a blocker appears, update the current bead, summarize the blocker, and stop.
8. If build/test fails and the fix is still in scope, return to implementation and retry.
9. After success, stop with a concise summary. Do not automatically claim a second bead.

## Hard Rules

- One bead only.
- Do not silently skip verification.
- Do not continue into another bead after close.
