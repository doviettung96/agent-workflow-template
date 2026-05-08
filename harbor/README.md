# Harbor

Harbor is a small Python runner that drives beads epics to completion by spawning one tmux pane per bead. It replaces the session-as-coordinator role of `swarm-epic`, so a long epic does not exhaust the chat session's context window. One process watches tmux, polls `br ready`, and writes the same `state.json` / `STATE.md` / Agent Mail surfaces the existing flow already uses — so it coexists with `swarm-epic` (the Agent Mail epic-lock arbitrates).

See `C:\Users\Admin\.claude\plans\the-current-workflow-has-cozy-harbor.md` for the design.

## Prerequisites

- Python 3.10+
- `tmux` on PATH — macOS/Linux: stock `brew install tmux` / `apt install tmux`. Windows: see [`docs/WINDOWS_TMUX.md`](docs/WINDOWS_TMUX.md) (`marlocarlo.psmux` has a broken `attach`; install `arndawg.tmux-windows` instead).
- `br` (the beads tracker) on PATH
- An agent CLI: `codex` or `claude`
- One shared editable install from the workflow template checkout

## Install

Install Harbor once from the template checkout:

```bash
python -m pip install -e <template>/harbor
```

That install exposes `harbor` on PATH for every project directory and keeps
all downstream repos on the current template Harbor code without copying
`harbor/` into each repo. Verify from any repo root:

```bash
harbor --help
```

`harbor.yml` is optional. If a repo does not provide one, Harbor uses its
built-in defaults; add `harbor.yml` only when a project needs local overrides.

## Status

Phase 1 (single-bead MVP) is in progress. See beads `awt-zmq.*` for the slice plan.
