# New Repo Checklist

## Machine-Wide Once

- Install `bd`
- Install `dolt`
- Install Codex skills from `skills/`
- Install Codex prompts from `prompts/`
- If using Claude Code, run `bd setup claude` once and verify with `bd setup claude --check`

## Per Repo

1. `cd <repo>`
2. `bd init -p <prefix>`
3. `bd setup codex`
4. Copy `BEADS_WORKFLOW.md`
5. Copy `.codex/skills/build-and-test/SKILL.md`
6. Add the `AGENTS.md` snippet outside the Beads-managed block
7. Add the `CLAUDE.md` snippet if the repo uses Claude
8. Verify:
   - `bd setup codex --check`
   - `bd ready --json`

## Working Style

### Planner Session

1. Use `plan-beads` as the planner entry point
2. Use `brainstorming` if the problem is still fuzzy
3. Use `beads-planner` to break approved work into beads

### Executor Session

1. Use `executor-once` or `executor-loop`
2. Use `beads-claim` to start the executor cycle
3. Use `writing-plans` for the local execution plan
4. Implement
5. Use `systematic-debugging` if blocked
6. Use repo-local `build-and-test`
7. Use `requesting-code-review` or `verification-before-completion`
8. Use `beads-close` to finish cleanly
