<!-- BEGIN TEMPLATE BR WORKFLOW -->
## Workflow Guide

Use `BEADS_WORKFLOW.md` for the current planner, worker-backed executor, manual compatibility executor, and swarm executor flow. All workflow skills are repo-local: Codex skills live under `.codex/skills/`, Claude skills under `.claude/skills/`.

Preferred entry points are `plan-beads`, `swarm-epic`, and `executor-once`. Use `planner-research` only inside a planner session when `brainstorming` still leaves material factual uncertainty. Treat `executor-loop` and `executor-loop-epic` as compatibility paths, not the default for long epic execution.

Use `start-epic-worktree` only when you truly want a parallel epic in its own checkout. It prepares a Git worktree and hydrates the local-only workflow files there. Then run `swarm-epic` inside that worktree.

The executor test skill lives at `.codex/skills/build-and-test/SKILL.md`; use it between implementation and final verification.

Use `scripts/windows/workflow-status.ps1` or `scripts/posix/workflow-status.sh` to inspect `.beads/workflow/`, the shared control plane, and Beads backend state. Use `scripts/windows/agent-mail.ps1` or `scripts/posix/agent-mail.sh` for shared epic locks, reservations, and mailbox inspection.
Workflow scaffold files such as `AGENTS.md`, `CLAUDE.md`, `BEADS_WORKFLOW.md`, `docs/plans/`, and `.codex/.claude` skills stay local-only in downstream Git. Mirror them to the backup repo with `scripts/windows/sync-workflow-backup.ps1` or `scripts/posix/sync-workflow-backup.sh` before opening a PR.

Keep repo exploration local. If `.beads/workflow/runtime-target.json` selects SSH, route build, test, run, deploy, migration, or other project-execution commands through `scripts/shared/target_runtime.py` or the repo-local `target-runtime-exec` skill instead of assuming the local machine.

## Planning And Execution Policy

- `AGENTS.md` is the canonical instruction file for repo policy; keep other assistant-specific files as thin references back to this file
- present implementation options during planning time, not during execution after work has already started
- once the user approves one option, implement only that option
- do not silently switch to a fallback, backup plan, or alternate implementation path
- if the chosen option fails or proves non-viable, stop, explain the failure, and discuss new options before continuing

## Issue Tracking With `br`

- Use `br --no-db` for all issue tracking
- Do not use markdown TODO files, TodoWrite, or alternate trackers
- Live `.beads` state is local-only and should not be committed
- Run one top-level epic executor session at a time in a checkout
- Epic execution can run on the current feature branch; it does not require branch `epic/<epic-id>` or a clean worktree
- If epic execution starts on `main`, create a generic temporary branch such as `feat/work-<timestamp>` first; if already on any non-`main` branch, do not switch branches

## Essential Commands

```bash
br ready --json --no-db
br show <id> --json --no-db
br create --title="Summary" --description="Details" --type=task|bug|feature|epic --priority=2 --no-db
br update <id> --status=in_progress --no-db
br close <id> --reason="Completed" --no-db
br dep add <child-id> <parent-id> --type parent-child --no-db
git status --short
git switch -c "feat/work-<timestamp>"
git add -p
git commit -m "<epic-id>: <description>"
```

## Notes

- Epics must use `--type=epic`
- Check `br ready --no-db` before asking what to work on next
- `swarm-epic` may coordinate workers inside one epic, but only the coordinator updates bead status during swarm execution
- Commits for one epic must start with the exact subject prefix `<epic-id>:` so `finishing-a-development-branch <epic-id>` can cherry-pick the epic slice from a mixed temporary branch
- Use explicit path staging or `git add -p` when files contain unrelated dirty work
- Worker-ready beads must be fresh-session-safe: a fresh worker should be able to execute from the bead contract, persisted inputs, and local code inspection without replaying prior chat
- If the current checkout cannot open the Beads workspace, inspect `br where --no-db` and run `br init --prefix <prefix> --no-db` before continuing
<!-- END TEMPLATE BR WORKFLOW -->
