---
name: executor-once
description: "Run exactly one full executor cycle for one bead: claim, assign a fresh worker, review the result, verify, and close. Use when the user wants to execute a single bead end-to-end."
---

# Executor Once

Run exactly one full executor cycle for one bead.

The main session is a thin coordinator. Implementation happens in a fresh `execute-bead-worker` subagent, even when there is only one bead.

## Steps

1. If the current repo is not initialized for Beads, stop and tell the user to run the template bootstrap script or at minimum `br init --prefix <prefix> --no-db` plus the repo scaffolding steps.
2. Determine the target bead:
   - if the user supplied a bead id in the current request, use that bead
   - if the user supplied freeform selector text, treat it as a selector or hint
   - otherwise inspect `br ready --json --no-db` and choose the best ready bead autonomously
3. Preferred bead choice order:
   - first, a ready bead clearly related to the current repo context or recent planner discussion
   - otherwise, the highest-priority ready bead
4. If bead choice is ambiguous, ask before claiming.
5. Claim the bead, then keep the parent session as coordinator:
   - `beads-claim`
   - inspect `br show <bead-id> --json --no-db` and any persisted contract fields
   - dispatch `execute-bead-worker` as a fresh subagent with coordination scope `manual/<bead-id>`, bead id, full bead details, relevant `Read:`, `Inputs:`, `Files:`, `Verify:`, and explicit instruction that the worker must not mutate Beads state
   - if worker spawning fails, update the bead with a blocker note, summarize the spawn failure, and stop without local implementation fallback
6. Wait for the worker report, then review it before closeout:
   - changed files
   - verification evidence
   - inputs consumed
   - released reservations or explanation that none were needed
   - blocker classification if blocked
7. If the worker reports `clarify` or `env`, resolve the small issue if possible and continue with the same worker. If the worker reports `contract` or `scope`, tighten or split the bead and prefer a fresh worker before retrying.
8. If implementation is complete, run coordinator-side verification:
   - **`build-and-test`** - REQUIRED after implementation. Read the skill at `.codex/skills/build-and-test/SKILL.md` and follow it. Do NOT skip this step.
   - `verification-before-completion` or `requesting-code-review`
9. If verification fails and the fix is still in scope, send the failure evidence back to the worker or spawn a fresh worker when the prior report was not reusable. Do not implement the fix in the coordinator session unless the user explicitly changes the mode.
10. Use `beads-close` only after implementation and verification are complete, then stop with a concise summary. Do not automatically claim a second bead.
11. If separate work is discovered, create follow-up beads during execution or before close.

## Checkout Discipline

- If `br where --no-db` fails in the current checkout, stop and repair the repo with `br init --prefix <prefix> --no-db` before continuing.
- If you are executing on a feature branch, keep the work scoped to that branch and bead.

## Hard Rules

- One bead only.
- Implementation belongs to the fresh `execute-bead-worker` subagent; the parent session owns coordination, verification, Beads state, and closeout.
- If subagent spawning is unavailable, stop. Do not fall back to local implementation in the coordinator session.
- Do not silently skip verification.
- Do not continue into another bead after close.
