# `.beads/` Layout

This template standardizes local-only `bd` with Dolt in server mode.

- `config.yaml`, `metadata.json`, `issues.jsonl`, and `dolt/` are live local runtime created by `bd init`
- `.gitignore`, `README.md`, and `PRIME.md` are the template-owned static files
- `workflow/` is checkout-local runtime for swarm coordination and handoff

Live Beads state is local to this clone and is not shared through Git.
