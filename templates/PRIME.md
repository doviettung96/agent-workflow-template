# Prime

> **Context Recovery**: start from `br ready --no-db`, `br list --status open --no-db`, `br list --status in_progress --no-db`, and `br show <id> --no-db`.

## Core Rules

- Default: use `br --no-db` for all issue tracking
- Do not create parallel TODO lists or markdown trackers
- Live `.beads` state is local-only and not meant for Git sharing
- Run one top-level epic executor session at a time per checkout
- Planner sessions stay planner-only; executor sessions do implementation

## Useful Commands

```bash
br ready --no-db
br show <id> --no-db
br update <id> --status=in_progress --no-db
br close <id> --reason="Completed" --no-db
br dep add <child-id> <parent-id> --type parent-child --no-db
git checkout -b epic/<epic-id>
```

## Workflow Pointers

- `plan-beads` handles discuss -> optional research -> optional debate -> bead creation -> validation
- `executor-once` is the worker-backed single-bead executor
- `swarm-epic` is the epic-scoped composed executor
- `review-epic` runs before branch completion in swarm flow
- Worker-ready beads must be fresh-session-safe: rely on the bead contract, persisted inputs, and local inspection rather than prior chat memory

## Recovery

- If the current checkout cannot see the Beads workspace, inspect `br where --no-db`
- If local server state looks wrong, use `br init --prefix <prefix> --no-db`
