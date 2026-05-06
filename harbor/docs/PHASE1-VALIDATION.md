# Phase 1 — End-to-end validation

Phase 1 ships the single-bead MVP: `harbor run-bead <id>` opens a tmux window,
runs an agent CLI, parses the `HARBOR-DONE` sentinel, runs verify, and closes
the bead. This document captures how to validate it on a real Windows + Git
Bash machine.

## Prerequisites

- Python 3.10+ on PATH
- `tmux` on PATH (in a Git Bash / MSYS2 / WSL shell)
- `br` on PATH (the beads tracker bundled with this template)
- `codex` on PATH (or another agent CLI configured in `harbor.yml`)
- `pip install -e .` from `harbor/`

Quick prereq check:

```bash
python --version
tmux -V
br info --json --no-db
codex --version  # or whatever agent you configure
```

## Mock-agent smoke (no codex required)

Run this from Git Bash to exercise the full orchestrator without paying for an
agent. It uses a tiny fake agent that just echoes the sentinel.

```bash
cd /d/Projects/game-reverse/agent-workflow-template

# Override the 'balanced' profile to a fake-agent shell command for this run.
cat > harbor.yml <<'YAML'
default_profile: balanced
profiles:
  balanced:
    agent_kind: mock
    command: ["sh", "-c", "echo 'mock agent did the work'; echo 'HARBOR-DONE: __BEAD__ status=ok classification=none'"]
    args_template: []
    model: ""
    effort: ""
YAML

# Replace __BEAD__ with the bead id so the sentinel matches.
# (We rely on the test bead being trivially safe; create one first.)
br create "Harbor smoke (delete me)" --type task --description \
  $'Read:\n- README.md\n\nFiles:\n- harbor/SMOKE.md\n\nVerify:\n- echo verify-ok\n' \
  --no-db --silent
# capture the new id, e.g. awt-XXXX, then edit harbor.yml to replace __BEAD__

harbor run-bead <new-bead-id> --profile balanced
```

Expected: a tmux window appears, mock agent prints two lines, fallback file
gets written at `.beads/workflow/runner-finished/<bead>.json`, orchestrator
runs the `echo verify-ok` verify command (passes), `br close` succeeds, summary
printed.

## Real codex smoke

Replace the profile's `command` and `args_template` with the real codex
invocation (the built-in default works if `codex -m {model} --reasoning-effort
{effort}` is the right shape on your install). Then:

```bash
harbor run-bead awt-harbor-smoke --profile fast
```

Watch progress:

```bash
tmux -L harbor list-windows
tmux -L harbor attach -t harbor-<hash>:awt-harbor-smoke
```

(Detach with `Ctrl-b d`.)

## What "success" looks like

1. `tmux -L harbor list-windows` shows the bead's window appear within a few seconds.
2. The agent prints work + a final `HARBOR-DONE: <bead-id> status=ok classification=none` line.
3. `.beads/workflow/runner-finished/<bead-id>.json` is created by the runner wrapper.
4. The orchestrator runs the bead's `Verify:` commands, all pass.
5. `br show <bead-id>` reports `status=closed`.
6. `.beads/workflow/state.json` shows `runner.active=false` and the recent run in `harbor.db`.

## Known issues / quirks

- **Windows `br update --status` FK bug.** On the template's bundled Windows
  `br` build, `br update --status` fails with `FOREIGN KEY constraint
  failed`. The orchestrator continues anyway (logs a WARNING). `br close`
  works fine in observed runs, so the bead does end up closed. See
  `feedback_br_windows_fk_bug.md` in the agent's auto-memory.
- **`psmux` (the Windows winget tmux package) is NOT real tmux.** It's a
  PowerShell-based clone — `tmux 3.3.1 — Terminal multiplexer for Windows
  (tmux alternative)`. Two divergences mattered for harbor:
  1. `tmux new-window <command>` does NOT pass the command through. We
     always open the window without a command, then `send-keys` the command
     into the pane's default shell. (`harbor.tmux.new_window` does this.)
  2. The pane's default shell is `powershell` on this install. Whatever
     command we send-keys must be invocable from PowerShell —
     `harbor-bead-runner` works because it's a console_script entry point
     installed by `pip install -e harbor/`, so PATH-resolution is shell-
     agnostic.
  3. `subprocess.Popen(["sh", "-c", ...])` from inside a PowerShell pane
     fails with `WinError 2: file not found` because `sh.exe` isn't on
     PATH. Built-in profiles use the agent CLI directly (`codex`, `claude`)
     so this only bites home-grown mock profiles. If you write a custom
     profile, use `python -c '...'` or a path-resolved binary.
- **First-window quirk.** `tmux new-session -d -A -s <session>` on Windows
  Git Bash starts the bootstrap window with the user's default shell
  (powershell). That window is harmless — harbor's bead window is the one
  it cares about.
- **Sentinel must be on its own line.** The runner scans for `HARBOR-DONE:`
  at the start of a line. If the agent prefixes it with logging like
  `[INFO] HARBOR-DONE: ...`, the parser misses it. The skill spec at
  `skills/harbor-bead-worker/SKILL.md` instructs the agent to print the line
  verbatim with no prefix.

## Smoke results captured 2026-05-06

End-to-end run with a python-native mock agent (no codex needed):
- Created `awt-k91` (Files: `harbor/SMOKE-PROBE.txt`, Verify: `echo verify-ok`)
- `harbor run-bead awt-k91 --profile mock`
- tmux window appeared in `harbor-6ee962d1`
- Mock agent printed `HARBOR-DONE: awt-k91 status=ok classification=none`
- Orchestrator parsed sentinel, ran `echo verify-ok` (passed), called
  `br close awt-k91` (succeeded), wrote `state.json` + `STATE.md`
- Final summary printed `closed: True`
