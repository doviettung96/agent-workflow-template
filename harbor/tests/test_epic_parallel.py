"""Parallel-runner tests (Phase 2.2).

Verifies the ThreadPoolExecutor-based loop:
  * Spawns up to `max_concurrency` beads in a single tick.
  * Never exceeds the cap.
  * Returns to drained state once all in-flight finish.
  * `StateStore` survives concurrent record_bead_* calls without corruption.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from harbor.epic import RunEpicOptions, run_epic
from harbor.orchestrator import RunBeadResult
from harbor.state import StateStore


def _ready_mock(*per_tick: list[dict]):
    """Build a `Beads.ready` side_effect that returns the given lists in order
    and yields `[]` forever once exhausted. Tolerant of the extra polls that
    happen when `wait()` returns futures one-at-a-time across multiple
    reap-cycles."""
    queue = iter(per_tick)
    def _se(parent=None):
        return next(queue, [])
    return _se


def _ok_result(bead_id: str) -> RunBeadResult:
    return RunBeadResult(
        bead_id=bead_id, sentinel_status="ok", blocker_class="none",
        exit_code=0, verify=None, closed=True,
    )


class _ConcurrencyTracker:
    """Counts how many fake run_bead calls are in-flight at the same instant.
    `max_observed` lets the test assert the cap is honored."""

    def __init__(self, hold_s: float = 0.05):
        self.hold_s = hold_s
        self._lock = threading.Lock()
        self._in_flight = 0
        self.max_observed = 0
        self.calls: list[str] = []

    def __call__(self, opts, *, log=None, parent_run=None):  # noqa: D401
        with self._lock:
            self._in_flight += 1
            self.calls.append(opts.bead_id)
            if self._in_flight > self.max_observed:
                self.max_observed = self._in_flight
        try:
            time.sleep(self.hold_s)
        finally:
            with self._lock:
                self._in_flight -= 1
        return _ok_result(opts.bead_id)


def test_parallel_runner_spawns_up_to_max_concurrency_in_one_tick(tmp_path: Path):
    """Three independent ready beads + max_concurrency=3 → all three get a
    pool worker before any of them finishes (max_observed >= 2 proves at
    least one moment of true concurrency; we expect 3 here)."""
    tracker = _ConcurrencyTracker(hold_s=0.05)
    fake_beads = MagicMock()
    fake_beads.ready.side_effect = _ready_mock(
        [{"id": "awt.1"}, {"id": "awt.2"}, {"id": "awt.3"}],
    )

    with (
        patch("harbor.epic.Beads", return_value=fake_beads),
        patch("harbor.epic.run_bead", tracker),
    ):
        opts = RunEpicOptions(
            epic_id="awt", repo_root=tmp_path, max_concurrency=3,
            interval_s=1.0,
        )
        result = run_epic(opts, log=lambda *a, **k: None)

    assert result.exit_reason == "drained"
    assert sorted(result.closed) == ["awt.1", "awt.2", "awt.3"]
    assert tracker.max_observed >= 2, (
        f"expected concurrent execution; max_observed={tracker.max_observed}"
    )
    assert tracker.max_observed <= 3
    assert sorted(tracker.calls) == ["awt.1", "awt.2", "awt.3"]


def test_parallel_runner_respects_max_concurrency_cap(tmp_path: Path):
    """Five ready beads, cap=2 → at most 2 in-flight at any moment."""
    tracker = _ConcurrencyTracker(hold_s=0.05)
    fake_beads = MagicMock()
    # Re-yield the same set each tick; the loop tracks attempted to avoid
    # double-spawn, so each unique id only runs once.
    bead_ids = [f"awt.{i}" for i in range(1, 6)]
    fake_beads.ready.side_effect = _ready_mock(
        [{"id": b} for b in bead_ids],
        [{"id": b} for b in bead_ids[2:]],
        [{"id": b} for b in bead_ids[4:]],
    )

    with (
        patch("harbor.epic.Beads", return_value=fake_beads),
        patch("harbor.epic.run_bead", tracker),
    ):
        opts = RunEpicOptions(
            epic_id="awt", repo_root=tmp_path, max_concurrency=2,
            interval_s=1.0,
        )
        result = run_epic(opts, log=lambda *a, **k: None)

    assert result.exit_reason == "drained"
    assert sorted(result.closed) == sorted(bead_ids)
    assert tracker.max_observed <= 2, (
        f"max_concurrency=2 violated; max_observed={tracker.max_observed}"
    )


def test_parallel_runner_does_not_double_spawn_in_flight(tmp_path: Path):
    """Even if br ready keeps returning the same in-flight bead, the runner
    must not submit it to the pool twice."""
    tracker = _ConcurrencyTracker(hold_s=0.05)
    fake_beads = MagicMock()
    fake_beads.ready.side_effect = _ready_mock(
        [{"id": "awt.1"}],
        [{"id": "awt.1"}],  # still 'ready' (in_progress flip didn't stick)
        [{"id": "awt.1"}],
    )

    with (
        patch("harbor.epic.Beads", return_value=fake_beads),
        patch("harbor.epic.run_bead", tracker),
    ):
        opts = RunEpicOptions(
            epic_id="awt", repo_root=tmp_path, max_concurrency=3,
            interval_s=0.02,  # short so tick #2 fires before run_bead returns
        )
        result = run_epic(opts, log=lambda *a, **k: None)

    assert result.closed == ["awt.1"]
    assert tracker.calls.count("awt.1") == 1
    assert tracker.max_observed == 1


def test_parallel_runner_records_workers_under_one_epic_run(tmp_path: Path):
    """All beads spawned by the parallel runner must record events under the
    epic's run_id. The mock here uses a callable side_effect so the extra
    ready() polls that happen across reap-cycles don't trip StopIteration."""
    captured_parent_run = []
    captured_lock = threading.Lock()

    def fake_run_bead(opts, *, log=None, parent_run=None):
        with captured_lock:
            captured_parent_run.append(parent_run)
        return _ok_result(opts.bead_id)

    fake_beads = MagicMock()
    fake_beads.ready.side_effect = _ready_mock(
        [{"id": "awt.1"}, {"id": "awt.2"}],
    )

    with (
        patch("harbor.epic.Beads", return_value=fake_beads),
        patch("harbor.epic.run_bead", fake_run_bead),
    ):
        opts = RunEpicOptions(
            epic_id="awt", repo_root=tmp_path, max_concurrency=2,
            interval_s=1.0,
        )
        result = run_epic(opts, log=lambda *a, **k: None)

    assert result.exit_reason == "drained"
    assert len(captured_parent_run) == 2
    stores = {pr[0] for pr in captured_parent_run}
    run_ids = {pr[1] for pr in captured_parent_run}
    assert len(stores) == 1   # same StateStore instance
    assert run_ids == {result.run_id}


def test_state_store_is_thread_safe_under_concurrent_writes(tmp_path: Path):
    """Direct stress test: 10 threads hammer record_event simultaneously.
    With check_same_thread=True (the pre-P2.2 default) this would raise; with
    the lock + check_same_thread=False it must complete cleanly and record
    every event."""
    store = StateStore(tmp_path)
    run_id = store.start_run(mode="epic", epic_id="awt")

    n_threads = 10
    n_per_thread = 50
    barrier = threading.Barrier(n_threads)

    def worker(idx: int):
        barrier.wait()
        for j in range(n_per_thread):
            store.record_event(
                run_id=run_id, type="probe",
                bead_id=f"t{idx}", payload={"j": j},
            )

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    rows = store._conn.execute(
        "SELECT COUNT(*) FROM events WHERE type = 'probe'"
    ).fetchone()
    assert rows[0] == n_threads * n_per_thread

    store.end_run(run_id, status="finished")
    store.close()
