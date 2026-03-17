---
name: executor-loop-epic
description: "Run repeated executor cycles scoped to a single epic: pick the next ready descendant bead under that epic, execute it, then continue until the epic has no ready descendants or a blocker requires user input. Use when the user wants focused autonomous progress within one epic instead of the global ready queue."
---

# Executor Loop Epic

Run repeated executor cycles bead-by-bead, but only within one epic.

## Steps

1. If the current repo is not initialized for Beads, stop and tell the user to run `bd init -p <prefix>` and `bd setup codex`.
2. Determine the target epic:
   - if the user supplied an epic id in the current request, use that epic
   - otherwise ask for the epic id or enough selector text to identify one unambiguously
3. Verify the epic exists and inspect it:
   ```bash
   bd show <epic-id> --json
   ```
4. Find ready work only within that epic's descendant tree:
   ```bash
   bd ready --parent <epic-id> --json
   ```
5. Choose the next ready descendant bead using this preference order:
   - first, the ready descendant bead most clearly related to the current repo context or recent discussion
   - otherwise, the highest-priority ready descendant bead
6. Run one full executor cycle for that bead by invoking:
   - `beads-claim`
   - `writing-plans`
   - implementation
   - `systematic-debugging` if blocked
   - repo-local `build-and-test` when needed
   - `verification-before-completion` or `requesting-code-review`
   - `beads-close`
7. After a successful close and local commit, inspect the epic again for more ready descendants:
   ```bash
   bd ready --parent <epic-id> --json
   ```
8. Repeat until one of these stop conditions is reached:
   - no ready descendant beads remain under the epic
   - descendant work exists under the epic, but none of it is ready
   - a blocker requires user input
   - build/test or verification cannot pass
   - manual intervention is required
9. When separate follow-up work is discovered during execution:
   - create the follow-up bead
   - parent it to the same epic by default unless the discovery clearly belongs elsewhere
   - preserve any dependency links needed to explain the relationship
10. When stopping:
   - if there are no ready descendants left, summarize what was completed and whether the epic still has blocked or deferred work
   - if blocked, summarize the current bead, the blocker, and what input or fix is needed

## Hard Rules

- Stay within the target epic. Do not wander to unrelated ready beads outside it.
- Treat each descendant bead as its own logical executor cycle.
- Do not hold multiple claimed beads at once.
- Never continue past a blocker without user input.
- If the supplied epic id is not actually an epic, stop and ask the user whether to scope to that parent bead anyway or choose a different epic.
