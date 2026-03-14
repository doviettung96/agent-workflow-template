# Beads Workflow

This repo uses **bd** for task state and selected execution-quality skills for planning and delivery. Beads remains the source of truth for `epic`, `task`, `bug`, and `chore` state.

## Recommended Flow

1. `brainstorming`
   Use when the problem is still fuzzy and needs scope, constraints, and risks clarified.
2. `beads-planner`
   Use to turn the approved problem or approved execution plan into Beads epics, tasks, and dependencies.
3. Claim a bead
   Use `bd ready --json`, choose the next task, then `bd update <id> --claim --json`.
4. `writing-plans`
   Use for the local execution plan of that one bead. This is not the same as the Beads planning step.
5. Implement
   Execute the task in the current session or worktree.
6. `systematic-debugging` if blocked
   Use when the task is blocked by unclear behavior, runtime failures, or conflicting assumptions.
7. `requesting-code-review` or `verification-before-completion`
   Use before marking the bead complete.
8. `beads-task-cycle`
   Close or update the bead, create discovered follow-up beads, sync Beads if you are publishing task state, then sync code if this repo's workflow publishes code immediately.

## Default Mode vs Plan Mode

- Use default mode when the problem is already clear and you just need to create beads or execute one claimed bead.
- Use plan mode when the problem is ambiguous, high-risk, or needs discussion before bead creation.
- If plan mode already produced an approved execution plan, `beads-planner` should use that plan directly instead of re-planning.

## Ownership Rules

- Beads owns task state.
- Execution-quality skills improve clarity, debugging, review, and worktree hygiene, but they do not replace Beads tracking.
- The main session owns Beads updates.
- Subagents can help with implementation, testing, or review, but should not mutate Beads unless explicitly asked.

## Multi-Agent Note

Plain Beads plus careful claiming and `git worktree` is the default workflow. Heavier multi-agent coordination layers are optional and should only be added if manual worktree discipline stops scaling.
