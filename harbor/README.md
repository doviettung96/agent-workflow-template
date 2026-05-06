# Harbor

Harbor is a small Python runner that drives beads epics to completion by spawning one tmux pane per bead. It replaces the session-as-coordinator role of `swarm-epic`, so a long epic does not exhaust the chat session's context window. One process watches tmux, polls `br ready`, and writes the same `state.json` / `STATE.md` / Agent Mail surfaces the existing flow already uses — so it coexists with `swarm-epic` (the Agent Mail epic-lock arbitrates).

See `C:\Users\Admin\.claude\plans\the-current-workflow-has-cozy-harbor.md` for the design.

## Prerequisites

- Python 3.10+
- `tmux` on PATH (Git Bash / MSYS2 / WSL on Windows)
- `br` (the beads tracker) on PATH
- An agent CLI: `codex` or `claude`

## Install (editable, during development)

```bash
cd harbor
pip install -e .
```

## Status

Phase 1 (single-bead MVP) is in progress. See beads `awt-zmq.*` for the slice plan.
