---
name: swarm-epic
description: "Coordinate multi-agent execution for one epic. Use after planning when the user wants parallel work across ready descendant beads with coordinator-owned Beads state, feature-branch execution, automatic epic review, runtime files, and Agent Mail reservations."
---

# Swarm Epic

Coordinate epic-scoped execution across one or more workers.

## Goal

Drive an epic to completion while keeping the current checkout's local `br`/`.beads` store as the single source of truth.

The coordinator should remain thin. Workers are fresh per bead and should rely on the bead contract plus local code inspection, not the full epic session history.

## Steps

1. If the current repo is not initialized for Beads, stop and tell the user to run the template bootstrap script or at minimum `br init --prefix <prefix> --no-db` plus the repo scaffolding steps.
2. Determine the target epic:
   - if the user supplied an epic id, use it
   - otherwise ask for the epic id or enough selector text to identify one unambiguously
3. Inspect the epic:
   ```bash
   br show <epic-id> --json --no-db
   ```
4. Ensure the epic has passed `validate-beads`. In the normal flow this should already be true because `plan-beads` ends with validation. If the epic has not been validated, stop and run that gate first.
5. Confirm the execution branch and dirty-worktree context:
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
6. Confirm the current checkout resolves the Beads workspace correctly:
   ```bash
   br where --no-db
   br info --json --no-db
   ```
7. Initialize or refresh local `.beads/workflow/` in this checkout:
   - `state.json` tracks mode, coordinator identity, workers, assignments, reservations, blockers, and next action
   - `STATE.md` summarizes the current swarm status for humans
   - `HANDOFF.json` captures pause and resume details when the session stops early
8. Inspect ready descendants:
   ```bash
   br ready --parent <epic-id> --json --no-db
   ```
9. Initialize shared Agent Mail and acquire the epic lock for this coordinator:
   - Windows:
     ```powershell
     .\scripts\windows\agent-mail.ps1 --repo . init
     .\scripts\windows\agent-mail.ps1 --repo . register --name coordinator/<epic-id> --role coordinator --epic-id <epic-id>
     .\scripts\windows\agent-mail.ps1 --repo . acquire-epic --epic-id <epic-id> --owner coordinator/<epic-id>
     ```
   - POSIX:
     ```bash
     ./scripts/posix/agent-mail.sh --repo . init
     ./scripts/posix/agent-mail.sh --repo . register --name coordinator/<epic-id> --role coordinator --epic-id <epic-id>
     ./scripts/posix/agent-mail.sh --repo . acquire-epic --epic-id <epic-id> --owner coordinator/<epic-id>
     ```
10. Choose execution mode:
   - preferred: coordinator plus fresh workers with Agent Mail reservations
   - fallback: sequential epic execution in the current session when Agent Mail or worker spawning is unavailable
11. Coordinator rules:
   - the coordinator is the only writer for `br update --no-db` and `br close --no-db`
   - move only assigned ready leaf beads to `in_progress`; do not mark the epic itself `in_progress` just because child work has started
   - each worker owns at most one bead at a time
   - do not assign a bead until its file scope is reserved or confirmed conflict-free in the shared control plane
   - do not rely on prior epic chat as worker context; assignment must include the persisted bead contract
   - update `.beads/workflow/state.json` and `.beads/workflow/STATE.md` after every assignment, completion, blocker, and reservation change
12. For each ready bead:
   - inspect the bead contract
   - confirm the bead is fresh-session-safe and includes `Read:`, `Inputs:`, `Files:`, `Verify:`, `Risk:`, `Parallel:`, and `Escalate:`
   - reserve the declared file scope with Agent Mail before work starts
   - assign the bead to `execute-bead-worker` as a fresh worker context
   - pass the full persisted contract in the assignment payload instead of telling the worker to infer missing context from the coordinator session
   - require the worker to report changed files, verification evidence, released reservations, and blocker classification when blocked
   - require the worker to report which persisted inputs were consumed and any closeout note needed for downstream beads
   - independently review the report before closing the bead
13. For each assignment, post a thread message so other sessions can inspect coordinator intent:
   - thread naming: `epic/<epic-id>` for coordinator broadcasts, `bead/<bead-id>` for bead-specific traffic
   - post `assignment`, `blocked`, `completed`, and `release` messages
   - use the concrete Agent Mail CLI shape:
     - `post --thread epic/<epic-id> --sender coordinator/<epic-id> --type assignment --body '<json>'`
     - `post --thread bead/<bead-id> --sender worker/<bead-id> --type started --body '<json>'`
14. When Agent Mail is unavailable:
   - record the degraded mode in `state.json`
   - execute one descendant bead at a time within the same checkout and epic
   - preserve the same fresh-worker mental model: treat each bead as a fresh executor unit and do not rely on accumulated chat memory if the bead contract is incomplete
   - keep the same coordinator-owned status updates and runtime files
15. When a worker blocks:
   - read the worker's blocker classification
   - if the blocker is `clarify` or `env`, prefer replying to the same worker after clarifying the instruction or fixing the environment
   - if the blocker is `contract` or `scope`, prefer tightening the bead, splitting work, creating a follow-up bead, or spawning a fresh worker instead of continuing the same worker session
   - decide whether to reassign, tighten the bead, create a follow-up bead, or stop for user input
   - record the blocker in both `state.json` and `STATE.md`
16. When the epic has no ready descendants left:
   - run the repo-local `build-and-test` skill one final time for the whole epic
   - automatically run `review-epic` as part of swarm completion
   - if the review passes or only yields non-blocking follow-up work, use `finishing-a-development-branch <epic-id>`
17. When stopping early:
   - write `HANDOFF.json`
   - release any outstanding reservations owned by the coordinator
   - release the epic lock if no worker still depends on this session
   - summarize active workers, claimed or assigned beads, blockers, and the next command to run

## Reservation Policy

- Use Agent Mail threads to announce reservations and releases.
- Reserve only the declared `Files:` scope for the active bead.
- If two beads want overlapping files, serialize them unless the overlap is demonstrably safe.
- Never leave a stale reservation behind when a worker stops, hands off, or fails verification.
- Agent Mail reservations coordinate workers inside the current epic run. Do not use them as justification for multiple independent top-level code-writing sessions in one checkout.

## Hard Rules

- Stay within the target epic.
- Do not let workers mutate bead state directly.
- Do not assign beads that failed validation.
- Prefer sequential fallback over unreliable pseudo-parallel execution.
- The coordinator should not implement code directly unless the run has explicitly fallen back to sequential mode.
- Do not assign a bead that still depends on conversational memory instead of persisted `Inputs:`.
- Treat blocked workers as reusable only when the blocker is local and clarifiable. If the bead contract or scope is wrong, fix the bead and prefer a fresh worker.
- If `acquire-epic` fails because another coordinator owns the lock, stop and inspect `workflow-status` instead of forcing progress.
- Treat execution-branch inspection, commit-prefix discipline, and epic review as part of the default `swarm-epic` composition, not optional operator memory.
- Do not require a clean worktree just to start the epic. Keep commits scoped by staging explicit paths or hunks.
