# Beads Workflow

This repo uses `br` (`beads_rust`) for task state and selected execution-quality skills for planning and delivery. Beads remains the source of truth for `epic`, `task`, `bug`, and `chore` state.

The template standard is `.beads/config.yaml` with `no-db: false`. Normal `br` mutations use the shared live Beads store for this clone in the clone-local path reported by `shared-beads status`, while the repo-tracked `.beads/issues.jsonl` is an explicit snapshot for Git sharing across machines. In ordinary sessions run `br sync --flush-only` before commit or handoff so the shared live JSONL reflects the latest DB state. Use `shared-beads attach` when preparing a checkout, and `shared-beads export-snapshot` from the main checkout when you want the tracked snapshot updated.

## Two-Session Model

Work is split into planner sessions and executor sessions. Planner sessions define bead structure. Executor sessions deliver one bead manually or coordinate many beads under one epic.

## Workflow Skills

Codex and Claude can enter the workflow through repo-local skills installed under `.codex/skills/` and `.claude/skills/`:

- `plan-beads`
- `planner-research`
- `validate-beads`
- `start-epic-worktree`
- `shared-beads`
- `executor-once`
- `executor-loop`
- `executor-loop-epic`
- `swarm-epic`
- `review-epic`

`execute-bead-worker` is a worker contract invoked by `swarm-epic` for assigned bead execution.

## Planner Session

1. `brainstorming`
2. `planner-research` only when discussion still leaves factual uncertainty that affects the plan
3. `beads-planner`
4. `validate-beads` in the same planner session before it ends when the epic is intended for swarm execution

Entry: a problem statement, feature idea, or bug report.  
Exit: beads created with dependencies and, for swarmable epics, a validated execution contract.

`brainstorming` is the discuss stage. It should end with an approved Beads-ready design, not a committed spec doc or executor handoff.

`planner-research` is a planner helper, not a second workflow system. Its output should be folded into the approved design and the resulting bead descriptions or notes rather than stored as a separate source of truth.

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

All manual status changes should be one bead at a time. Do not batch multiple ids into one `br update` or `br close`.

## Swarm Executor Session

1. `swarm-epic` - create or reuse the dedicated worktree for `epic/<epic-id>` if needed, attach it to the shared live Beads store, initialize `.beads/workflow/`, acquire the shared epic lock, inspect ready descendants, coordinate execution, and finish with epic review
3. `execute-bead-worker` - workers reserve file scope through Agent Mail, implement one assigned bead, verify it, and report evidence back to the coordinator
4. `build-and-test`
5. `review-epic`
6. `finishing-a-development-branch`

Entry: a validated epic id.  
Exit: all intended child beads are closed or blocked with handoff state, the epic has been reviewed automatically by the swarm flow, and the branch is ready for PR or waiting on a blocker.

`start-epic-worktree` remains available as a standalone helper, but the default operator path is to invoke `swarm-epic` directly and let it ensure the correct worktree and shared Beads attachment.

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

Use `scripts/windows/workflow-status.ps1` or `scripts/posix/workflow-status.sh` to inspect the current worktree runtime plus shared control-plane and shared live Beads state.

## Agent Mail

Swarm execution uses a shared control plane under `git rev-parse --git-common-dir` so every worktree for the repo sees the same mailbox and reservation state:

- `agents.json`
- `reservations.json`
- `locks/epic-*.json`
- `threads/*.jsonl`

Use:

- `scripts/windows/agent-mail.ps1`
- `scripts/posix/agent-mail.sh`

The same Git common dir also holds the live Beads store shared by every worktree in the clone:

- clone-shared `_beads/issues.jsonl` - live shared Beads JSONL
- clone-shared `_beads/beads.db*` - live shared SQLite store
- local `.beads/redirect` - untracked stub that makes plain `br` resolve to the shared live store
- repo `.beads/issues.jsonl` - explicit snapshot/export, not the live intra-clone store

## Session Boundaries

- Planner sessions do not write code.
- Manual executor sessions do not re-plan from scratch.
- Swarm workers do not mutate bead state. They implement, verify, and report. The coordinator handles `br update` and `br close`.

## Mutation Error Recovery

- If any `br update` or `br close` command errors, stop issuing further bead mutations.
- Immediately inspect the same bead with `br show <id> --json`.
- Use `scripts/windows/shared-beads.ps1 status` or `scripts/posix/shared-beads.sh status` to find the live shared `issues.jsonl`, then inspect the same id there.
- If DB and JSONL both already show the intended state, continue from that state without replaying the mutation.
- If DB and JSONL disagree, reconcile JSONL before more status changes or handoff.
- Prefer one-bead mutations over batched status changes in all manual and swarm flows.
- If single-bead mutations keep failing in one worktree and the live shared JSONL looks sane, rebuild the shared DB cache from that JSONL. See `docs/TROUBLESHOOTING.md`.

## Branch and PR Workflow

Work happens on feature branches. Swarm execution uses one dedicated worktree per epic branch. Merging to `main` is done via pull requests, not local merges.

- Live Beads state is shared per clone in the clone-local path reported by `shared-beads status`
- Export the repo snapshot from the main checkout when you want Beads state committed for Git sharing
- Do not commit `.beads/workflow/`; it is local worktree runtime
- Use pull requests to merge to `main`

## Cross-Machine Sharing

Inside one clone, every worktree already sees the same live Beads state. You only need a snapshot export when another clone or another machine needs to inherit that state through Git.

Use this from the main checkout:

```bash
br sync --flush-only
./scripts/posix/shared-beads.sh --repo . export-snapshot
```

On Windows:

```powershell
br sync --flush-only
.\scripts\windows\shared-beads.ps1 --repo . export-snapshot
```

Typical times to run this:

- before pushing `main` when bead state changed
- after merging epic work back into `main`
- before switching to another machine

You do not need snapshot export for normal in-progress work inside one clone.

## Ownership Rules

- Beads owns task state.
- The main coordinator session owns Beads updates during `swarm-epic`.
- Manual executor sessions own their own Beads updates through `beads-claim` and `beads-close`.
- Agent Mail owns shared epic locks, worker mail, and file reservations during swarm execution.
- All skills are repo-local: Codex skills live under `.codex/skills/`, Claude skills under `.claude/skills/`.
