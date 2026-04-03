# Beads Workflow Context

> **Context Recovery**: start from `br ready`, `br list --status=in_progress`, and `br show <id>`

# SESSION CLOSE PROTOCOL

**Before saying work is complete, run this checklist:**

```bash
[ ] 1. git status
[ ] 2. git add <files> .beads/
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
- Repo standard: `.beads/config.yaml` uses `no-db: true`, so normal `br` mutations update the repo-shared JSONL directly

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
- `br close <id1> <id2> ...`
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
br close <id1> <id2> ...
git add <files> .beads/
git commit -m "..."
```

**Creating dependent work**

```bash
br create --title="Implement feature X" --description="Details" --type=feature
br create --title="Write tests for X" --description="Details" --type=task
br dep add proj-yyy proj-xxx
```
