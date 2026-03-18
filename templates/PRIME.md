# Beads Workflow Context

> **Context Recovery**: Run `bd prime` after compaction, clear, or new session
> Hooks auto-call this in Claude Code when .beads/ detected

# SESSION CLOSE PROTOCOL

**CRITICAL**: Before saying "done" or "complete", you MUST run this checklist:

```
[ ] 1. git status              (check what changed)
[ ] 2. git add <files>         (stage code changes)
[ ] 3. git commit -m "..."     (commit code changes)
```

**Note:** Work happens on feature branches. Merging to main is done via PR, not local merge. Beads state is shared via the main repo's `.beads/` directory (auto-discovered by `bd` in git worktrees).

## Core Rules
- **Default**: Use beads for ALL task tracking (`bd create`, `bd ready`, `bd close`)
- **Prohibited**: Do NOT use TodoWrite, TaskCreate, or markdown files for task tracking
- **Workflow**: Create beads issue BEFORE writing code, mark in_progress when starting
- **Memory**: Use `bd remember "insight"` for persistent knowledge across sessions. Do NOT use MEMORY.md files — they fragment across accounts. Search with `bd memories <keyword>`.
- **Worktrees**: Use `git worktree add`, NOT Claude's `EnterWorktree` or Codex built-in worktree features
- **No dolt remote**: Do NOT run `bd dolt pull` or `bd dolt push` — beads state is tracked by git, not Dolt remotes
- Session management: check `bd ready` for available work

## Essential Commands

### Finding Work
- `bd ready` - Show issues ready to work (no blockers)
- `bd list --status=open` - All open issues
- `bd list --status=in_progress` - Your active work
- `bd show <id>` - Detailed issue view with dependencies

### Creating & Updating
- `bd create --title="Summary" --description="Details" --type=task|bug|feature --priority=2` - New issue
  - Priority: 0-4 or P0-P4 (0=critical, 2=medium, 4=backlog). NOT "high"/"medium"/"low"
- `bd update <id> --status=in_progress` - Claim work
- `bd update <id> --title/--description/--notes/--design` - Update fields inline
- `bd close <id>` - Mark complete
- `bd close <id1> <id2> ...` - Close multiple issues at once
- `bd close <id> --reason="explanation"` - Close with reason
- **WARNING**: Do NOT use `bd edit` - it opens $EDITOR which blocks agents

### Dependencies & Blocking
- `bd dep add <issue> <depends-on>` - Add dependency
- `bd blocked` - Show all blocked issues

### Project Health
- `bd stats` - Project statistics
- `bd search <query>` - Search issues by keyword

## Common Workflows

**Starting work:**
```bash
bd ready           # Find available work
bd show <id>       # Review issue details
bd update <id> --status=in_progress  # Claim it
```

**Completing work:**
```bash
bd close <id1> <id2> ...    # Close all completed issues at once
git add . && git commit -m "..."  # Commit your changes
```

**Creating dependent work:**
```bash
bd create --title="Implement feature X" --description="Details" --type=feature
bd create --title="Write tests for X" --description="Details" --type=task
bd dep add beads-yyy beads-xxx  # Tests depend on Feature
```
