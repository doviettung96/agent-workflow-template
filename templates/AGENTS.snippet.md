<!-- BEGIN TEMPLATE BR WORKFLOW -->
## Workflow Guide

Use `BEADS_WORKFLOW.md` for the current planner, manual executor, and swarm executor flow. All workflow skills are repo-local: Codex skills live under `.codex/skills/`, Claude skills under `.claude/skills/`.

Preferred entry points are `plan-beads`, `swarm-epic`, and `executor-once`. `plan-beads` should end with `validate-beads` for swarmable epics, and `swarm-epic` should handle worktree setup plus final epic review. Use `executor-loop` or `executor-loop-epic` for sequential autonomy when swarm coordination is not needed.

The executor test skill lives at `.codex/skills/build-and-test/SKILL.md`; use it between implementation and final verification.

Use `scripts/windows/workflow-status.ps1` or `scripts/posix/workflow-status.sh` to inspect `.beads/workflow/` plus the shared control plane. Use `scripts/windows/agent-mail.ps1` or `scripts/posix/agent-mail.sh` for shared epic locks, reservations, and mailbox inspection. `start-epic-worktree` remains available as a helper, but `swarm-epic` should normally handle that step.

## Issue Tracking With `br`

- Use `br` for all issue tracking
- Do not use markdown TODO files, TodoWrite, or alternate trackers
- `.beads/` is committed to git and travels with the repo
- This template standardizes `.beads/config.yaml` with `no-db: true`

## Essential Commands

```bash
br ready --json
br show <id> --json
br create --title="Summary" --description="Details" --type=task|bug|feature|epic --priority=2
br update <id> --status=in_progress
br close <id> --reason="Completed"
br dep add <child-id> <parent-id>
```

## Session Protocol

```bash
git status
git add <files> .beads/
git commit -m "..."
```

## Notes

- Epics must use `--type=epic`
- Check `br ready` before asking what to work on next
- Different sessions may coordinate with Agent Mail across worktrees, but only the coordinator updates bead status during swarm execution
<!-- END TEMPLATE BR WORKFLOW -->
