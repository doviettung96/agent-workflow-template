---
name: executor-loop
description: "Run repeated manual executor cycles bead-by-bead until the ready queue is exhausted or a blocker requires user input. Use when the user wants sequential autonomous progress without swarm coordination."
---

# Executor Loop

Run repeated manual executor cycles bead-by-bead until the queue is exhausted or a blocker requires user input.

Compatibility path only. For epic-scoped work, prefer `swarm-epic` or repeated fresh `executor-once` sessions instead of one long-running loop that accumulates context.

## Steps

1. If the current repo is not initialized for Beads, stop and tell the user to run the template bootstrap script or at minimum `br init --prefix <prefix> --no-db` plus the repo scaffolding steps.
2. Determine the first bead:
   - if the user supplied a bead id in the current request, start there
   - if the user supplied freeform selector text, treat it as a selector or hint for the first bead
   - otherwise inspect `br ready --json --no-db` and choose the best ready bead autonomously
3. Run one full executor cycle for that bead by invoking every step in order:
   - `beads-claim`
   - `writing-plans`
   - implementation
   - `systematic-debugging` if blocked
   - `build-and-test` after implementation; read `.codex/skills/build-and-test/SKILL.md` and follow it
   - `verification-before-completion` or `requesting-code-review`
   - `beads-close`
4. After a successful close and local commit, inspect `br ready --json --no-db` again and choose the next best ready bead using the same preference order.
5. Repeat until one of these stop conditions is reached:
   - no ready bead remains
   - a blocker requires user input
   - build, test, or verification cannot pass
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
- This is a sequential path. Do not market it as true multi-agent swarming.
- If the loop grows long enough that session context becomes unreliable, stop and resume the next bead in a fresh `executor-once` session instead of pushing through.

