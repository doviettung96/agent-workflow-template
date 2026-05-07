"""Thin wrappers around `tmux -L harbor`.

Mirrors the pattern verified in agtx (D:\\Projects\\agtx\\src\\tmux\\operations.rs):
each call shells out to one tmux subcommand on a dedicated server name so we
never collide with the user's other tmux sessions.

All quoting uses shlex.quote so the wrappers behave the same under Git Bash on
Windows as under POSIX shells. tmux on Git Bash speaks the same protocol; only
the launcher (`sh -c`) needs to be present, which Git Bash provides.
"""
from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass
from typing import Sequence

DEFAULT_SERVER = "harbor"


class TmuxError(RuntimeError):
    """Raised when a tmux subprocess returns a non-zero exit code."""

    def __init__(self, argv: Sequence[str], returncode: int, stdout: str, stderr: str):
        super().__init__(
            f"tmux exited {returncode}: argv={list(argv)!r} stderr={stderr.strip()!r}"
        )
        self.argv = list(argv)
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


@dataclass
class Tmux:
    """Bound to one tmux server name (default `harbor`).

    `config_path`, when set and the server is being newly started, is passed via
    `tmux -L <server> -f <path>` so any `set-option` directives apply before
    the first session's default window is created. This is the clean way to
    pin `default-shell` on Windows psmux — `set-option` after `new-session` is
    too late to influence the auto-created window.
    """

    server: str = DEFAULT_SERVER
    config_path: str | None = None
    # Cached `tmux -V` detection — older psmux builds reported
    # "tmux v3.3.1 ... (tmux alternative)" and diverged from real tmux for
    # `kill-window` and `new-window`. Newer builds drop the marker but harbor
    # uses one-session-per-bead now so the divergences are mostly moot.
    _is_psmux_cache: bool | None = None

    def _run(self, *args: str, check: bool = True, capture: bool = True) -> subprocess.CompletedProcess[str]:
        argv = ["tmux", "-L", self.server]
        if self.config_path:
            argv += ["-f", self.config_path]
        argv += list(args)
        # `encoding="utf-8", errors="replace"` is critical on Windows: the
        # default subprocess text mode uses cp1252, which raises
        # UnicodeDecodeError the moment a captured pane contains a non-ASCII
        # byte (em-dash from a bead description, codex's "•" bullet, etc.).
        # Replace mode keeps the polling loop alive — at worst a glyph turns
        # into U+FFFD, which never matches the HARBOR-DONE sentinel format.
        cp = subprocess.run(
            argv,
            check=False,
            capture_output=capture,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if check and cp.returncode != 0:
            raise TmuxError(argv, cp.returncode, cp.stdout or "", cp.stderr or "")
        return cp

    def is_psmux(self) -> bool:
        """True iff the resident `tmux` is psmux (a Windows tmux-alike whose
        `kill-window -t <session>:<window>` is a silent no-op)."""
        if self._is_psmux_cache is not None:
            return self._is_psmux_cache
        try:
            cp = subprocess.run(
                ["tmux", "-V"], capture_output=True, text=True,
                encoding="utf-8", errors="replace", check=False,
            )
            out = (cp.stdout or "") + (cp.stderr or "")
        except (FileNotFoundError, OSError):
            out = ""
        self._is_psmux_cache = "(tmux alternative)" in out
        return self._is_psmux_cache

    # ---- session lifecycle ----

    def has_session(self, session: str) -> bool:
        cp = self._run("has-session", "-t", session, check=False)
        return cp.returncode == 0

    def ensure_session(self, session: str, cwd: str, *, default_shell: str | None = None) -> None:
        """Create a detached session if it does not already exist (idempotent).

        On psmux/Windows, the session's auto-created default window is the only
        addressable pane — `tmux send-keys -t <session>:<window>` is unreliable
        for non-active windows. Harbor therefore uses one session per bead and
        targets `-t <session>:` (the active window) for all driving operations.

        `default_shell`, if provided, is applied two ways for safety:
          1. Server config file (`-f`) — picked up at server start, so the
             very first session's default window already uses `default_shell`.
          2. `set-option -t <session> default-shell` — set after creation as a
             fallback for cases where the server already exists.
        """
        if self.has_session(session):
            return
        self._run("new-session", "-d", "-A", "-s", session, "-c", cwd)
        if default_shell:
            self._run("set-option", "-t", session, "default-shell", default_shell, check=False)

    def kill_session(self, session: str) -> None:
        self._run("kill-session", "-t", session, check=False)

    # ---- windows / panes ----

    def new_window(self, session: str, window: str, cwd: str, command: str) -> None:
        """Open a new window in `session` named `window` and start `command`.

        Implementation note: we open the window WITHOUT a command, then use
        `send-keys` to type the command into the pane's default shell. This
        works on both real tmux 3.x and on Windows `psmux` (a tmux-alike whose
        `new-window` does not accept a command argument). The trade-off is a
        brief flicker of the default shell prompt before the command runs.

        On Windows the default shell is typically `powershell`; on POSIX it is
        whatever the user's tmux config says. `command` should therefore be
        invocable in either — `harbor-bead-runner <args>` is a console_script
        entry point installed by `pip install -e harbor/`, so PATH-resolution
        works the same in both shells.
        """
        self._run(
            "new-window",
            "-d",
            "-t",
            f"{session}:",
            "-n",
            window,
            "-c",
            cwd,
        )
        if command:
            self.send_keys(session, window, command)

    def window_exists(self, session: str, window: str) -> bool:
        try:
            cp = self._run(
                "list-windows",
                "-t",
                session,
                "-F",
                "#{window_name}",
                check=False,
            )
        except TmuxError:
            return False
        if cp.returncode != 0:
            return False
        names = [line.strip() for line in cp.stdout.splitlines() if line.strip()]
        return window in names

    def list_windows(self, session: str) -> list[tuple[str, str]]:
        """Return [(window_name, window_id), ...] for the session.

        Empty list if the session does not exist.
        """
        cp = self._run(
            "list-windows",
            "-t",
            session,
            "-F",
            "#{window_name}|#{window_id}",
            check=False,
        )
        if cp.returncode != 0:
            return []
        out: list[tuple[str, str]] = []
        for line in cp.stdout.splitlines():
            line = line.strip()
            if not line or "|" not in line:
                continue
            name, wid = line.split("|", 1)
            out.append((name, wid))
        return out

    def kill_window(self, session: str, window: str) -> None:
        """Kill the named window. On real tmux, `-t <session>:<window>` works
        directly. psmux (Windows) ignores `-t` on kill-window and only kills the
        currently-selected window — so we select the target first, then kill
        without `-t`. Tracked at awt-zmq.12."""
        if self.is_psmux():
            # `select-window -t` IS supported on psmux. Once it's selected,
            # `kill-window` (no -t) closes that one specifically.
            self._run("select-window", "-t", f"{session}:{window}", check=False)
            self._run("kill-window", check=False)
            return
        self._run("kill-window", "-t", f"{session}:{window}", check=False)

    # ---- pane I/O ----

    @staticmethod
    def _target(session: str, window: str = "") -> str:
        """Build a tmux target string. Empty `window` produces `<session>:` —
        which targets the session's currently-active window, the only form
        psmux respects reliably."""
        if window:
            return f"{session}:{window}"
        return f"{session}:"

    def send_keys(self, session: str, window: str = "", keys: str = "", *, enter: bool = True) -> None:
        argv = ["send-keys", "-t", self._target(session, window), keys]
        if enter:
            argv.append("Enter")
        self._run(*argv)

    def send_keys_literal(self, session: str, window: str = "", text: str = "", *, enter: bool = True) -> None:
        """Paste literal text via `send-keys -l` (no key-name interpretation).

        Multi-line input is handled by sending each line literally, then a synthetic
        `Enter` between lines. This is necessary because `-l` passes characters
        verbatim — including raw `\\n` — and not all tmux variants translate that
        into a press of Enter inside an interactive REPL.
        """
        target = self._target(session, window)
        lines = text.splitlines() or [""]
        for i, line in enumerate(lines):
            if line:
                self._run("send-keys", "-t", target, "-l", line)
            if i < len(lines) - 1:
                self._run("send-keys", "-t", target, "Enter")
        if enter:
            self._run("send-keys", "-t", target, "Enter")

    def capture_pane(self, session: str, window: str = "", lines: int = 200) -> str:
        cp = self._run(
            "capture-pane",
            "-t",
            self._target(session, window),
            "-p",
            "-S",
            f"-{lines}",
        )
        return cp.stdout

    # ---- attach hint ----

    def attach_command(self, session: str, window: str | None = None) -> str:
        """The exact command a user can paste into a terminal to attach.

        With per-bead sessions, callers usually pass `window=None` so the user
        attaches to the session as a whole — the session has only one window.
        """
        target = session if not window else f"{session}:{window}"
        return f"tmux -L {shlex.quote(self.server)} attach -t {shlex.quote(target)}"
