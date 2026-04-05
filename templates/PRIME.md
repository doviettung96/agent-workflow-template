# Beads Workflow Context

> **Context Recovery**: start from `br ready`, `br list --status=in_progress`, and `br show <id>`

# SESSION CLOSE PROTOCOL

**Before saying work is complete, run this checklist:**

```bash
[ ] 1. git status
[ ] 2. git add <files>
[ ] 3. git commit -m "..."
```

Work happens on feature branches. Merging to `main` is done via PR, not local merge.

## Core Rules

- Default: use `br` for all issue tracking
- Prohibited: do not use TodoWrite, TaskCreate, or markdown files for task tracking
- Workflow: create a bead before writing code when the task is non-trivial, mark it `in_progress` when starting
- Bead threshold: if a task is expected to take more than 5 minutes, create a bead instead of doing it inline
- Always group batches of related work under an epic
- Session management: check `br ready` for available work
- Repo standard: `.beads/config.yaml` uses `no-db: false`, so normal `br` mutations use the shared live Beads store and you flush that live JSONL before commit or handoff

## Essential Commands

### Finding Work

- `br ready`
- `br list --status=open`
- `br list --status=in_progress`
- `br show <id>`

### Creating and Updating

- `br create --title="Summary" --description="Details" --type=task|bug|feature|epic --priority=2`
- Epics must use `--type=epic`
- `br update <id> --status=in_progress`
- `br update <id> --title/--description/--notes/--design`
- `br close <id>`
- `br close <id> --reason="explanation"`

### Dependencies and Blocking

- `br dep add <issue> <depends-on>`
- `br blocked`

### Project Health

- `br stats`
- `br search <query>`

## Common Workflows

**Starting work**

```bash
br ready
br show <id>
br update <id> --status=in_progress
```

**Completing work**

```bash
br close <id>
git add <files>
git commit -m "..."
```

Perform bead-status mutations one bead at a time. If a `br update` or `br close` command errors, immediately verify the bead with `br show <id> --json` and inspect the live shared `issues.jsonl` path reported by `shared-beads status` before retrying.

For persistent worktree-local `br` mutation failures after verification, see `docs/TROUBLESHOOTING.md`.

When you want the latest Beads state to travel by Git to another machine, export the tracked snapshot explicitly from the main checkout:

```bash
./scripts/posix/shared-beads.sh export-snapshot
```

**Creating dependent work**

```bash
br create --title="Implement feature X" --description="Details" --type=feature
br create --title="Write tests for X" --description="Details" --type=task
br dep add proj-yyy proj-xxx
```
