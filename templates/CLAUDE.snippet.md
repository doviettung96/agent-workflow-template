<!-- BEGIN TEMPLATE BD WORKFLOW -->
This repo uses `bd` for issue tracking. Use `bd`, not markdown TODO files or alternate trackers.

Live `.beads` state is local-only and should not be committed. Use one top-level epic executor session at a time in a checkout.

Preferred workflow entry points are `plan-beads`, `swarm-epic`, and `executor-once`. Use `planner-research` only inside planner sessions, and keep `writing-plans` executor-only.

Useful commands:

```bash
bd ready --json
bd show <id> --json
bd update <id> --status=in_progress
bd close <id> --reason="Completed"
bd dep add <child-id> <parent-id>
```
<!-- END TEMPLATE BD WORKFLOW -->
