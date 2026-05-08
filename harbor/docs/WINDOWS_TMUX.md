# Windows tmux for harbor

Harbor drives an interactive REPL through a tmux server (`tmux -L harbor`).
Two parts of the loop need a working tmux:

- **Drive (write-only)**: `new-session`, `send-keys`, `capture-pane`, `kill-session`.
  Harbor uses these in subprocesses and never opens an interactive client.
- **Recover (interactive)**: when an agent emits `HARBOR-DONE: ... status=blocked`,
  harbor leaves the pane alive and prints a `tmux -L harbor attach -t <session>`
  hint so a human can attach from another terminal and finish the conversation.

The first part works on every tmux variant. The second is where Windows tmux
ports diverge — `attach-session` is the most pty-sensitive subcommand, and
not every port implements it correctly.

## The bug we hit on `marlocarlo.psmux` 3.3.1

On this machine (`marlocarlo.psmux 3.3.1`, installed via `winget`) attach is
broken:

```bash
$ tmux -L test new-session -d -s ctl
$ tmux -L test list-sessions
ctl: 1 windows (created Fri May  8 ...)
$ tmux -L test attach -t ctl
psmux: can't find session 'ctl' (no server running)
```

The session exists (`list-sessions` confirms it, `list-clients` even shows a
client at `/dev/pts/0`), and yet `attach` from the same shell reports the
server is gone. Reproducible from any shell on this host. Saved evidence:
[`feedback_psmux_attach_bug.md`](#) in the per-account memory store.

This kills harbor's documented recovery flow on Windows. The send-keys relay
still works for write-only nudges, and the webview's pane capture still works
for read-only observation, but the human cannot get a real interactive REPL
back without a working `attach`.

## Variants tried

| Tool | Version | `attach` works? | Notes |
|------|---------|-----------------|-------|
| `marlocarlo.psmux` | 3.3.1 | ❌ | The bug above. Reproducible with a one-shell control test. |
| `marlocarlo.psmux` | 3.3.4 | unverified | Newer point release; attach behavior not separately confirmed. Upstream changelog does not call out the attach fix. |
| `arndawg.tmux-windows` | 3.6a-win32.7 | ✅ (recommended) | Native Windows port of upstream tmux 3.6a. Uses ConPTY for the pty layer and Windows Named Pipes for IPC. Supports detach/reattach. Recent release notes explicitly cover SSH session survival (`CREATE_BREAKAWAY_FROM_JOB`), which is the same OS-level mechanism that affects local attach. |
| Cygwin tmux | varies | ✅ (in theory) | Real tmux compiled for Cygwin. Heavy install (full Cygwin runtime). Not pursued — `arndawg.tmux-windows` covers the same need without the Cygwin tax. |
| MSYS2 tmux | varies | ✅ (in theory) | Same story as Cygwin. Heavy install. Not pursued. |
| WSL tmux | n/a | ❌ on this host | WSL2 is unsupported here (`Virtual Machine Platform` disabled in BIOS). Not portable as a "harbor on Windows" baseline. |

## Chosen path: `arndawg.tmux-windows`

`arndawg.tmux-windows` is a native Windows port of upstream tmux 3.6a. It
implements the same CLI grammar harbor already uses (`-L`, `new-session -d`,
`send-keys`, `capture-pane`, `kill-session`, `kill-window`, `select-window`,
`new-window`, `list-windows`, `set-option`), and it implements `attach`
correctly because it uses ConPTY end-to-end.

Trade-offs versus alternatives:

- **vs psmux**: real tmux semantics. Harbor's psmux-divergence branches in
  `harbor/harbor/tmux.py` (`is_psmux()`, the kill-window workaround, the
  no-arg `new-window` workaround) become dormant — the `(tmux alternative)`
  marker is absent in `tmux -V` for this port. Existing tests still pass
  because the divergent branches are only triggered when the marker is
  present.
- **vs Cygwin/MSYS2**: no extra runtime to install. Single-binary portable
  zip from winget.
- **vs WSL**: works on hosts where virtualization is not available.

### Install

```powershell
winget install arndawg.tmux-windows
```

**Restart your shell after install.** WinGet's portable installer prints
`Path environment variable modified; restart your shell to use the new
value.` — the shim is added to the User-level `PATH` and existing shells
do not pick it up automatically.

After restart, verify the resident `tmux.exe` resolves to the new port:

```powershell
tmux -V
# expected: tmux 3.6a-win32  (note: NO "(tmux alternative)" marker)
(Get-Command tmux).Path
# expected: ...\WinGet\Packages\arndawg.tmux-windows_..._8wekyb3d8bbwe\tmux.exe
```

```bash
# from Git Bash:
tmux -V
where.exe tmux
```

How the two installs coexist: arndawg's portable install adds its package
directory directly to User `PATH` and removes `tmux.exe` from
`%LOCALAPPDATA%\Microsoft\WinGet\Links\` (where psmux's WinGet shim lives).
psmux's other aliases (`pmux.exe`, `psmux.exe`) stay in `Links\`, so
`psmux` is still reachable by name if you ever need to compare behavior.
If `tmux -V` still reports `psmux` after a shell restart, psmux's `Links\
tmux.exe` shim was reinstalled later and now precedes arndawg in `PATH`
order — fix with `winget uninstall marlocarlo.psmux` (you can keep the
psmux package installed and just drop the conflicting shim by
re-running `winget install --force arndawg.tmux-windows`).

### Verify the attach bug is fixed

Same control test that reproduced the psmux bug:

```bash
$ tmux -L test kill-server
$ tmux -L test new-session -d -s ctl
$ tmux -L test list-sessions
ctl: 1 windows (created ...)
$ tmux -L test attach -t ctl
# expected: an interactive pane attached to the `ctl` session.
# Press Ctrl-b then d to detach. `list-sessions` should still show `ctl`.
```

Verified on this host (2026-05-08, awt-zmq.110): after
`winget install arndawg.tmux-windows`, `tmux -V` reports
`tmux 3.6a-win32`, the control test attaches to `ctl` and shows the
live cmd.exe banner with the tmux status bar updating its clock in
real time, and all 169 harbor tests still pass with the new tmux on
`PATH`.

### Verify the harbor end-to-end loop

```bash
# 1. start any harbor bead so a session named harbor-<digest>-<id> exists
harbor run-bead awt-zmq.<some-id> --profile codex
# 2. while the bead is running, attach from a fresh Git Bash:
tmux -L harbor list-sessions
tmux -L harbor attach -t harbor-<digest>-<id>
# 3. you should land in the live codex REPL. Type a message, press Enter,
#    codex responds. Press Ctrl-b d to detach without killing the pane.
```

## arndawg.tmux-windows quirks discovered in use

One CLI divergence from upstream tmux turned up after we shipped the
install (awt-zmq.112 incident, 2026-05-09):

- **`new-session -c <cwd>` always fails** with `create window failed:
  spawn failed`, regardless of cwd value (forward-slash, backslash, simple
  path, path with spaces, anything). Reproduced with a one-shell control
  test:

  ```bash
  $ tmux -L test new-session -d -A -s s1 -c 'D:/'
  create window failed: spawn failed
  ```

  Without `-c`, the session creates fine. So the workaround is: drop
  `-c <cwd>` from `harbor.tmux.ensure_session`'s argv and instead
  `cd <cwd>` via `send-keys` immediately after creation. That works on
  every tmux variant we target — `cd` is a builtin in Git Bash,
  PowerShell, cmd.exe, and any POSIX shell. See `harbor/harbor/tmux.py`'s
  `ensure_session` for the implementation.

  The behavior on real tmux 3.x is `-c <cwd>` works as documented; on
  arndawg it does not. We don't conditionally branch — the universal
  `cd` workaround is correct on every platform.

## Harbor code consequences

For the investigation step, no harbor code needs to change:

- `harbor/harbor/tmux.py` — `is_psmux()` already keys off the
  `(tmux alternative)` marker in `tmux -V`. With `arndawg.tmux-windows`
  resident, the marker is absent, so `is_psmux()` returns `False` and the
  divergent code paths (psmux-only `kill-window` workaround) become dormant
  but harmless. The cached value is fine — harbor processes are short-lived.
- `harbor/harbor/orchestrator.py` — the `pane left alive at: ...` recovery
  hint already prints the same `tmux -L harbor attach -t <session>` command
  string. With a working `attach`, the printed hint becomes actionable
  without any code change.

A follow-up bead (filed as a child of `awt-zmq.110`) covers any
defensive hardening we want — for example, a startup check that warns the
operator when `is_psmux()` is true, pointing at this document.

## Out of scope

- **Webview-embedded terminal (xterm.js + websocket bridge over send-keys /
  capture-pane).** A bigger feature; track separately if we ever decide
  attach is not enough (e.g. for multi-user observability).
- **Refactoring harbor to skip tmux entirely** (raw ConPTY in the harbor
  process). Way out of scope for this bead.

## Rejected alternatives

- **Configure psmux to keep the server alive (`destroy-unattached off`,
  etc.)**: `destroy-unattached` is already `off` by default on psmux 3.3.1
  on this host (verified via `show-options -g`), and `list-sessions` and
  `list-clients` confirm the server IS alive between subprocess
  invocations. The bug is in psmux's `attach-session` client-side code path
  itself, not in server lifecycle. No config tweak makes attach work.
- **Switch harbor to a foreground tmux session that the user starts ahead
  of time and harbor `new-window`s into.** Forces a user-facing setup step
  before every harbor run, regresses the "one bead, one session" model
  introduced for psmux divergence reasons (awt-zmq.106 / .12), and still
  needs a working `attach` to recover from `blocked` sentinels. Strictly
  worse than fixing the resident tmux.
- **Drop `attach` from harbor's recovery flow and rely entirely on the
  webview pane capture + send-keys relay.** Working today as a fallback,
  but a chat box in the webview is its own non-trivial feature (input
  echo, multi-line, terminal escape passthrough), and the relay text
  carries the never-include-`HARBOR-DONE` footgun documented in
  `feedback_harbor_relay_pitfalls.md`. The right place for that work is a
  separate bead if/when we want it; the existing tmux attach contract is
  the cheaper local minimum.
