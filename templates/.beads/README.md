# `.beads/` Layout

This template standardizes local-only `bd` with Dolt in server mode.

- `config.yaml`, `metadata.json`, `issues.jsonl`, and `dolt/` are live local runtime created by `bd init`
- `.gitignore`, `README.md`, and `PRIME.md` are the template-owned static files
- `workflow/` is checkout-local runtime for swarm coordination, handoff, and optional target-runtime selection
- `workflow/runtime-target.json` selects local execution by default and may be customized per checkout for SSH execution

Live Beads state is local to this clone and is not shared through Git.
