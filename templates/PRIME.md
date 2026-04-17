# Prime

> **Context Recovery**: start from `bd ready`, `bd list --status open`, `bd list --status in_progress`, and `bd show <id>`.

## Core Rules

- Default: use `bd` for all issue tracking
- Do not create parallel TODO lists or markdown trackers
- Live `.beads` state is local-only and not meant for Git sharing
- Run one top-level epic executor session at a time per checkout
- Planner sessions stay planner-only; executor sessions do implementation

## Useful Commands

```bash
bd ready
bd show <id>
bd update <id> --status=in_progress
bd close <id> --reason="Completed"
bd dep add <child-id> <parent-id>
git checkout -b epic/<epic-id>
```

## Workflow Pointers

- `plan-beads` handles discuss -> optional research -> optional debate -> bead creation -> validation
- `executor-once` is the manual single-bead executor
- `swarm-epic` is the epic-scoped composed executor
- `review-epic` runs before branch completion in swarm flow
- Swarm-ready beads must be fresh-session-safe: rely on the bead contract, persisted inputs, and local inspection rather than prior chat memory

## Recovery

- If the current checkout cannot see the Beads database, inspect `bd where`
- If local server state looks wrong, use `bd bootstrap --yes`
