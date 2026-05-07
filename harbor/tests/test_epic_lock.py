"""Agent Mail epic-lock tests (Phase 2.3).

Verifies harbor's epic-lock semantics:
  * `mail.acquire_epic(owner='harbor/<run-id>')` is called before the first tick.
  * `mail.release_epic(...)` is called in `finally` — on normal exit, on
    exception, and after early-exit when the lock is held.
  * If the lock is already held by another owner, run_epic refuses to do any
    work, prints the holder, and returns an exit_reason='lock_held' result.
  * The `cmd_run_epic` CLI wrapper maps lock_held -> exit code 2.

`Mail` is the only collaborator that needs a fake here; we leverage the
existing fall-through where `Beads` and `run_bead` are patched at the
harbor.epic level.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from harbor.epic import RunEpicOptions, run_epic
from harbor.orchestrator import RunBeadResult


def _ok_result(bead_id: str) -> RunBeadResult:
    return RunBeadResult(
        bead_id=bead_id, sentinel_status="ok", blocker_class="none",
        exit_code=0, verify=None, closed=True,
    )


class _FakeAgentMailError(Exception):
    """Stand-in for scripts.shared.agent_mail.AgentMailError. Has the `.details`
    attribute that command_acquire_epic populates with the existing lock dict."""

    def __init__(self, message: str, *, code: int = 10, details=None):
        super().__init__(message)
        self.code = code
        self.details = details


def _patch_epic_mail(mail_factory):
    return patch("harbor.epic.Mail", mail_factory)


def test_run_epic_acquires_and_releases_lock(tmp_path: Path):
    fake_mail = MagicMock()
    fake_beads = MagicMock()
    fake_beads.ready.side_effect = lambda parent=None: []

    with (
        _patch_epic_mail(MagicMock(return_value=fake_mail)),
        patch("harbor.epic.Beads", return_value=fake_beads),
        patch("harbor.epic.run_bead"),
    ):
        opts = RunEpicOptions(epic_id="awt-zmq", repo_root=tmp_path, skip_finalize=True)
        result = run_epic(opts, log=lambda *a, **k: None)

    assert result.exit_reason == "drained"
    fake_mail.acquire_epic.assert_called_once()
    acq_kwargs = fake_mail.acquire_epic.call_args.kwargs
    assert acq_kwargs["epic_id"] == "awt-zmq"
    assert acq_kwargs["owner"] == f"harbor/{result.run_id}"

    fake_mail.release_epic.assert_called_once()
    rel_kwargs = fake_mail.release_epic.call_args.kwargs
    assert rel_kwargs["epic_id"] == "awt-zmq"
    assert rel_kwargs["owner"] == f"harbor/{result.run_id}"


def test_run_epic_refuses_to_start_when_lock_held(tmp_path: Path):
    """When acquire_epic raises (held by another owner), run_epic must not
    enter the loop, must not spawn anything, and must return lock_held."""
    fake_mail = MagicMock()
    fake_mail.acquire_epic.side_effect = _FakeAgentMailError(
        "Epic awt-zmq is already locked by swarm-epic/sess-42",
        code=10,
        details={"owner": "swarm-epic/sess-42", "session_id": "sess-42"},
    )

    fake_beads = MagicMock()
    fake_run_bead = MagicMock()
    captured: list[str] = []
    log = lambda *a, **k: captured.append(" ".join(str(x) for x in a))  # noqa: E731

    with (
        _patch_epic_mail(MagicMock(return_value=fake_mail)),
        patch("harbor.epic.Beads", return_value=fake_beads),
        patch("harbor.epic.run_bead", fake_run_bead),
    ):
        opts = RunEpicOptions(epic_id="awt-zmq", repo_root=tmp_path, skip_finalize=True)
        result = run_epic(opts, log=log)

    assert result.exit_reason == "lock_held"
    assert result.iterations == 0
    fake_run_bead.assert_not_called()
    fake_beads.ready.assert_not_called()
    # Lock-held path must NOT call release (we never held the lock).
    fake_mail.release_epic.assert_not_called()
    # Operator-visible message identifies the holder.
    assert any("swarm-epic/sess-42" in line for line in captured)


def test_run_epic_releases_lock_when_loop_raises(tmp_path: Path):
    """If something inside the loop raises (e.g. Beads.ready blows up
    permanently), the finally clause must still release the lock."""
    fake_mail = MagicMock()
    fake_beads = MagicMock()
    fake_beads.ready.side_effect = RuntimeError("br executable missing")

    with (
        _patch_epic_mail(MagicMock(return_value=fake_mail)),
        patch("harbor.epic.Beads", return_value=fake_beads),
        patch("harbor.epic.run_bead"),
    ):
        opts = RunEpicOptions(epic_id="awt-zmq", repo_root=tmp_path, skip_finalize=True)
        with pytest.raises(RuntimeError):
            run_epic(opts, log=lambda *a, **k: None)

    fake_mail.acquire_epic.assert_called_once()
    fake_mail.release_epic.assert_called_once()


def test_run_epic_continues_when_mail_unavailable(tmp_path: Path):
    """If `scripts/shared/agent_mail.py` is missing the constructor raises
    FileNotFoundError. Harbor logs and continues lock-less so downstream
    repos that haven't scaffolded Agent Mail still get harbor."""
    def mail_factory(repo_root):  # noqa: ARG001
        raise FileNotFoundError("agent_mail.py not found at /tmp/scripts/shared/...")

    fake_beads = MagicMock()
    fake_beads.ready.side_effect = lambda parent=None: []

    with (
        _patch_epic_mail(mail_factory),
        patch("harbor.epic.Beads", return_value=fake_beads),
        patch("harbor.epic.run_bead"),
    ):
        opts = RunEpicOptions(epic_id="awt-zmq", repo_root=tmp_path, skip_finalize=True)
        result = run_epic(opts, log=lambda *a, **k: None)

    assert result.exit_reason == "drained"
    # No raise propagated, no lock release attempted (we never held one).


def test_run_epic_releases_lock_after_running_beads(tmp_path: Path):
    """End-to-end: lock acquire → run beads → lock release in finally."""
    fake_mail = MagicMock()
    fake_beads = MagicMock()
    counter = {"i": 0}

    def ready_se(parent=None):
        counter["i"] += 1
        if counter["i"] == 1:
            return [{"id": "awt-zmq.1"}]
        return []

    fake_beads.ready.side_effect = ready_se

    with (
        _patch_epic_mail(MagicMock(return_value=fake_mail)),
        patch("harbor.epic.Beads", return_value=fake_beads),
        patch("harbor.epic.run_bead", side_effect=lambda opts, **k: _ok_result(opts.bead_id)),
    ):
        opts = RunEpicOptions(epic_id="awt-zmq", repo_root=tmp_path, max_concurrency=1, skip_finalize=True)
        result = run_epic(opts, log=lambda *a, **k: None)

    assert result.closed == ["awt-zmq.1"]
    # Acquire happens before the loop, release after the loop drains.
    assert fake_mail.acquire_epic.call_count == 1
    assert fake_mail.release_epic.call_count == 1


def test_cmd_run_epic_returns_2_when_lock_held(tmp_path: Path):
    """The CLI wrapper translates exit_reason='lock_held' to process exit 2,
    matching the bead description's acceptance contract."""
    from harbor.__main__ import build_parser

    fake_mail = MagicMock()
    fake_mail.acquire_epic.side_effect = _FakeAgentMailError(
        "locked",
        code=10,
        details={"owner": "swarm-epic/x"},
    )
    fake_beads = MagicMock()

    with (
        _patch_epic_mail(MagicMock(return_value=fake_mail)),
        patch("harbor.epic.Beads", return_value=fake_beads),
        patch("harbor.epic.run_bead"),
    ):
        parser = build_parser()
        args = parser.parse_args([
            "run-epic", "awt-zmq",
            "--repo-root", str(tmp_path),
            "--max-iterations", "1",
        ])
        rc = args.func(args)

    assert rc == 2
