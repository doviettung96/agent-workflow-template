"""Reservation-conflict deferral tests (Phase 2.4).

The parallel epic runner pre-reserves Files: paths under a per-bead owner
before submitting `run_bead` to the pool. If the reservation conflicts with
another holder, the bead is *deferred* — not added to `attempted`, not
spawned this tick — and retried on subsequent ticks. The same bead spawns
the moment the conflicting holder releases.
"""
from __future__ import annotations

import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from harbor.epic import RunEpicOptions, run_epic
from harbor.orchestrator import (
    ReservationOutcome,
    RunBeadResult,
    try_reserve_for_bead,
)


# ----- pure helper tests -----

def test_try_reserve_returns_ok_when_files_empty():
    fake_mail = MagicMock()
    out = try_reserve_for_bead(fake_mail, owner="o", files=[], bead_id="b")
    assert out.ok is True
    assert out.available is True
    fake_mail.reserve.assert_not_called()


def test_try_reserve_returns_ok_when_mail_is_none():
    out = try_reserve_for_bead(None, owner="o", files=["a"], bead_id="b")
    assert out.ok is True
    assert out.available is False


def test_try_reserve_translates_conflict_to_outcome():
    """`mail.reserve` raising with `details.conflicts` becomes ok=False with
    the conflicting owners enumerated. Other errors propagate."""
    class _Err(Exception):
        def __init__(self, msg, details=None):
            super().__init__(msg)
            self.details = details

    fake_mail = MagicMock()
    fake_mail.reserve.side_effect = _Err(
        "conflict",
        details={"conflicts": [
            {"owner": "swarm-epic/sess-1"},
            {"owner": "swarm-epic/sess-1"},  # dup — should dedupe
            {"owner": "harbor/other-run/x"},
        ]},
    )
    out = try_reserve_for_bead(fake_mail, owner="me", files=["src/a"], bead_id="b")
    assert out.ok is False
    assert out.available is True
    assert out.conflict_with == ("harbor/other-run/x", "swarm-epic/sess-1")


def test_try_reserve_propagates_non_conflict_errors():
    fake_mail = MagicMock()
    fake_mail.reserve.side_effect = RuntimeError("network fail")
    with pytest.raises(RuntimeError):
        try_reserve_for_bead(fake_mail, owner="me", files=["x"], bead_id="b")


# ----- runner integration tests -----

def _ok_result(bead_id: str) -> RunBeadResult:
    return RunBeadResult(
        bead_id=bead_id, sentinel_status="ok", blocker_class="none",
        exit_code=0, verify=None, closed=True,
    )


class _ConflictingMail:
    """Stand-in for `Mail` whose `reserve` conflicts on the first call for
    each bead and succeeds on subsequent calls — simulates a real holder
    releasing between ticks."""

    def __init__(self, conflict_holder: str = "swarm-epic/x"):
        self.conflict_holder = conflict_holder
        self.calls: list[tuple[str, str]] = []  # (owner, bead_id)
        self.released: list[tuple[str, str]] = []
        self._first_call = True
        self._lock = threading.Lock()

    # epic-lock interface — always grants, never raises
    def acquire_epic(self, *, epic_id, owner, **_kwargs):
        return {"ok": True}

    def release_epic(self, *, epic_id, owner, **_kwargs):
        return {"ok": True}

    def register(self, *, name, role, bead_id=None, epic_id=None, **_kwargs):
        return {"ok": True}

    def reserve(self, *, owner, paths, bead_id=None, epic_id=None, **_kwargs):
        with self._lock:
            self.calls.append((owner, bead_id))
            should_conflict = self._first_call
            self._first_call = False
        if should_conflict:
            err = Exception("Reservation conflict detected")
            err.details = {"conflicts": [{"owner": self.conflict_holder}]}
            err.code = 12
            raise err
        return {"ok": True}

    def release_reservations(self, *, owner, bead_id=None, **_kwargs):
        with self._lock:
            self.released.append((owner, bead_id))
        return {"ok": True}


def test_reservation_conflict_defers_bead_and_retries(tmp_path: Path):
    """First tick: reserve raises conflict → bead deferred, no spawn. Second
    tick: reserve succeeds → bead spawns and closes."""
    fake_mail = _ConflictingMail()
    fake_beads = MagicMock()
    fake_beads.ready.side_effect = lambda parent=None: (
        [{
            "id": "awt.1",
            "description": "Read:\n- README\n\nFiles:\n- src/contended.py\n",
        }]
        if "awt.1" not in finished else []
    )

    finished: set[str] = set()
    spawn_log: list[str] = []

    def fake_run_bead(opts, *, log=None, parent_run=None, **kwargs):
        spawn_log.append(opts.bead_id)
        finished.add(opts.bead_id)
        return _ok_result(opts.bead_id)

    captured: list[str] = []
    log = lambda *a, **k: captured.append(" ".join(str(x) for x in a))  # noqa: E731

    with (
        patch("harbor.epic.Mail", MagicMock(return_value=fake_mail)),
        patch("harbor.epic.Beads", return_value=fake_beads),
        patch("harbor.epic.run_bead", fake_run_bead),
    ):
        opts = RunEpicOptions(
            epic_id="awt", repo_root=tmp_path, max_concurrency=2,
            interval_s=0.05,  # short tick so the second iteration fires fast
        )
        result = run_epic(opts, log=log)

    assert result.exit_reason == "drained"
    assert result.closed == ["awt.1"]
    # Bead was reserved twice — once conflicting, once succeeding.
    assert len(fake_mail.calls) == 2
    # Reservation must have been released after the bead finished.
    assert ("harbor/" + result.run_id + "/awt.1", "awt.1") in fake_mail.released
    # Spawn happened exactly once — not on the conflicting tick.
    assert spawn_log == ["awt.1"]
    # Operator-visible defer log appeared.
    assert any("deferred awt.1" in line for line in captured), captured


def test_permanent_reservation_conflict_exits_deferred_out(tmp_path: Path):
    """If the conflicting holder never releases, the runner can't make
    progress. After the first tick where the only ready bead is deferred
    and nothing is in flight, exit with reason='deferred_out'."""
    class _AlwaysConflicts(_ConflictingMail):
        def reserve(self, *, owner, paths, bead_id=None, epic_id=None, **_kwargs):
            with self._lock:
                self.calls.append((owner, bead_id))
            err = Exception("conflict")
            err.details = {"conflicts": [{"owner": self.conflict_holder}]}
            err.code = 12
            raise err

    fake_mail = _AlwaysConflicts()
    fake_beads = MagicMock()
    fake_beads.ready.side_effect = lambda parent=None: [{
        "id": "awt.1",
        "description": "Files:\n- src/contended.py\n",
    }]

    fake_run_bead = MagicMock()  # must never be called

    with (
        patch("harbor.epic.Mail", MagicMock(return_value=fake_mail)),
        patch("harbor.epic.Beads", return_value=fake_beads),
        patch("harbor.epic.run_bead", fake_run_bead),
    ):
        opts = RunEpicOptions(
            epic_id="awt", repo_root=tmp_path, max_concurrency=2,
            interval_s=0.05, max_iterations=1,
        )
        result = run_epic(opts, log=lambda *a, **k: None)

    assert result.exit_reason == "deferred_out"
    assert result.closed == []
    fake_run_bead.assert_not_called()


def test_two_beads_with_overlapping_files_serialize_through_reservation(tmp_path: Path):
    """Two ready beads claim the same file. With max_concurrency=2 the loop
    would normally spawn both at once; reservations force them to serialize
    — second bead defers until the first releases."""
    finished: set[str] = set()
    finished_lock = threading.Lock()

    class _SharedFileMail:
        def __init__(self):
            self.reservations: dict[str, str] = {}  # path -> owner
            self.released_beads: list[str] = []
            self.lock = threading.Lock()

        def acquire_epic(self, **_): return {"ok": True}
        def release_epic(self, **_): return {"ok": True}
        def register(self, **_): return {"ok": True}

        def reserve(self, *, owner, paths, bead_id=None, epic_id=None, **_):
            with self.lock:
                conflicts = []
                for p in paths:
                    held_by = self.reservations.get(p)
                    if held_by and held_by != owner:
                        conflicts.append({"owner": held_by, "path": p})
                if conflicts:
                    err = Exception("conflict")
                    err.details = {"conflicts": conflicts}
                    err.code = 12
                    raise err
                for p in paths:
                    self.reservations[p] = owner
            return {"ok": True}

        def release_reservations(self, *, owner, bead_id=None, **_):
            with self.lock:
                self.released_beads.append(bead_id or "")
                self.reservations = {
                    p: o for p, o in self.reservations.items() if o != owner
                }
            return {"ok": True}

    fake_mail = _SharedFileMail()
    fake_beads = MagicMock()
    fake_beads.ready.side_effect = lambda parent=None: [
        {"id": b, "description": "Files:\n- src/shared.py\n"}
        for b in ("awt.A", "awt.B") if b not in finished
    ]

    def fake_run_bead(opts, *, log=None, parent_run=None, **_):
        # Hold the reservation a moment so the second bead must wait.
        import time as _t
        _t.sleep(0.04)
        with finished_lock:
            finished.add(opts.bead_id)
        return _ok_result(opts.bead_id)

    with (
        patch("harbor.epic.Mail", MagicMock(return_value=fake_mail)),
        patch("harbor.epic.Beads", return_value=fake_beads),
        patch("harbor.epic.run_bead", fake_run_bead),
    ):
        opts = RunEpicOptions(
            epic_id="awt", repo_root=tmp_path, max_concurrency=2,
            interval_s=0.02,
        )
        result = run_epic(opts, log=lambda *a, **k: None)

    assert result.exit_reason == "drained"
    assert sorted(result.closed) == ["awt.A", "awt.B"]
    # Both beads' reservations released exactly once.
    assert sorted(fake_mail.released_beads) == ["awt.A", "awt.B"]


def test_run_bead_aborts_on_late_reservation_conflict(tmp_path: Path):
    """Defensive path: even if epic.py somehow submits run_bead without
    pre-reserving, run_bead's own reserve attempt must fail clean (no tmux
    spawn, return reservation_conflict marker) rather than tearing down
    halfway through."""
    from harbor.orchestrator import RunBeadOptions, run_bead

    # Build a bead with a Files: section so reserve gets called.
    bead_payload = {
        "id": "awt.1",
        "status": "open",
        "title": "smoke",
        "description": "Files:\n- src/x.py\n",
    }

    fake_beads = MagicMock()
    fake_beads.show.return_value = bead_payload
    fake_beads.update_status.return_value = None

    # Mail.reserve always conflicts
    fake_mail = MagicMock()
    err = Exception("conflict")
    err.details = {"conflicts": [{"owner": "other"}]}
    err.code = 12
    fake_mail.reserve.side_effect = err

    fake_tmux = MagicMock()

    with (
        patch("harbor.orchestrator.Beads", return_value=fake_beads),
        patch("harbor.orchestrator.Mail", MagicMock(return_value=fake_mail)),
        patch("harbor.orchestrator.Tmux", return_value=fake_tmux),
    ):
        opts = RunBeadOptions(
            bead_id="awt.1", repo_root=tmp_path,
            poll_interval_s=0.01, timeout_s=1.0,
            agent_startup_delay_s=0.0,
        )
        result = run_bead(opts, log=lambda *a, **k: None)

    assert result.closed is False
    assert result.sentinel_status == "reservation_conflict"
    assert result.blocker_class == "reservation"
    fake_tmux.ensure_session.assert_not_called()
    fake_tmux.send_keys.assert_not_called()
