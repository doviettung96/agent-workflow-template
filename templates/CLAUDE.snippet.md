<!-- BEGIN TEMPLATE BD WORKFLOW -->
This repo uses `bd` for issue tracking. Use `bd`, not markdown TODO files or alternate trackers.

Live `.beads` state is local-only and should not be committed. Use one top-level epic executor session at a time in a checkout.

Preferred workflow entry points are `plan-beads`, `swarm-epic`, and `executor-once`. Use `planner-research` only inside planner sessions and keep `writing-plans` executor-only. Treat long-running loop executors as compatibility paths rather than the default for epic work.

Swarm-ready beads must be fresh-session-safe: a fresh worker should be able to execute from the bead contract, persisted inputs, and local code inspection without replaying prior chat.

Workflow scaffold files such as `AGENTS.md`, `CLAUDE.md`, `BEADS_WORKFLOW.md`, `docs/plans/`, and repo-local skills stay local-only in downstream Git. Mirror them to the backup repo with `scripts/windows/sync-workflow-backup.ps1` or `scripts/posix/sync-workflow-backup.sh` before opening a PR.

Keep repo exploration local. If `.beads/workflow/runtime-target.json` selects SSH, route build, test, run, deploy, migration, or other project-execution commands through `scripts/shared/target_runtime.py` or the repo-local `target-runtime-exec` skill instead of assuming the local machine.

Useful commands:

```bash
bd ready --json
bd show <id> --json
bd update <id> --status=in_progress
bd close <id> --reason="Completed"
bd dep add <child-id> <parent-id>
```
<!-- END TEMPLATE BD WORKFLOW -->
