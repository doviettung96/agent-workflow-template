# New Repo Checklist

## Machine Setup

- Install `br`
- Install `git`
- Install Python 3 for Agent Mail

## Repo Setup

1. `git init` or clone the repo
2. `br init --prefix <prefix>`
3. Run the template bootstrap script
4. Verify:
   - `br version`
   - `br ready --json`
   - `scripts/windows/shared-beads.ps1 status` or `scripts/posix/shared-beads.sh status`
   - `scripts/windows/workflow-status.ps1` or `scripts/posix/workflow-status.sh`

## Expected Files

- `.beads/config.yaml` with `no-db: false`
- `.beads/redirect`
- `.beads/PRIME.md`
- `.beads/workflow/`
- `BEADS_WORKFLOW.md`
- `.codex/skills/`
- `.claude/skills/`
- `scripts/windows/agent-mail.ps1` or `scripts/posix/agent-mail.sh`
- `scripts/windows/shared-beads.ps1` or `scripts/posix/shared-beads.sh`
- `scripts/windows/start-epic-worktree.ps1` or `scripts/posix/start-epic-worktree.sh`
- managed blocks in `AGENTS.md` and `CLAUDE.md`

## Existing `bd` Repo

If the repo already has `bd` state, run the downstream migration script instead of reinitializing it manually.
