<!-- BEGIN TEMPLATE BD WORKFLOW -->
## Workflow Guide

Use `BEADS_WORKFLOW.md` for the current planner, manual executor, and swarm executor flow. All workflow skills are repo-local: Codex skills live under `.codex/skills/`, Claude skills under `.claude/skills/`.

Preferred entry points are `plan-beads`, `swarm-epic`, and `executor-once`. Use `planner-research` only inside a planner session when `brainstorming` still leaves material factual uncertainty. Use `executor-loop` or `executor-loop-epic` for sequential autonomy when swarm coordination is not needed.

The executor test skill lives at `.codex/skills/build-and-test/SKILL.md`; use it between implementation and final verification.

Use `scripts/windows/workflow-status.ps1` or `scripts/posix/workflow-status.sh` to inspect `.beads/workflow/`, the shared control plane, and Beads backend state. Use `scripts/windows/agent-mail.ps1` or `scripts/posix/agent-mail.sh` for shared epic locks, reservations, and mailbox inspection. Use `start-epic-worktree` or native `bd worktree create` for epic worktrees; do not use raw `git worktree add`.

## Issue Tracking With `bd`

- Use `bd` for all issue tracking
- Do not use markdown TODO files, TodoWrite, or alternate trackers
- Live `.beads` state is local-only and should not be committed
- Worktrees share the main checkout’s `.beads` through Beads redirect files

## Essential Commands

```bash
bd ready --json
bd show <id> --json
bd create --title="Summary" --description="Details" --type=task|bug|feature|epic --priority=2
bd update <id> --status=in_progress
bd close <id> --reason="Completed"
bd dep add <child-id> <parent-id>
bd worktree create <name> --branch epic/<epic-id>
```

## Notes

- Epics must use `--type=epic`
- Check `bd ready` before asking what to work on next
- Different sessions may coordinate with Agent Mail across worktrees, but only the coordinator updates bead status during swarm execution
- If a worktree cannot open the Beads database, inspect `bd where` and recreate the worktree with `bd worktree create` or run `bd bootstrap --yes` from the main checkout
<!-- END TEMPLATE BD WORKFLOW -->
