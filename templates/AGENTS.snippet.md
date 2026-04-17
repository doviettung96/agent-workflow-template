<!-- BEGIN TEMPLATE BD WORKFLOW -->
## Workflow Guide

Use `BEADS_WORKFLOW.md` for the current planner, manual executor, and swarm executor flow. All workflow skills are repo-local: Codex skills live under `.codex/skills/`, Claude skills under `.claude/skills/`.

Preferred entry points are `plan-beads`, `swarm-epic`, and `executor-once`. Use `planner-research` only inside a planner session when `brainstorming` still leaves material factual uncertainty. Use `plan-debate` before `beads-planner` when the user asks for extra scrutiny or the plan is risky. Treat `executor-loop` and `executor-loop-epic` as compatibility paths, not the default for long epic execution.

The executor test skill lives at `.codex/skills/build-and-test/SKILL.md`; use it between implementation and final verification.

Use `scripts/windows/workflow-status.ps1` or `scripts/posix/workflow-status.sh` to inspect `.beads/workflow/`, the shared control plane, and Beads backend state. Use `scripts/windows/agent-mail.ps1` or `scripts/posix/agent-mail.sh` for shared epic locks, reservations, and mailbox inspection.

Keep repo exploration local. If `.beads/workflow/runtime-target.json` selects SSH, route build, test, run, deploy, migration, or other project-execution commands through `scripts/shared/target_runtime.py` or the repo-local `target-runtime-exec` skill instead of assuming the local machine.

## Issue Tracking With `bd`

- Use `bd` for all issue tracking
- Do not use markdown TODO files, TodoWrite, or alternate trackers
- Live `.beads` state is local-only and should not be committed
- Run one top-level epic executor session at a time in a checkout

## Essential Commands

```bash
bd ready --json
bd show <id> --json
bd create --title="Summary" --description="Details" --type=task|bug|feature|epic --priority=2
bd update <id> --status=in_progress
bd close <id> --reason="Completed"
bd dep add <child-id> <parent-id>
git checkout -b epic/<epic-id>
```

## Notes

- Epics must use `--type=epic`
- Check `bd ready` before asking what to work on next
- `swarm-epic` may coordinate workers inside one epic, but only the coordinator updates bead status during swarm execution
- Swarm-ready beads must be fresh-session-safe: a fresh worker should be able to execute from the bead contract, persisted inputs, and local code inspection without replaying prior chat
- If the current checkout cannot open the Beads database, inspect `bd where` and run `bd bootstrap --yes` before continuing
<!-- END TEMPLATE BD WORKFLOW -->
