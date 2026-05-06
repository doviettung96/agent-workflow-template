"""Library wrapper around `scripts/shared/agent_mail.py`.

We import the module directly (not via subprocess) so harbor can call into
Agent Mail as a Python library. The underlying module exposes `AgentMailStore`
plus a set of `command_*` functions that take an argparse-style namespace; we
synthesize those namespaces with `types.SimpleNamespace` to keep semantics
identical to the CLI.

Phase 1 only uses `register`, `reserve`, `release_reservations`, and `post`.
Phase 2 will add `acquire_epic` / `release_epic`. Behavior must stay identical
to the existing flow so swarm-epic and harbor produce the same Agent Mail
artifacts.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

_AGENT_MAIL_MODULE: ModuleType | None = None


def _load_agent_mail(repo_root: Path) -> ModuleType:
    """Lazy import of scripts/shared/agent_mail.py from the given repo root."""
    global _AGENT_MAIL_MODULE
    if _AGENT_MAIL_MODULE is not None:
        return _AGENT_MAIL_MODULE
    candidate = repo_root / "scripts" / "shared" / "agent_mail.py"
    if not candidate.exists():
        raise FileNotFoundError(
            f"agent_mail.py not found at {candidate} — harbor.mail requires the "
            f"shared script. Re-run scripts/{'windows' if sys.platform == 'win32' else 'posix'}/scaffold-repo-files."
        )
    spec = importlib.util.spec_from_file_location("agent_mail", candidate)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load agent_mail spec from {candidate}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["agent_mail"] = module
    spec.loader.exec_module(module)
    _AGENT_MAIL_MODULE = module
    return module


class Mail:
    """Bound to one repo root; constructs an AgentMailStore on demand."""

    def __init__(self, repo_root: str | Path):
        self.repo_root = Path(repo_root).resolve()
        self._mod = _load_agent_mail(self.repo_root)
        self._store = self._mod.AgentMailStore(self.repo_root)

    # ---- agent registration ----

    def register(
        self,
        *,
        name: str,
        role: str,
        epic_id: str | None = None,
        bead_id: str | None = None,
        status: str = "active",
        session_id: str | None = None,
    ) -> dict[str, Any]:
        ns = SimpleNamespace(
            name=name,
            role=role,
            epic_id=epic_id,
            bead_id=bead_id,
            status=status,
            session_id=session_id,
        )
        return self._mod.command_register(self._store, ns)

    def unregister(self, name: str) -> dict[str, Any]:
        return self._mod.command_unregister(self._store, SimpleNamespace(name=name))

    # ---- epic locks ----

    def acquire_epic(self, *, epic_id: str, owner: str, session_id: str | None = None) -> dict[str, Any]:
        ns = SimpleNamespace(epic_id=epic_id, owner=owner, session_id=session_id)
        return self._mod.command_acquire_epic(self._store, ns)

    def release_epic(self, *, epic_id: str, owner: str) -> dict[str, Any]:
        ns = SimpleNamespace(epic_id=epic_id, owner=owner)
        return self._mod.command_release_epic(self._store, ns)

    # ---- reservations ----

    def reserve(
        self,
        *,
        owner: str,
        paths: list[str],
        epic_id: str | None = None,
        bead_id: str | None = None,
    ) -> dict[str, Any]:
        ns = SimpleNamespace(owner=owner, path=list(paths), epic_id=epic_id, bead_id=bead_id)
        return self._mod.command_reserve(self._store, ns)

    def release_reservations(self, *, owner: str, bead_id: str | None = None) -> dict[str, Any]:
        ns = SimpleNamespace(owner=owner, bead_id=bead_id)
        return self._mod.command_release_reservations(self._store, ns)

    # ---- thread messages ----

    def post(
        self,
        *,
        thread: str,
        sender: str,
        body: str,
        message_type: str | None = None,
        to: str | None = None,
        epic_id: str | None = None,
        bead_id: str | None = None,
    ) -> dict[str, Any]:
        ns = SimpleNamespace(
            thread=thread,
            sender=sender,
            to=to,
            body=body,
            message_type=message_type,
            epic_id=epic_id,
            bead_id=bead_id,
        )
        return self._mod.command_post(self._store, ns)
