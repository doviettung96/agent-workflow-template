# Beads Workflow

This repo uses `br` (`beads_rust`) for task state and selected execution-quality skills for planning and delivery. Beads remains the source of truth for `epic`, `task`, `bug`, and `chore` state.

The template standard is `.beads/config.yaml` with `no-db: true`, so normal `br` mutations write the repo-shared JSONL directly. In ordinary sessions you commit `.beads/` alongside code; you do not need routine `br sync --flush-only`.

## Two-Session Model

Work is split into planner sessions and executor sessions. Planner sessions define bead structure. Executor sessions deliver one bead manually or coordinate many beads under one epic.

## Workflow Skills

Codex and Claude can enter the workflow through repo-local skills installed under `.codex/skills/` and `.claude/skills/`:

- `plan-beads`
- `validate-beads`
- `start-epic-worktree`
- `executor-once`
- `executor-loop`
- `executor-loop-epic`
- `swarm-epic`
- `review-epic`

`execute-bead-worker` is a worker contract invoked by `swarm-epic` for assigned bead execution.

## Planner Session

1. `brainstorming`
2. `beads-planner`
3. `validate-beads` in the same planner session before it ends when the epic is intended for swarm execution

Entry: a problem statement, feature idea, or bug report.  
Exit: beads created with dependencies and, for swarmable epics, a validated execution contract.

## Manual Executor Session

1. `beads-claim` - `br ready`, choose the next task, inspect it, then `br update <id> --status=in_progress`
2. `writing-plans`
3. implement
4. `systematic-debugging` if blocked
5. `build-and-test`
6. `requesting-code-review` or `verification-before-completion`
7. `beads-close`

Entry: a claimed bead from `br ready`.  
Exit: bead closed, code committed, follow-up beads created if needed.

## Swarm Executor Session

1. `swarm-epic` - create or reuse the dedicated worktree for `epic/<epic-id>` if needed, run inside that worktree, initialize `.beads/workflow/`, acquire the shared epic lock, inspect ready descendants, coordinate execution, and finish with epic review
3. `execute-bead-worker` - workers reserve file scope through Agent Mail, implement one assigned bead, verify it, and report evidence back to the coordinator
4. `build-and-test`
5. `review-epic`
6. `finishing-a-development-branch`

Entry: a validated epic id.  
Exit: all intended child beads are closed or blocked with handoff state, the epic has been reviewed automatically by the swarm flow, and the branch is ready for PR or waiting on a blocker.

`start-epic-worktree` remains available as a standalone helper, but the default operator path is to invoke `swarm-epic` directly and let it ensure the correct worktree.

## Swarm-Ready Bead Contract

Any bead intended for `swarm-epic` should encode enough detail for a worker to start without replaying the full planning conversation:

- `Files:` exact file paths or directory scope the worker may touch
- `Verify:` exact commands or checks the worker must run before reporting success
- `Risk:` `low`, `medium`, or `high`
- `Parallel:` whether the bead can run in parallel and what it must not overlap with
- `Escalate:` what the worker should do if blocked or if the scope expands

If these fields are missing, `validate-beads` should fail the epic for swarm use until the bead is corrected.

## Runtime Files

Swarm execution uses `.beads/workflow/` for repo-local runtime state:

- `state.json`
- `STATE.md`
- `HANDOFF.json`

Use `scripts/windows/workflow-status.ps1` or `scripts/posix/workflow-status.sh` to inspect the current worktree runtime plus shared control-plane state.

## Agent Mail

Swarm execution uses a shared control plane under `git rev-parse --git-common-dir` so every worktree for the repo sees the same mailbox and reservation state:

- `agents.json`
- `reservations.json`
- `locks/epic-*.json`
- `threads/*.jsonl`

Use:

- `scripts/windows/agent-mail.ps1`
- `scripts/posix/agent-mail.sh`

## Session Boundaries

- Planner sessions do not write code.
- Manual executor sessions do not re-plan from scratch.
- Swarm workers do not mutate bead state. They implement, verify, and report. The coordinator handles `br update` and `br close`.

## Branch and PR Workflow

Work happens on feature branches. Swarm execution uses one dedicated worktree per epic branch. Merging to `main` is done via pull requests, not local merges.

- Beads state (`.beads/`) is committed to git
- Commit code changes and `.beads/` issue changes together
- Do not commit `.beads/workflow/`; it is local worktree runtime
- Use pull requests to merge to `main`

## Ownership Rules

- Beads owns task state.
- The main coordinator session owns Beads updates during `swarm-epic`.
- Manual executor sessions own their own Beads updates through `beads-claim` and `beads-close`.
- Agent Mail owns shared epic locks, worker mail, and file reservations during swarm execution.
- All skills are repo-local: Codex skills live under `.codex/skills/`, Claude skills under `.claude/skills/`.
