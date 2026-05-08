"""Subprocess wrapper for the `br` CLI used by the daemon and the runner.

We deliberately stay thin: `br` is the source of truth for bead state, harbor
just shells out and parses the JSON it returns.

Note: every command runs with `--no-db` to keep the JSONL the canonical store
(see `templates/BEADS_WORKFLOW.md`). The daemon uses these wrappers, not the
worker — workers must not mutate bead state.

Concurrency note (awt-zmq.107): `br update`/`br close` write the
`.beads/issues.jsonl` non-atomically. When N worker threads call them at
once — typical for a parallel epic run — we observed lost writes (Run 2 of
the Phase 2 smoke saw 2-of-3 closes land in JSONL even though all three
exited 0). Until br fixes its own concurrency, the harbor side defends
itself with a process-wide `_WRITE_LOCK` that serializes every write
invocation. Reads (`info`, `show`, `ready`) are unaffected.
"""
from __future__ import annotations

import json
import subprocess
import threading
from dataclasses import dataclass
from typing import Any

# Serializes all `br` write invocations across this process. See module
# docstring for the underlying race. Acquired by `update_status`, `close`,
# and any future write helpers.
_WRITE_LOCK = threading.Lock()


class BeadsError(RuntimeError):
    """Raised when a `br` invocation fails."""

    def __init__(self, argv: list[str], returncode: int, stdout: str, stderr: str):
        super().__init__(
            f"br exited {returncode}: argv={argv!r} stderr={stderr.strip()!r}"
        )
        self.argv = argv
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


@dataclass(frozen=True)
class Beads:
    """All commands shell out to `br`."""

    binary: str = "br"

    def _run(self, *args: str) -> str:
        argv = [self.binary, *args]
        # encoding="utf-8" + errors="replace" defends against Windows cp1252
        # decode errors when br output contains non-ASCII (em-dashes etc).
        cp = subprocess.run(
            argv, capture_output=True, text=True, check=False,
            encoding="utf-8", errors="replace",
        )
        if cp.returncode != 0:
            raise BeadsError(argv, cp.returncode, cp.stdout or "", cp.stderr or "")
        return cp.stdout

    # ---- read ----

    def info(self) -> dict[str, Any]:
        out = self._run("info", "--json", "--no-db")
        return json.loads(out)

    def show(self, bead_id: str) -> dict[str, Any]:
        out = self._run("show", bead_id, "--json", "--no-db")
        data = json.loads(out)
        # `br show --json` returns a JSON array even for a single id.
        if isinstance(data, list):
            if not data:
                raise BeadsError(["br", "show", bead_id], 0, out, "br show returned empty list")
            return data[0]
        return data

    def list_in_progress(self) -> list[dict[str, Any]]:
        """Return all in_progress beads (any prefix). Used by the webview to
        surface beads stuck in_progress without a live worker — typically the
        residue of a failed harbor run that crashed before completion."""
        out = self._run(
            "list", "--status", "in_progress", "--json", "--no-db", "--limit", "200"
        )
        out = out.strip()
        if not out:
            return []
        data = json.loads(out)
        if isinstance(data, dict) and "issues" in data:
            return list(data["issues"])
        if isinstance(data, list):
            return data
        return []

    def ready(self, parent: str | None = None) -> list[dict[str, Any]]:
        args = ["ready", "--json", "--no-db"]
        if parent is not None:
            args += ["--parent", parent]
        out = self._run(*args)
        out = out.strip()
        if not out:
            return []
        data = json.loads(out)
        # `br ready --json` returns a list directly.
        if isinstance(data, list):
            return data
        # Fallback in case the CLI wraps it (`{"issues": [...]}`).
        if isinstance(data, dict) and "issues" in data:
            return list(data["issues"])
        return []

    # ---- write ----

    def update_status(self, bead_id: str, status: str) -> None:
        # Serialized via `_WRITE_LOCK` — see module docstring (awt-zmq.107).
        with _WRITE_LOCK:
            self._run("update", bead_id, "--status", status, "--no-db")

    def close(self, bead_id: str, reason: str | None = None) -> None:
        args = ["close", bead_id, "--no-db"]
        if reason:
            args += ["--reason", reason]
        # Serialized via `_WRITE_LOCK` — see module docstring (awt-zmq.107).
        with _WRITE_LOCK:
            self._run(*args)

    def close_batch(self, bead_ids: list[str], reason: str | None = None) -> None:
        """Close multiple beads in a single `br close <id1> <id2> ...` call.

        Faster than N sequential `close()` calls (one fork+exec instead of N)
        and bypasses the lock-induced serialization. Use this from places
        that already collect a batch of completed bead-ids — e.g. the epic
        reaper at end-of-tick — to avoid contending with worker threads
        still finishing other beads.

        No-op when `bead_ids` is empty.
        """
        if not bead_ids:
            return
        args = ["close", *bead_ids, "--no-db"]
        if reason:
            args += ["--reason", reason]
        with _WRITE_LOCK:
            self._run(*args)
