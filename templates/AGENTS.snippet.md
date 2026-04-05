<!-- BEGIN TEMPLATE BR WORKFLOW -->
## Workflow Guide

Use `BEADS_WORKFLOW.md` for the current planner, manual executor, and swarm executor flow. All workflow skills are repo-local: Codex skills live under `.codex/skills/`, Claude skills under `.claude/skills/`.

Preferred entry points are `plan-beads`, `swarm-epic`, and `executor-once`. `plan-beads` should end with `validate-beads` for swarmable epics, and `swarm-epic` should handle worktree setup plus final epic review. Use `planner-research` only inside a planner session when `brainstorming` still leaves material factual uncertainty. In this template, `brainstorming` is a planner-only discuss stage and should hand back to `planner-research` or `beads-planner`, not to `writing-plans`. Use `executor-loop` or `executor-loop-epic` for sequential autonomy when swarm coordination is not needed.

The executor test skill lives at `.codex/skills/build-and-test/SKILL.md`; use it between implementation and final verification.

Use `scripts/windows/workflow-status.ps1` or `scripts/posix/workflow-status.sh` to inspect `.beads/workflow/`, the shared control plane, and the shared live Beads store. Use `scripts/windows/agent-mail.ps1` or `scripts/posix/agent-mail.sh` for shared epic locks, reservations, and mailbox inspection. Use `scripts/windows/shared-beads.ps1` or `scripts/posix/shared-beads.sh` for live-store attachment, status, and snapshot export. `start-epic-worktree` remains available as a helper, but `swarm-epic` should normally handle that step.

## Issue Tracking With `br`

- Use `br` for all issue tracking
- Do not use markdown TODO files, TodoWrite, or alternate trackers
- `.beads/config.yaml` is committed to git and this template standardizes it with `no-db: false`
- The live Beads store is shared per clone in the clone-local path reported by `shared-beads status`
- Repo `.beads/issues.jsonl` is an explicit snapshot for Git sharing across machines

## Essential Commands

```bash
br ready --json
br show <id> --json
br create --title="Summary" --description="Details" --type=task|bug|feature|epic --priority=2
br update <id> --status=in_progress
br close <id> --reason="Completed"
br dep add <child-id> <parent-id>
```

Use one-bead status mutations only. If a `br update` or `br close` command errors, immediately verify the bead with `br show <id> --json` and inspect the live shared `issues.jsonl` path reported by `shared-beads status` before retrying.

## Session Protocol

```bash
git status
git add <files>
git commit -m "..."
```

## Notes

- Epics must use `--type=epic`
- Check `br ready` before asking what to work on next
- Different sessions may coordinate with Agent Mail across worktrees, but only the coordinator updates bead status during swarm execution
- Export the repo snapshot explicitly from the main checkout when you need Beads state committed for another machine
<!-- END TEMPLATE BR WORKFLOW -->
