---
name: executor-once
description: "Run exactly one full executor cycle for one bead: claim, write a local execution plan, implement, verify, and close. Use when the user wants to execute a single bead end-to-end."
---

# Executor Once

Run exactly one full executor cycle for one bead.

## Steps

1. If the current repo is not initialized for Beads, stop and tell the user to run the template bootstrap script or at minimum `bd init --prefix <prefix>` plus the repo scaffolding steps.
2. Determine the target bead:
   - if the user supplied a bead id in the current request, use that bead
   - if the user supplied freeform selector text, treat it as a selector or hint
   - otherwise inspect `bd ready --json` and choose the best ready bead autonomously
3. Preferred bead choice order:
   - first, a ready bead clearly related to the current repo context or recent planner discussion
   - otherwise, the highest-priority ready bead
4. If bead choice is ambiguous, ask before claiming.
5. Claim the bead and run the executor workflow — **every step in order**:
   - `beads-claim`
   - `writing-plans`
   - implementation
   - `systematic-debugging` if blocked
   - **`build-and-test`** — REQUIRED after implementation. Read the skill at `.codex/skills/build-and-test/SKILL.md` and follow it. Do NOT skip this step.
   - `verification-before-completion` or `requesting-code-review`
   - `beads-close`
6. If separate work is discovered, create follow-up beads during execution or before close.
7. If a blocker appears, update the current bead, summarize the blocker, and stop.
8. If build/test fails and the fix is still in scope, return to implementation and retry.
9. After success, stop with a concise summary. Do not automatically claim a second bead.

## Checkout Discipline

- If `bd where` fails in the current checkout, stop and repair the repo with `bd bootstrap --yes` before continuing.
- If you are executing on a feature branch, keep the work scoped to that branch and bead.

## Hard Rules

- One bead only.
- Do not silently skip verification.
- Do not continue into another bead after close.
