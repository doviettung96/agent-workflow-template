# Beads Workflow

This repo uses **`br --no-db`** for task state and selected execution-quality skills for planning and delivery. Beads remains the source of truth for `epic`, `task`, `bug`, and `chore` state.

## Local-Only Beads Model

- The current checkout owns the live `.beads/` state.
- Live Beads state is local to this clone and is not shared through Git.
- Run one top-level epic executor session at a time in a clone to avoid shared-checkout Git conflicts.
- If you want checkout isolation for a parallel epic, use `start-epic-worktree` from the current checkout. It creates a Git worktree and hydrates the local-only workflow files into it.

## Workflow Skills

Codex and Claude Code can enter the workflow through repo-local skills installed under `.codex/skills/` and `.claude/skills/`:

- `plan-beads`
- `start-epic-worktree`
- `executor-once`
- `executor-loop`
- `executor-loop-epic`
- `swarm-epic`
- `review-epic`

When an executor skill stops on a blocker, continue in normal chat by telling the agent to resume the blocked bead. For long epics, prefer `swarm-epic` or repeated worker-backed `executor-once` cycles over one continuously growing executor thread.

## Planner Session

Turns a fuzzy idea into structured, claimable beads. No code is written.

1. `brainstorming` - clarify scope, options, and design direction
2. `planner-research` - only if material factual uncertainty remains
3. brief the settled recommendation and confirm Beads creation
4. `beads-planner` - translate the design into Beads epics, tasks, and dependencies
5. `validate-beads` - confirm the epic is swarm-ready and fresh-session-safe when parallel execution is intended

Entry: a feature idea, bug report, or project change.
Exit: beads created with dependencies, ready for `br ready --no-db` or `swarm-epic`.

Worker-ready does not mean dependency-free. It means each bead carries enough persisted context that a fresh worker can execute it without replaying the prior epic chat.

## Single-Bead Executor Session

Claims one bead, dispatches a fresh worker, reviews the result, verifies, and closes it.

1. `beads-claim`
2. `execute-bead-worker` for implementation
3. coordinator review of the worker report
4. repo-local `build-and-test`
5. `requesting-code-review` or `verification-before-completion`
6. `beads-close`

Entry: a ready bead from `br ready --no-db`.
Exit: bead closed, code committed, follow-up beads created if needed.

If worker spawning is unavailable, `executor-once` stops and reports the blocker instead of falling back to coordinator-local implementation. `executor-loop` remains the compatibility path for old current-session manual execution. `executor-loop-epic` is sequential but still worker-backed: one ready descendant bead, one fresh worker, one closeout.

## Epic Swarm Session

Use `swarm-epic <epic-id>` when one epic has multiple ready descendants that can safely move in parallel.

If that epic should run in its own checkout, start with `start-epic-worktree` in the source checkout and then continue inside the new worktree.

Default composition:

1. `swarm-epic`
2. create or check out branch `epic/<epic-id>` in the current checkout or prepared worktree
3. coordinator assigns work and owns bead-state changes
4. `execute-bead-worker` for worker execution
5. final repo-local `build-and-test`
6. `review-epic`
7. `finishing-a-development-branch`

In swarm mode:

- only the coordinator mutates Beads state
- workers implement, verify, and report
- workers are fresh per bead and rely on the bead contract plus local inspection, not the full coordinator chat history
- blocked workers classify the blocker so the coordinator can decide whether to reply to the same worker or replace it with a fresh one
- Agent Mail owns epic locks, file reservations, and message threads
- local `.beads/workflow/` stores checkout-local runtime and handoff state

## Session Boundaries

- Planner sessions do not write code.
- Executor sessions do not re-plan the whole project.
- Epic swarm sessions stay inside one epic.
- Do not run multiple top-level code-writing epic sessions in the same checkout at the same time.

## Branch and PR Workflow

- Do code work on feature branches.
- Open pull requests instead of merging locally.
- Beads state itself is local-only; code moves through Git, not Beads exports.
- Workflow scaffold files stay local-only in downstream Git and are mirrored to the backup repo with `scripts/posix/sync-workflow-backup.sh` or `scripts/windows/sync-workflow-backup.ps1`.
- `finishing-a-development-branch` handles workflow-backup sync, branch push, and PR creation.

## Operational Notes

- Run `scripts/windows/workflow-status.ps1` or `scripts/posix/workflow-status.sh` to inspect checkout runtime plus Agent Mail state.
- Run `scripts/windows/sync-workflow-backup.ps1` or `scripts/posix/sync-workflow-backup.sh` before a PR when you need to sync workflow docs, skills, or helper scripts outside the normal branch-finish flow.
- Keep repo exploration local. Route runtime-dependent project commands through `scripts/shared/target_runtime.py` when the checkout config selects SSH execution.
- If `br where --no-db` or `br info --json --no-db` fails in the current checkout, repair the repo with `br init --prefix <prefix> --no-db` before continuing.
- Use `br ready --no-db` before asking what to work on next.

## Game-RE Profile (optional)

Repos bootstrapped with `-Profile game-re` (`--profile game-re` on posix) additionally install the `game-action-harness` skill and `scripts/shared/harness.py`. That combination lets executor and debugging sessions trigger in-game actions (tap, click, key, swipe) and observe the effect through the project's existing hook logs / memory / packet capture — no OpenCV or OCR. When a plan's `## Verification` would otherwise require a human click, rewrite it as `python scripts/shared/harness.py trigger <action> --json` and keep the executor autonomous. Catalog lives at `.harness/actions.yaml`; see the stage-2 follow-up bead "Populate action catalog for this repo" and `skills/game-action-harness/reference.md`.
