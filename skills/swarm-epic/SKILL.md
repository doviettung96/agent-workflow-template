---
name: swarm-epic
description: "Coordinate multi-agent execution for one epic. Use after planning when the user wants parallel work across ready descendant beads with coordinator-owned Beads state, automatic worktree setup, automatic epic review, runtime files, and Agent Mail reservations."
---

# Swarm Epic

Coordinate epic-scoped execution across one or more workers.

## Goal

Drive an epic to completion while keeping the shared live `br`/`.beads` store as the single source of truth and avoiding split-brain state between workers.

## Steps

1. If the current repo is not initialized for Beads, stop and tell the user to run the template bootstrap script or at minimum `br init --prefix <prefix>` plus the repo scaffolding steps.
2. Determine the target epic:
   - if the user supplied an epic id, use it
   - otherwise ask for the epic id or enough selector text to identify one unambiguously
3. Inspect the epic:
   ```bash
   br show <epic-id> --json
   ```
4. Ensure the epic has passed `validate-beads`. In the normal flow this should already be true because `plan-beads` ends with validation. If the epic has not been validated, stop and run that gate first.
5. Ensure the current execution context is the dedicated worktree for `epic/<epic-id>`:
   - if already inside the correct worktree on branch `epic/<epic-id>`, continue
   - otherwise automatically run `start-epic-worktree`, switch to or reopen the returned worktree, and continue there
   - do not continue epic swarm execution from a shared checkout when concurrent epic work is possible
6. Ensure this worktree is attached to the shared live Beads store before execution:
   ```bash
   ./scripts/posix/shared-beads.sh --repo . attach
   ```
   On Windows, use `.\scripts\windows\shared-beads.ps1 --repo . attach`.
7. Initialize or refresh local `.beads/workflow/` in this worktree:
   - `state.json` tracks mode, coordinator identity, workers, assignments, reservations, blockers, and next action
   - `STATE.md` summarizes the current swarm status for humans
   - `HANDOFF.json` captures pause and resume details when the session stops early
8. Inspect ready descendants:
   ```bash
   br ready --parent <epic-id> --json
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
   - preferred: coordinator plus workers with Agent Mail reservations
   - fallback: sequential epic execution in the current session when Agent Mail or worker spawning is unavailable
11. Coordinator rules:
   - the coordinator is the only writer for `br update` and `br close`
   - move only assigned ready leaf beads to `in_progress`; do not mark the epic itself `in_progress` just because child work has started
   - each worker owns at most one bead at a time
   - do not assign a bead until its file scope is reserved or confirmed conflict-free in the shared control plane
   - update `.beads/workflow/state.json` and `.beads/workflow/STATE.md` after every assignment, completion, blocker, and reservation change
12. For each ready bead:
    - inspect the bead contract
    - reserve the declared file scope with Agent Mail before work starts
    - assign the bead to `execute-bead-worker`
    - require the worker to report changed files, verification evidence, and released reservations
    - independently review the report before closing the bead
13. For each assignment, post a thread message so other sessions can inspect coordinator intent:
    - thread naming: `epic/<epic-id>` for coordinator broadcasts, `bead/<bead-id>` for bead-specific traffic
    - post `assignment`, `blocked`, `completed`, and `release` messages
    - use the concrete Agent Mail CLI shape:
      - `post --thread epic/<epic-id> --sender coordinator/<epic-id> --type assignment --body '<json>'`
      - `post --thread bead/<bead-id> --sender worker/<bead-id> --type started --body '<json>'`
14. When Agent Mail is unavailable:
    - record the degraded mode in `state.json`
    - execute one descendant bead at a time within the same worktree and epic
    - keep the same coordinator-owned status updates and runtime files
15. When a worker blocks:
    - decide whether to reassign, tighten the bead, create a follow-up bead, or stop for user input
    - record the blocker in both `state.json` and `STATE.md`
16. When the epic has no ready descendants left:
    - run the repo-local `build-and-test` skill one final time for the whole epic
    - automatically run `review-epic` as part of swarm completion
    - flush the latest Beads state back to the shared live JSONL before branch completion:
      ```bash
      br sync --flush-only
      ```
    - if the review passes or only yields non-blocking follow-up work, use `finishing-a-development-branch`
17. When stopping early:
    - write `HANDOFF.json`
    - run `br sync --flush-only` so handoff and status changes are preserved in the shared live JSONL
    - release any outstanding reservations owned by the coordinator
    - release the epic lock if no worker still depends on this session
    - summarize active workers, claimed or assigned beads, blockers, and the next command to run

## Reservation Policy

- Use Agent Mail threads to announce reservations and releases.
- Reserve only the declared `Files:` scope for the active bead.
- If two beads want overlapping files, serialize them unless the overlap is demonstrably safe.
- Never leave a stale reservation behind when a worker stops, hands off, or fails verification.
- Different sessions may run different epics at the same time from different worktrees. The epic lock prevents two coordinators from driving the same epic, and shared file reservations prevent unsafe overlap across epics.

## Hard Rules

- Stay within the target epic.
- Do not let workers mutate bead state directly.
- Do not assign beads that failed validation.
- Prefer sequential fallback over unreliable pseudo-parallel execution.
- The coordinator should not implement code directly unless the run has explicitly fallen back to sequential mode.
- If `acquire-epic` fails because another coordinator owns the lock, stop and inspect `workflow-status` instead of forcing progress.
- Treat worktree setup and epic review as part of the default `swarm-epic` composition, not optional operator memory.
