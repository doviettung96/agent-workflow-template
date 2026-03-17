# Beads Workflow

This repo uses **bd** for task state and selected execution-quality skills for planning and delivery. Beads remains the source of truth for `epic`, `task`, `bug`, and `chore` state.

## Two-Session Model

Work is split into two distinct session types. Each session has its own skill chain and responsibilities.

## Workflow Skills

Codex and Claude Code can enter the workflow through repo-local skills installed under `.codex/skills/` and `.claude/skills/`:

- **`plan-beads`** - planner-only entry point; use the current conversation topic or an explicit planning request in your prompt
- **`executor-once`** - run one full executor cycle for one bead; optionally provide a bead id or selector in the request
- **`executor-loop`** - repeat executor cycles bead-by-bead until no ready work remains or a blocker requires input
- **`executor-loop-epic`** - repeat executor cycles, but only across ready descendant beads under one epic

When an executor skill stops on a blocker, continue in normal chat by telling Codex to resume or continue the blocked bead in the same session.

### Planner Session

Turns a fuzzy idea into structured, claimable beads. No code is written.

1. **`brainstorming`** - explore the problem, clarify scope/constraints/risks, produce an approved design spec
2. **`beads-planner`** - translate the approved spec into Beads epics, tasks, and dependencies

**Entry:** A problem statement, feature idea, or bug report.
**Exit:** Beads created with dependencies, ready for `bd ready`.

### Executor Session

Claims one bead and delivers it. All code happens here.

1. **`beads-claim`** - `bd ready`, choose the next task, inspect it, then `bd update <id> --status=in_progress`; Codex slash commands may auto-claim when the bead choice is unambiguous
2. **`writing-plans`** - write a detailed execution plan for that one bead (bite-sized steps, exact files, TDD, verification section)
3. **Implement** - execute the plan in the current session or worktree
4. **`systematic-debugging`** - use if blocked by unclear behavior, runtime failures, or conflicting assumptions
5. **`build-and-test`** - repo-local Codex skill at `.codex/skills/build-and-test/SKILL.md`; build, deploy, and test only the affected components. If tests fail, loop back to step 3 to fix, then re-run step 5.
6. **`requesting-code-review`** or **`verification-before-completion`** - verify work before marking complete
7. **`beads-close`** - close the bead, create discovered follow-up beads, `bd dolt pull`, commit locally

**Entry:** A claimed bead from `bd ready`.
**Exit:** Bead closed, code committed, follow-up beads created if needed.

## Session Boundaries

- **Planner sessions do not write code.** If the design reveals implementation is trivial, the planner still creates a bead - the executor handles it.
- **Executor sessions do not re-plan from scratch.** The bead description and any linked spec are the starting point. `writing-plans` produces a local execution plan for that one bead, not a project-level re-plan.
- **Multiple executor sessions can run in parallel** on different beads (use worktrees for isolation).

## Local Workflow

This workflow assumes ephemeral branches merged to main locally. There is no upstream push.

- Run `bd dolt pull` at session start and before committing
- Commit code changes locally
- Merge to main when ready (local merge, not push)

## Ownership Rules

- Beads owns task state.
- Execution-quality skills improve clarity, debugging, review, and worktree hygiene, but they do not replace Beads tracking.
- The main session owns Beads updates.
- Subagents can help with implementation, testing, or review, but should not mutate Beads unless explicitly asked.
- All skills are repo-local: Codex skills live under `.codex/skills/`, Claude skills under `.claude/skills/`.

## Multi-Agent Note

Plain Beads plus careful claiming and `git worktree` is the default workflow. Heavier multi-agent coordination layers are optional and should only be added if manual worktree discipline stops scaling.
