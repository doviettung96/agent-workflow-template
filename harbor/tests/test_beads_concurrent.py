"""Concurrency tests for `Beads` write paths (awt-zmq.107).

The Phase 2 smoke (Run 2, run id 3c257f04563a) caught a real-world race:
three worker threads called `br close` on three independent beads within
~1 second of each other; harbor logged success for all three but only two
landed in `.beads/issues.jsonl`. The underlying bug is in `br`'s JSONL
write path, but harbor exposes it via the parallel epic runner. The fix
in `harbor.beads` is a process-wide `_WRITE_LOCK` that serializes every
write invocation.

These tests verify the lock holds:

  - `close` calls from N concurrent threads never overlap inside the
    `subprocess.run` invocation.
  - `update_status` calls from N concurrent threads never overlap.
  - Read paths (`show`, `ready`) are NOT serialized — they keep running
    in parallel with each other and with writes.
  - `close_batch` issues exactly one subprocess call regardless of the
    number of bead-ids, which is the long-term escape hatch from N
    sequential lock acquisitions.
"""
from __future__ import annotations

import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from harbor.beads import Beads


def _completed(returncode: int = 0, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


class OverlapDetector:
    """Records concurrent entries to its `enter`/`exit` window. After a
    workload runs through it, `max_overlap` reveals whether the workload
    was actually serialized (==1) or interleaved (>1)."""

    def __init__(self):
        self._lock = threading.Lock()
        self.in_flight = 0
        self.max_overlap = 0
        self.overlapped_invocations: list[str] = []

    def enter(self, tag: str) -> None:
        with self._lock:
            self.in_flight += 1
            self.max_overlap = max(self.max_overlap, self.in_flight)
            if self.in_flight > 1:
                self.overlapped_invocations.append(tag)

    def exit(self) -> None:
        with self._lock:
            self.in_flight -= 1


def test_concurrent_close_calls_are_serialized():
    """N=10 worker threads each calling `Beads.close` for distinct ids must
    serialize inside the subprocess invocation — `br` never sees more than
    one write at a time, even though the calls are issued concurrently."""
    detector = OverlapDetector()

    def fake_run(argv, **kwargs):
        # The third positional after `br close` is the bead-id.
        bid = argv[2] if len(argv) >= 3 else "?"
        detector.enter(bid)
        # Simulate a slow JSONL write so two unsynchronized threads would
        # provably overlap without the lock.
        time.sleep(0.01)
        detector.exit()
        return _completed()

    beads = Beads()
    with patch("harbor.beads.subprocess.run", side_effect=fake_run):
        with ThreadPoolExecutor(max_workers=10) as ex:
            futs = [ex.submit(beads.close, f"awt-test.{i}") for i in range(10)]
            for f in futs:
                f.result()

    assert detector.max_overlap == 1, (
        f"close calls overlapped (max in-flight = {detector.max_overlap}); "
        f"overlapped on {detector.overlapped_invocations[:5]}"
    )


def test_concurrent_update_status_calls_are_serialized():
    """`update_status` shares the same JSONL race as `close` — both are
    write paths into `.beads/issues.jsonl`. Same lock; same expectation."""
    detector = OverlapDetector()

    def fake_run(argv, **kwargs):
        detector.enter(argv[2] if len(argv) >= 3 else "?")
        time.sleep(0.01)
        detector.exit()
        return _completed()

    beads = Beads()
    with patch("harbor.beads.subprocess.run", side_effect=fake_run):
        with ThreadPoolExecutor(max_workers=10) as ex:
            futs = [
                ex.submit(beads.update_status, f"awt-test.{i}", "in_progress")
                for i in range(10)
            ]
            for f in futs:
                f.result()

    assert detector.max_overlap == 1, (
        f"update_status calls overlapped (max in-flight = {detector.max_overlap})"
    )


def test_reads_are_not_serialized_against_writes():
    """The lock guards writes only. Read paths (`show`, `ready`) must keep
    running concurrently — otherwise a slow `br close` would block every
    pane-poll thread inspecting bead state, defeating the parallel runner.

    We launch 5 slow concurrent reads under one held write and assert the
    reads ran in parallel (max_overlap > 1).
    """
    read_detector = OverlapDetector()
    write_started = threading.Event()
    write_finish = threading.Event()

    def fake_run(argv, **kwargs):
        cmd = argv[1] if len(argv) >= 2 else ""
        if cmd in {"close", "update"}:
            write_started.set()
            # Wait until the read-fanout has been launched and is in flight,
            # then finish. If the lock incorrectly covered reads, the reads
            # would be queued behind us and max_overlap would equal 1.
            write_finish.wait(timeout=2.0)
            return _completed()
        # Read path: `show` returns a bead JSON list.
        read_detector.enter(cmd)
        time.sleep(0.05)
        read_detector.exit()
        return _completed(stdout='[{"id": "x", "status": "open"}]')

    beads = Beads()
    with patch("harbor.beads.subprocess.run", side_effect=fake_run):
        with ThreadPoolExecutor(max_workers=8) as ex:
            write_fut = ex.submit(beads.close, "awt-test.lockholder")
            # Wait for the write to enter the locked region before launching
            # readers so we're actually testing concurrent-with-write.
            assert write_started.wait(timeout=2.0), "write never started"
            read_futs = [ex.submit(beads.show, f"awt-test.{i}") for i in range(5)]
            # Give readers a moment to actually start before releasing the writer.
            time.sleep(0.1)
            write_finish.set()
            write_fut.result()
            for f in read_futs:
                f.result()

    assert read_detector.max_overlap > 1, (
        f"reads were serialized against the write (max_overlap = "
        f"{read_detector.max_overlap}); the lock should guard writes only"
    )


def test_close_batch_issues_one_subprocess_call():
    """`close_batch` is the long-term escape hatch from N sequential locked
    close() calls — it shells out to `br close <id1> <id2> ...` exactly once,
    regardless of batch size. Lower contention, lower fork+exec overhead.
    """
    captured: list[list[str]] = []

    def fake_run(argv, **kwargs):
        captured.append(list(argv))
        return _completed()

    beads = Beads()
    with patch("harbor.beads.subprocess.run", side_effect=fake_run):
        beads.close_batch(["a", "b", "c", "d"])

    assert len(captured) == 1, f"expected exactly 1 br call, got {len(captured)}"
    argv = captured[0]
    assert argv[:2] == ["br", "close"]
    assert argv[2:6] == ["a", "b", "c", "d"]
    assert "--no-db" in argv


def test_close_batch_with_reason_appends_flag():
    captured: list[list[str]] = []

    def fake_run(argv, **kwargs):
        captured.append(list(argv))
        return _completed()

    beads = Beads()
    with patch("harbor.beads.subprocess.run", side_effect=fake_run):
        beads.close_batch(["a", "b"], reason="epic-drained")

    argv = captured[0]
    assert "--reason" in argv
    assert argv[argv.index("--reason") + 1] == "epic-drained"


def test_close_batch_empty_list_is_noop():
    """Empty batch must not invoke `br` at all — calling `br close --no-db`
    with no ids would be an error (or worse, a 'close everything' surprise)."""
    captured: list[list[str]] = []

    def fake_run(argv, **kwargs):
        captured.append(list(argv))
        return _completed()

    beads = Beads()
    with patch("harbor.beads.subprocess.run", side_effect=fake_run):
        beads.close_batch([])

    assert captured == []
