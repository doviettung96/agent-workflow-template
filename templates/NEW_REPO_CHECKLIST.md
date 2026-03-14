# New Repo Checklist

## Machine-Wide Once

- Install `bd`
- Install `dolt`
- Install Codex skills from `skills/`
- If using Claude Code, run `bd setup claude` once and verify with `bd setup claude --check`

## Per Repo

1. `cd <repo>`
2. `bd init -p <prefix>`
3. `bd setup codex`
4. Copy `BEADS_WORKFLOW.md`
5. Add the `AGENTS.md` snippet outside the Beads-managed block
6. Add the `CLAUDE.md` snippet if the repo uses Claude
7. Verify:
   - `bd setup codex --check`
   - `bd ready --json`

## Working Style

1. Use `brainstorming` if the problem is still fuzzy
2. Use `beads-planner` to break approved work into beads
3. Claim a bead
4. Use `writing-plans` for the local execution plan
5. Implement
6. Use `systematic-debugging` if blocked
7. Use `requesting-code-review` or `verification-before-completion`
8. Use `beads-task-cycle` to finish cleanly
