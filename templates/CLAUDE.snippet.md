<!-- BEGIN TEMPLATE BD WORKFLOW -->
This repo uses `bd` for issue tracking. Use `bd`, not markdown TODO files or alternate trackers.

Live `.beads` state is local-only and should not be committed. Worktrees share the main checkout’s `.beads` through Beads redirect files, so use `start-epic-worktree` or native `bd worktree create` for epic branches instead of raw `git worktree add`.

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
