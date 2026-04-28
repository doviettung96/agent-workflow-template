---
name: executor-loop-epic
description: "Run repeated worker-backed executor cycles scoped to a single epic: pick the next ready descendant bead under that epic, assign a fresh worker, close it, then continue until the epic has no ready descendants or a blocker requires user input. Use when the user wants sequential epic progress without swarm coordination."
---

# Executor Loop Epic

Run repeated worker-backed executor cycles bead-by-bead, but only within one epic.

Compatibility path only. For full coordinator-plus-worker execution with reservations, runtime state, and handoff files, prefer `swarm-epic`. This skill is sequential: one claimed bead, one fresh worker, one closeout, then the next ready descendant.

## Steps

1. If the current repo is not initialized for Beads, stop and tell the user to run the template bootstrap script or at minimum `br init --prefix <prefix> --no-db` plus the repo scaffolding steps.
2. Determine the target epic:
   - if the user supplied an epic id in the current request, use that epic
   - otherwise ask for the epic id or enough selector text to identify one unambiguously
3. Verify the epic exists and inspect it:
   ```bash
   br show <epic-id> --json --no-db
   ```
4. Confirm the execution branch and dirty-worktree context:
   ```bash
   git branch --show-current
   git status --short
   ```
   - run from the current feature branch; it does not need to be named `epic/<epic-id>`
   - if the checkout is on any non-`main` branch, do not check out another branch
   - if the checkout is on `main`, create and switch to a generic temporary branch before code work starts:
     - Windows: `git switch -c ("feat/work-" + (Get-Date -Format "yyyyMMdd-HHmmss"))`
     - POSIX: `git switch -c "feat/work-$(date +%Y%m%d-%H%M%S)"`
   - do not use `epic/<epic-id>` as the execution branch; that name is reserved for the reconstructed PR branch created by `finishing-a-development-branch <epic-id>`
   - local tracked, staged, or untracked changes do not block by themselves
   - if files the epic will touch are already dirty, stage and commit only the intended hunks or paths for this epic; `git add -p` is normal and allowed
   - every implementation commit for this epic must start with the exact subject prefix `<epic-id>:`
5. Find ready work only within that epic's descendant tree:
   ```bash
   br ready --parent <epic-id> --json --no-db
   ```
6. Choose the next ready descendant bead using this preference order:
   - first, the ready descendant bead most clearly related to the current repo context or recent discussion
   - otherwise, the highest-priority ready descendant bead
7. Run one full worker-backed executor cycle for that bead:
   - `beads-claim`
   - inspect `br show <bead-id> --json --no-db` and any persisted contract fields
   - dispatch `execute-bead-worker` as a fresh subagent with the real epic id, bead id, full bead details, relevant `Read:`, `Inputs:`, `Files:`, `Verify:`, and explicit instruction that the worker must not mutate Beads state
   - if worker spawning fails, update the bead with a blocker note, summarize the spawn failure, and stop without local implementation fallback
   - wait for the worker report and review changed files, verification evidence, inputs consumed, reservation release, and blocker classification
   - if complete, run `build-and-test` after implementation; read `.codex/skills/build-and-test/SKILL.md` and follow it
   - run `verification-before-completion` or `requesting-code-review`
   - use `beads-close` only after implementation and verification are complete
8. After a successful close and local commit, inspect the epic again for more ready descendants:
   ```bash
   br ready --parent <epic-id> --json --no-db
   ```
9. Repeat until one of these stop conditions is reached:
   - no ready descendant beads remain under the epic
   - descendant work exists under the epic, but none of it is ready
   - a blocker requires user input
   - build, test, or verification cannot pass
   - manual intervention is required
10. When separate follow-up work is discovered during execution:
    - create the follow-up bead
    - parent it to the same epic by default unless the discovery clearly belongs elsewhere
    - preserve any dependency links needed to explain the relationship
11. When the epic has no ready descendants left:
    - run `build-and-test` one final time to verify the full epic
    - invoke `review-epic` if the user wants an epic-level quality gate before the PR
    - use `finishing-a-development-branch <epic-id>` to reconstruct an epic PR branch from prefixed commits and create a PR targeting `main`
12. When stopping early:
    - summarize the current bead, the blocker, and what input or fix is needed

## Hard Rules

- Stay within the target epic. Do not wander to unrelated ready beads outside it.
- Treat each descendant bead as its own logical executor cycle.
- Do not hold multiple claimed beads at once.
- Implementation belongs to the fresh `execute-bead-worker` subagent; the parent session owns sequencing, verification, Beads state, and closeout.
- If subagent spawning is unavailable, stop. Do not fall back to local implementation in the coordinator session.
- Never continue past a blocker without user input.
- If the supplied epic id is not actually an epic, stop and ask the user whether to scope to that parent bead anyway or choose a different epic.
- Never merge locally; the PR is the merge mechanism.
- Do not require a clean worktree just to execute the epic. Keep commits scoped by staging explicit paths or hunks.
- This is a sequential compatibility path, not the primary swarm workflow.
- If the session accumulates too much coordinator context, stop after the current bead and restart the next bead in a fresh session.
