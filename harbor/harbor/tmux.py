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


@dataclass(frozen=True)
class Tmux:
    """Bound to one tmux server name (default `harbor`)."""

    server: str = DEFAULT_SERVER

    def _run(self, *args: str, check: bool = True, capture: bool = True) -> subprocess.CompletedProcess[str]:
        argv = ["tmux", "-L", self.server, *args]
        cp = subprocess.run(
            argv,
            check=False,
            capture_output=capture,
            text=True,
        )
        if check and cp.returncode != 0:
            raise TmuxError(argv, cp.returncode, cp.stdout or "", cp.stderr or "")
        return cp

    # ---- session lifecycle ----

    def has_session(self, session: str) -> bool:
        cp = self._run("has-session", "-t", session, check=False)
        return cp.returncode == 0

    def ensure_session(self, session: str, cwd: str) -> None:
        """Create a detached session if it does not already exist (idempotent)."""
        if self.has_session(session):
            return
        self._run("new-session", "-d", "-A", "-s", session, "-c", cwd)

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
        self._run("kill-window", "-t", f"{session}:{window}", check=False)

    # ---- pane I/O ----

    def send_keys(self, session: str, window: str, keys: str, *, enter: bool = True) -> None:
        argv = ["send-keys", "-t", f"{session}:{window}", keys]
        if enter:
            argv.append("Enter")
        self._run(*argv)

    def capture_pane(self, session: str, window: str, lines: int = 200) -> str:
        cp = self._run(
            "capture-pane",
            "-t",
            f"{session}:{window}",
            "-p",
            "-S",
            f"-{lines}",
        )
        return cp.stdout

    # ---- attach hint ----

    def attach_command(self, session: str, window: str | None = None) -> str:
        """The exact command a user can paste into a terminal to attach."""
        target = session if window is None else f"{session}:{window}"
        return f"tmux -L {shlex.quote(self.server)} attach -t {shlex.quote(target)}"
