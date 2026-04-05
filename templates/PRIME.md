# Prime

> **Context Recovery**: start from `bd ready`, `bd list --status open`, `bd list --status in_progress`, and `bd show <id>`.

## Core Rules

- Default: use `bd` for all issue tracking
- Do not create parallel TODO lists or markdown trackers
- Live `.beads` state is local-only and not meant for Git sharing
- Epic worktrees must come from `bd worktree create` or `start-epic-worktree`
- Planner sessions stay planner-only; executor sessions do implementation

## Useful Commands

```bash
bd ready
bd show <id>
bd update <id> --status=in_progress
bd close <id> --reason="Completed"
bd dep add <child-id> <parent-id>
bd worktree create <name> --branch epic/<epic-id>
```

## Workflow Pointers

- `plan-beads` handles discuss -> optional research -> bead creation -> validation
- `executor-once` is the manual single-bead executor
- `swarm-epic` is the epic-scoped composed executor
- `review-epic` runs before branch completion in swarm flow

## Recovery

- If a worktree cannot see the Beads database, inspect `bd where`
- If the redirect or local server state looks wrong, recreate the worktree with `bd worktree create`
- If recovery is needed in the main checkout, use `bd bootstrap --yes`
