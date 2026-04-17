# Beads Workflow

This repo uses **`bd`** for task state and selected execution-quality skills for planning and delivery. Beads remains the source of truth for `epic`, `task`, `bug`, and `chore` state.

## Local-Only Beads Model

- The current checkout owns the live `.beads/` database.
- Live Beads state is local to this clone and is not shared through Git.
- Run one top-level epic executor session at a time in a clone to avoid shared-checkout Git conflicts.

## Workflow Skills

Codex and Claude Code can enter the workflow through repo-local skills installed under `.codex/skills/` and `.claude/skills/`:

- `plan-beads`
- `plan-debate`
- `executor-once`
- `executor-loop`
- `executor-loop-epic`
- `swarm-epic`
- `review-epic`

When an executor skill stops on a blocker, continue in normal chat by telling the agent to resume the blocked bead. For long epics, prefer a fresh session per bead over one continuously growing executor thread.

## Planner Session

Turns a fuzzy idea into structured, claimable beads. No code is written.

1. `brainstorming` - clarify scope, options, and design direction
2. `planner-research` - only if material factual uncertainty remains
3. `plan-debate` - optional adversarial review when the user asks for extra scrutiny or the plan is risky
4. `beads-planner` - translate the design into Beads epics, tasks, and dependencies
5. `validate-beads` - confirm the epic is swarm-ready and fresh-session-safe when parallel execution is intended

Entry: a feature idea, bug report, or project change.
Exit: beads created with dependencies, ready for `bd ready` or `swarm-epic`.

Swarm-ready does not mean dependency-free. It means each bead carries enough persisted context that a fresh worker can execute it without replaying the prior epic chat.

## Manual Executor Session

Claims one bead and delivers it.

1. `beads-claim`
2. `writing-plans`
3. implement
4. `systematic-debugging` if blocked
5. repo-local `build-and-test`
6. `requesting-code-review` or `verification-before-completion`
7. `beads-close`

Entry: a ready bead from `bd ready`.
Exit: bead closed, code committed, follow-up beads created if needed.

For manual work on longer epics, prefer repeated fresh `executor-once` sessions bead-by-bead. Treat `executor-loop` and `executor-loop-epic` as compatibility paths when a long-lived session is still acceptable.

## Epic Swarm Session

Use `swarm-epic <epic-id>` when one epic has multiple ready descendants that can safely move in parallel.

Default composition:

1. `swarm-epic`
2. create or check out branch `epic/<epic-id>` in the current checkout
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
- Manual executor sessions do not re-plan the whole project.
- Epic swarm sessions stay inside one epic.
- Do not run multiple top-level code-writing epic sessions in the same checkout at the same time.

## Branch and PR Workflow

- Do code work on feature branches.
- Open pull requests instead of merging locally.
- Beads state itself is local-only; code moves through Git, not Beads exports.
- `finishing-a-development-branch` handles push and PR creation.

## Operational Notes

- Run `scripts/windows/workflow-status.ps1` or `scripts/posix/workflow-status.sh` to inspect checkout runtime plus Agent Mail state.
- Keep repo exploration local. Route runtime-dependent project commands through `scripts/shared/target_runtime.py` when the checkout config selects SSH execution.
- If `bd where` or `bd context` fails in the current checkout, repair the repo with `bd bootstrap --yes` before continuing.
- Use `bd ready` before asking what to work on next.
