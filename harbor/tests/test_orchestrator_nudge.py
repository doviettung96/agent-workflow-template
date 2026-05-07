"""Tests for `run_bead`'s sentinel-nudge logic (awt-zmq.106).

When codex finishes a review-style task with a summary paragraph and forgets
to emit the HARBOR-DONE sentinel, harbor's pane sits idle until --bead-timeout
(6h default). The nudge sends ONE one-line reminder into the REPL after the
pane has been idle for `nudge_idle_threshold_s`, so the agent can recover
without human intervention. These tests pin the contract:

  - nudge fires after sustained idle without a sentinel
  - nudge is skipped once any sentinel (incl. `blocked`) has arrived
  - nudge fires AT MOST once per bead, even on prolonged idle
  - `nudge_idle_threshold_s=0` opts out
  - active panes (pane content keeps changing) never trigger the nudge
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from harbor.orchestrator import RunBeadOptions, run_bead


class FakeTime:
    """Deterministic stand-in for `time` inside the orchestrator. `monotonic()`
    returns the current virtual clock; `sleep(s)` advances it by `s` seconds.
    Patching `harbor.orchestrator.time` lets the poll loop tick through many
    virtual seconds in a few milliseconds of real time, so we can exercise
    minute-scale idle thresholds without slow tests.
    """

    def __init__(self, start: float = 1000.0):
        self._t = start

    def monotonic(self) -> float:
        return self._t

    def sleep(self, secs: float) -> None:
        self._t += max(0.0, secs)


@pytest.fixture
def bead_payload():
    return {
        "id": "awt-test.nudge",
        "status": "open",
        "title": "nudge smoke",
        "description": (
            "Read:\n- README\n\nFiles:\n- harbor/x.py\n\nVerify:\n- echo verify-ok\n"
        ),
    }


def _patch_tmux(panes: list[str]) -> MagicMock:
    """Build a Tmux mock whose capture_pane returns each pane in order, then
    keeps yielding the last one once the queue drains."""
    fake = MagicMock()
    fake.attach_command.return_value = "<attach>"
    fake.has_session.return_value = True
    seq = list(panes)

    def cap(*_a, **_kw):
        if len(seq) > 1:
            return seq.pop(0)
        return seq[0]

    fake.capture_pane.side_effect = cap
    return fake


def _nudge_calls(fake_tmux: MagicMock, bead_id: str) -> list:
    """Return send_keys_literal calls whose pasted text contains the bead's
    HARBOR-DONE template — i.e. the nudge reminders. Other send_keys_literal
    calls (e.g. the prompt body for send_keys-injection profiles) won't match
    because the rendered prompt embeds the format only as `BEAD-ID` placeholders,
    not the substituted bead-id literal in a single-line reminder."""
    needle = f"HARBOR-DONE: {bead_id} status=ok classification=none"
    out = []
    for call in fake_tmux.send_keys_literal.call_args_list:
        args, _ = call
        if any(needle in str(a) for a in args):
            out.append(call)
    return out


def _run(opts, fake_beads, fake_tmux, *, verify_ok=True):
    with (
        patch("harbor.orchestrator.Beads", return_value=fake_beads),
        patch("harbor.orchestrator.Mail", MagicMock()),
        patch("harbor.orchestrator.Tmux", return_value=fake_tmux),
        patch("harbor.orchestrator.run_verify") as fake_verify,
    ):
        fake_verify.return_value = MagicMock(
            success=verify_ok, skipped=False, render_summary=lambda: "ok"
        )
        return run_bead(opts, log=lambda *a, **k: None)


def test_nudge_fires_after_idle_threshold(tmp_path: Path, bead_payload, monkeypatch):
    """Pane stays unchanged for >threshold seconds with no sentinel. Harbor
    sends one send_keys_literal nudge containing the bead's HARBOR-DONE
    template, after which the agent (simulated via the next pane content)
    emits the sentinel and the run closes."""
    monkeypatch.chdir(tmp_path)
    bead_id = "awt-test.nudge1"
    bead = {**bead_payload, "id": bead_id}

    fake_beads = MagicMock()
    fake_beads.show.return_value = bead

    idle_pane = "still thinking...\n"
    final_pane = (
        idle_pane + f"HARBOR-DONE: {bead_id} status=ok classification=none\n"
    )
    # 80 idle polls × 2s = 160 virtual s — well past the 60s threshold; then
    # the agent reacts to the nudge by emitting the sentinel.
    panes = [idle_pane] * 80 + [final_pane]
    fake_tmux = _patch_tmux(panes)

    fake_time = FakeTime()
    monkeypatch.setattr("harbor.orchestrator.time", fake_time)

    opts = RunBeadOptions(
        bead_id=bead_id,
        repo_root=tmp_path,
        poll_interval_s=2.0,
        timeout_s=10_000.0,
        agent_startup_delay_s=0.0,
        nudge_idle_threshold_s=60.0,
    )
    result = _run(opts, fake_beads, fake_tmux)

    nudges = _nudge_calls(fake_tmux, bead_id)
    assert len(nudges) == 1, f"expected exactly one nudge, got {len(nudges)}"
    nudge_text = nudges[0].args[2]
    assert "Reminder from harbor" in nudge_text
    assert f"HARBOR-DONE: {bead_id}" in nudge_text
    assert result.sentinel_status == "ok"
    assert result.closed is True


def test_nudge_skipped_when_sentinel_arrives_first(
    tmp_path: Path, bead_payload, monkeypatch
):
    """If the agent emits ANY sentinel (here: blocked) before idle threshold
    elapses, the nudge MUST NOT fire. The human-recovery flow takes over for
    blocked sentinels — a reminder would just be noise on top."""
    monkeypatch.chdir(tmp_path)
    bead_id = "awt-test.nudge2"
    bead = {**bead_payload, "id": bead_id}

    fake_beads = MagicMock()
    fake_beads.show.return_value = bead

    blocked_pane = (
        "did some work\n"
        f"HARBOR-DONE: {bead_id} status=blocked classification=clarify\n"
    )
    fake_tmux = _patch_tmux([blocked_pane] * 200)

    fake_time = FakeTime()
    monkeypatch.setattr("harbor.orchestrator.time", fake_time)

    opts = RunBeadOptions(
        bead_id=bead_id,
        repo_root=tmp_path,
        poll_interval_s=2.0,
        timeout_s=300.0,
        agent_startup_delay_s=0.0,
        nudge_idle_threshold_s=60.0,
    )
    result = _run(opts, fake_beads, fake_tmux)

    assert _nudge_calls(fake_tmux, bead_id) == [], (
        "nudge must be skipped after any sentinel has arrived"
    )
    assert result.closed is False  # blocked → bead stays open, pane stays alive


def test_nudge_fires_at_most_once(tmp_path: Path, bead_payload, monkeypatch):
    """Even when the pane stays idle for many multiples of the threshold,
    harbor sends the reminder exactly once and falls through to the existing
    --bead-timeout if the agent never recovers."""
    monkeypatch.chdir(tmp_path)
    bead_id = "awt-test.nudge3"
    bead = {**bead_payload, "id": bead_id}

    fake_beads = MagicMock()
    fake_beads.show.return_value = bead

    idle_pane = "thinking...\n"
    fake_tmux = _patch_tmux([idle_pane] * 1000)

    fake_time = FakeTime()
    monkeypatch.setattr("harbor.orchestrator.time", fake_time)

    opts = RunBeadOptions(
        bead_id=bead_id,
        repo_root=tmp_path,
        poll_interval_s=2.0,
        # 600 virtual seconds — 10× the threshold. If the latch were broken
        # we'd see ~9 nudges; the test asserts exactly 1.
        timeout_s=600.0,
        agent_startup_delay_s=0.0,
        nudge_idle_threshold_s=60.0,
    )
    result = _run(opts, fake_beads, fake_tmux)

    nudges = _nudge_calls(fake_tmux, bead_id)
    assert len(nudges) == 1, f"nudge must fire at most once, got {len(nudges)}"
    assert result.closed is False


def test_nudge_disabled_when_threshold_zero(
    tmp_path: Path, bead_payload, monkeypatch
):
    """`nudge_idle_threshold_s=0` is the documented opt-out — long-idle panes
    must not trigger a reminder in that mode."""
    monkeypatch.chdir(tmp_path)
    bead_id = "awt-test.nudge4"
    bead = {**bead_payload, "id": bead_id}

    fake_beads = MagicMock()
    fake_beads.show.return_value = bead

    fake_tmux = _patch_tmux(["thinking...\n"] * 200)

    fake_time = FakeTime()
    monkeypatch.setattr("harbor.orchestrator.time", fake_time)

    opts = RunBeadOptions(
        bead_id=bead_id,
        repo_root=tmp_path,
        poll_interval_s=2.0,
        timeout_s=300.0,
        agent_startup_delay_s=0.0,
        nudge_idle_threshold_s=0.0,
    )
    _run(opts, fake_beads, fake_tmux)

    assert _nudge_calls(fake_tmux, bead_id) == []


def test_nudge_resets_when_pane_changes(tmp_path: Path, bead_payload, monkeypatch):
    """Idle is measured by pane-content stability, not wall time. As long as
    the pane keeps producing new output (codex actively thinking / writing),
    the idle clock keeps resetting and the nudge stays parked."""
    monkeypatch.chdir(tmp_path)
    bead_id = "awt-test.nudge5"
    bead = {**bead_payload, "id": bead_id}

    fake_beads = MagicMock()
    fake_beads.show.return_value = bead

    fake_tmux = MagicMock()
    fake_tmux.attach_command.return_value = "<attach>"
    fake_tmux.has_session.return_value = True
    # Each capture returns content that has never appeared before — the agent
    # is actively producing output. capture_pane has no fixed queue, so we
    # cannot run out of distinct panes within the poll window.
    counter = {"n": 0}

    def cap(*_a, **_kw):
        counter["n"] += 1
        return f"step {counter['n']}\n" * counter["n"]

    fake_tmux.capture_pane.side_effect = cap

    fake_time = FakeTime()
    monkeypatch.setattr("harbor.orchestrator.time", fake_time)

    opts = RunBeadOptions(
        bead_id=bead_id,
        repo_root=tmp_path,
        poll_interval_s=2.0,  # 250 polls × 2s = 500 virtual s, well past 60s
        timeout_s=500.0,
        agent_startup_delay_s=0.0,
        nudge_idle_threshold_s=60.0,
    )
    _run(opts, fake_beads, fake_tmux)

    assert _nudge_calls(fake_tmux, bead_id) == [], (
        "active pane should never trigger the nudge"
    )
