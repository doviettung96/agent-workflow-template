# `.beads/` Layout

This template standardizes local-only `bd` with Dolt in server mode.

- `config.yaml`, `metadata.json`, `issues.jsonl`, and `dolt/` are live local runtime created by `bd init`
- `.gitignore`, `README.md`, and `PRIME.md` are the template-owned static files
- `workflow/` is per-worktree runtime for swarm coordination and handoff
- `redirect` is created automatically in worktrees by `bd worktree create`

Live Beads state is local to this clone and is not shared through Git. Use `bd worktree create` so every worktree points back to the main checkout's `.beads` database.
