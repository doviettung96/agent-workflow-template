"""Tests for the sequential epic runner (Phase 2.1).

The orchestrator's heavy collaborators (Tmux, Mail, Beads, run_bead itself)
are patched out — these tests focus on the loop contract:
  * polls `Beads.ready(parent=epic_id)`
  * runs each ready descendant exactly once via `run_bead`
  * stops cleanly when the ready set drains
  * records one StateStore run with mode='epic' and ends it on exit
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from harbor.epic import RunEpicOptions, run_epic
from harbor.orchestrator import RunBeadResult


def _ok_result(bead_id: str) -> RunBeadResult:
    return RunBeadResult(
        bead_id=bead_id,
        sentinel_status="ok",
        blocker_class="none",
        exit_code=0,
        verify=None,
        closed=True,
    )


def _failed_result(bead_id: str, reason: str = "blocked") -> RunBeadResult:
    return RunBeadResult(
        bead_id=bead_id,
        sentinel_status=reason,
        blocker_class="env",
        exit_code=124,
        verify=None,
        closed=False,
    )


def _ready_responses(*per_tick: list[str]) -> list[list[dict]]:
    return [[{"id": rid} for rid in tick] for tick in per_tick]


def _patch_epic(beads_responses: list[list[dict]], run_bead_side_effect):
    """Common patch context: fake Beads with a queue of ready() responses, and
    a fake run_bead returning RunBeadResults from `run_bead_side_effect`."""
    fake_beads = MagicMock()
    fake_beads.ready.side_effect = list(beads_responses)
    fake_run_bead = MagicMock(side_effect=run_bead_side_effect)
    return fake_beads, fake_run_bead


def test_run_epic_exits_immediately_on_empty_ready(tmp_path: Path):
    fake_beads, fake_run_bead = _patch_epic(_ready_responses([]), [])

    with (
        patch("harbor.epic.Beads", return_value=fake_beads),
        patch("harbor.epic.run_bead", fake_run_bead),
    ):
        opts = RunEpicOptions(epic_id="awt-zmq", repo_root=tmp_path)
        result = run_epic(opts, log=lambda *a, **k: None)

    assert result.exit_reason == "drained"
    assert result.iterations == 1
    assert result.closed == []
    assert result.failed == []
    fake_run_bead.assert_not_called()


def test_run_epic_runs_each_ready_bead_in_order(tmp_path: Path):
    """Three ready beads, sequential: each runs exactly once, in the order
    Beads.ready returns them. The loop drains on the fourth tick."""
    fake_beads, fake_run_bead = _patch_epic(
        _ready_responses(
            ["awt-zmq.1", "awt-zmq.2", "awt-zmq.3"],
            ["awt-zmq.2", "awt-zmq.3"],
            ["awt-zmq.3"],
            [],
        ),
        [_ok_result("awt-zmq.1"), _ok_result("awt-zmq.2"), _ok_result("awt-zmq.3")],
    )

    with (
        patch("harbor.epic.Beads", return_value=fake_beads),
        patch("harbor.epic.run_bead", fake_run_bead),
    ):
        opts = RunEpicOptions(epic_id="awt-zmq", repo_root=tmp_path)
        result = run_epic(opts, log=lambda *a, **k: None)

    assert result.exit_reason == "drained"
    assert result.closed == ["awt-zmq.1", "awt-zmq.2", "awt-zmq.3"]
    assert result.failed == []
    assert fake_run_bead.call_count == 3
    spawned = [call.args[0].bead_id for call in fake_run_bead.call_args_list]
    assert spawned == ["awt-zmq.1", "awt-zmq.2", "awt-zmq.3"]


def test_run_epic_records_state_with_mode_epic(tmp_path: Path):
    fake_beads, fake_run_bead = _patch_epic(_ready_responses([]), [])

    with (
        patch("harbor.epic.Beads", return_value=fake_beads),
        patch("harbor.epic.run_bead", fake_run_bead),
    ):
        opts = RunEpicOptions(epic_id="awt-zmq", repo_root=tmp_path)
        result = run_epic(opts, log=lambda *a, **k: None)

    state_path = tmp_path / ".beads" / "workflow" / "state.json"
    assert state_path.exists()
    state = json.loads(state_path.read_text(encoding="utf-8"))
    # The run is now ended (no active run), so snapshot drops to idle.
    assert state["mode"] == "idle"
    assert state["runner"]["active"] is False
    assert isinstance(result.run_id, str) and len(result.run_id) > 0


def test_run_epic_logs_tick_with_ready_set(tmp_path: Path):
    fake_beads, fake_run_bead = _patch_epic(
        _ready_responses(["awt-zmq.1"], []),
        [_ok_result("awt-zmq.1")],
    )

    captured: list[str] = []
    log = lambda *a, **k: captured.append(" ".join(str(x) for x in a))  # noqa: E731

    with (
        patch("harbor.epic.Beads", return_value=fake_beads),
        patch("harbor.epic.run_bead", fake_run_bead),
    ):
        opts = RunEpicOptions(epic_id="awt-zmq", repo_root=tmp_path)
        run_epic(opts, log=log)

    tick_lines = [line for line in captured if "tick #" in line]
    assert len(tick_lines) >= 2
    assert "ready=['awt-zmq.1']" in tick_lines[0]
    assert "ready=[]" in tick_lines[-1]


def test_run_epic_max_iterations_caps_loop(tmp_path: Path):
    """A pathological epic that keeps yielding new ready beads must stop at
    max_iterations rather than running forever. Use a counter-driven fake
    that surfaces a fresh bead on each tick."""
    counter = {"n": 0}

    def ready_side_effect(parent=None):
        counter["n"] += 1
        return [{"id": f"awt-zmq.{counter['n']}"}]

    fake_beads = MagicMock()
    fake_beads.ready.side_effect = ready_side_effect
    fake_run_bead = MagicMock(side_effect=lambda opts, **k: _ok_result(opts.bead_id))

    with (
        patch("harbor.epic.Beads", return_value=fake_beads),
        patch("harbor.epic.run_bead", fake_run_bead),
    ):
        opts = RunEpicOptions(
            epic_id="awt-zmq", repo_root=tmp_path, max_iterations=2
        )
        result = run_epic(opts, log=lambda *a, **k: None)

    assert result.exit_reason == "max_iterations"
    assert result.iterations == 2
    assert fake_run_bead.call_count == 2


def test_run_epic_filters_epic_id_from_ready_list(tmp_path: Path):
    """`br ready --parent X` sometimes echoes X itself when no children remain.
    The runner must not try to spawn the epic as if it were a bead."""
    fake_beads, fake_run_bead = _patch_epic(
        _ready_responses(["awt-zmq", "awt-zmq.1"], ["awt-zmq"]),
        [_ok_result("awt-zmq.1")],
    )

    with (
        patch("harbor.epic.Beads", return_value=fake_beads),
        patch("harbor.epic.run_bead", fake_run_bead),
    ):
        opts = RunEpicOptions(epic_id="awt-zmq", repo_root=tmp_path)
        result = run_epic(opts, log=lambda *a, **k: None)

    assert result.exit_reason == "drained"
    assert result.closed == ["awt-zmq.1"]
    spawned = [call.args[0].bead_id for call in fake_run_bead.call_args_list]
    assert spawned == ["awt-zmq.1"]  # epic itself was never picked


def test_run_epic_does_not_reattempt_failed_bead(tmp_path: Path):
    """When a bead returns closed=False, the runner must not re-spawn it on
    subsequent ticks even if br ready keeps surfacing it (e.g. because the FK
    bug prevented the in_progress status flip from sticking)."""
    fake_beads, fake_run_bead = _patch_epic(
        _ready_responses(
            ["awt-zmq.1", "awt-zmq.2"],
            ["awt-zmq.1", "awt-zmq.2"],  # 1 still 'ready' even after attempt
            ["awt-zmq.1"],                # only 1 left — already attempted
        ),
        [_failed_result("awt-zmq.1"), _ok_result("awt-zmq.2")],
    )

    with (
        patch("harbor.epic.Beads", return_value=fake_beads),
        patch("harbor.epic.run_bead", fake_run_bead),
    ):
        opts = RunEpicOptions(epic_id="awt-zmq", repo_root=tmp_path)
        result = run_epic(opts, log=lambda *a, **k: None)

    assert result.exit_reason == "all_attempted"
    assert result.closed == ["awt-zmq.2"]
    assert result.failed == [("awt-zmq.1", "blocked")]
    spawned = [call.args[0].bead_id for call in fake_run_bead.call_args_list]
    assert spawned == ["awt-zmq.1", "awt-zmq.2"]


def test_run_epic_propagates_parent_run_to_run_bead(tmp_path: Path):
    """run_bead must be called with parent_run=(store, run_id) so bead events
    record under the epic's run rather than spawning a parallel single run."""
    fake_beads, fake_run_bead = _patch_epic(
        _ready_responses(["awt-zmq.1"], []),
        [_ok_result("awt-zmq.1")],
    )

    with (
        patch("harbor.epic.Beads", return_value=fake_beads),
        patch("harbor.epic.run_bead", fake_run_bead),
    ):
        opts = RunEpicOptions(epic_id="awt-zmq", repo_root=tmp_path)
        result = run_epic(opts, log=lambda *a, **k: None)

    assert fake_run_bead.call_count == 1
    kwargs = fake_run_bead.call_args.kwargs
    assert "parent_run" in kwargs
    store, run_id = kwargs["parent_run"]
    assert run_id == result.run_id
    assert hasattr(store, "record_bead_start")  # is a StateStore


def test_run_epic_handles_run_bead_crash_and_continues(tmp_path: Path):
    """If run_bead raises (e.g. profile lookup fails), the epic loop should
    record the failure and move on to the next ready bead."""
    fake_beads, _ = _patch_epic(
        _ready_responses(
            ["awt-zmq.1", "awt-zmq.2"],
            ["awt-zmq.2"],
            [],
        ),
        [],
    )

    def crash_then_succeed(opts, **_kwargs):
        if opts.bead_id == "awt-zmq.1":
            raise RuntimeError("boom")
        return _ok_result(opts.bead_id)

    fake_run_bead = MagicMock(side_effect=crash_then_succeed)

    with (
        patch("harbor.epic.Beads", return_value=fake_beads),
        patch("harbor.epic.run_bead", fake_run_bead),
    ):
        opts = RunEpicOptions(epic_id="awt-zmq", repo_root=tmp_path)
        result = run_epic(opts, log=lambda *a, **k: None)

    assert result.exit_reason == "drained"
    assert result.closed == ["awt-zmq.2"]
    assert result.failed == [("awt-zmq.1", "crash")]
    assert fake_run_bead.call_count == 2
