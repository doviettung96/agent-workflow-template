"""Epic finalize tests (Phase 2.5).

`run_finalize` runs build-and-test then review-epic as synthetic beads, both
through the same `run_bead` path so the operator can attach to the pane and
watch live. Build-and-test gates review-epic — a broken build skips the
review.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from harbor.epic import RunEpicOptions, run_epic
from harbor.finalize import (
    FinalizeResult,
    _build_steps,
    _load_skill_prompt,
    run_finalize,
)
from harbor.orchestrator import RunBeadResult
from harbor.state import StateStore


def _ok_result(bead_id: str) -> RunBeadResult:
    return RunBeadResult(
        bead_id=bead_id, sentinel_status="ok", blocker_class="none",
        exit_code=0, verify=None, closed=True,
    )


def _failed_result(bead_id: str, reason: str = "blocked") -> RunBeadResult:
    return RunBeadResult(
        bead_id=bead_id, sentinel_status=reason, blocker_class="env",
        exit_code=124, verify=None, closed=False,
    )


# ----- pure helper tests -----

def test_load_skill_prompt_uses_repo_skill_when_present(tmp_path: Path):
    skill_dir = tmp_path / "skills" / "review-epic"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("Real review-epic body.", encoding="utf-8")

    out = _load_skill_prompt(tmp_path, "review-epic", "FALLBACK")
    assert "Real review-epic body" in out
    assert "FALLBACK" not in out


def test_load_skill_prompt_falls_back_when_skill_missing(tmp_path: Path):
    out = _load_skill_prompt(tmp_path, "build-and-test", "FALLBACK BODY")
    assert out == "FALLBACK BODY"


def test_build_steps_yields_two_steps_in_correct_order(tmp_path: Path):
    steps = _build_steps(tmp_path, "awt-zmq")
    assert [s.bead_id for s in steps] == [
        "finalize-build-and-test", "finalize-review-epic",
    ]
    # Each description should embed the epic id so the agent has context.
    for step in steps:
        assert "awt-zmq" in step.description


# ----- run_finalize integration tests -----

def test_run_finalize_runs_both_steps_in_order(tmp_path: Path):
    store = StateStore(tmp_path)
    run_id = store.start_run(mode="epic", epic_id="awt-zmq")

    calls: list[str] = []

    def fake_run_bead(opts, *, log=None, parent_run=None, **kwargs):
        calls.append(opts.bead_id)
        # Synthetic beads must arrive with synthetic_bead set.
        assert kwargs.get("synthetic_bead") is not None, "expected synthetic_bead kwarg"
        assert kwargs["synthetic_bead"]["id"] == opts.bead_id
        return _ok_result(opts.bead_id)

    with patch("harbor.finalize.run_bead", fake_run_bead):
        result = run_finalize(
            epic_id="awt-zmq", store=store, run_id=run_id,
            repo_root=tmp_path, log=lambda *a, **k: None,
        )

    assert calls == ["finalize-build-and-test", "finalize-review-epic"]
    assert result.steps_passed == [
        "finalize-build-and-test", "finalize-review-epic",
    ]
    assert result.steps_failed == []
    assert result.skipped == []
    assert result.all_passed is True

    store.end_run(run_id, status="finished")
    store.close()


def test_run_finalize_skips_review_when_build_fails(tmp_path: Path):
    """A broken build must NOT call review-epic — that's the gating contract."""
    store = StateStore(tmp_path)
    run_id = store.start_run(mode="epic", epic_id="awt-zmq")

    calls: list[str] = []

    def fake_run_bead(opts, *, log=None, parent_run=None, **kwargs):
        calls.append(opts.bead_id)
        if opts.bead_id == "finalize-build-and-test":
            return _failed_result(opts.bead_id, reason="blocked")
        return _ok_result(opts.bead_id)

    with patch("harbor.finalize.run_bead", fake_run_bead):
        result = run_finalize(
            epic_id="awt-zmq", store=store, run_id=run_id,
            repo_root=tmp_path, log=lambda *a, **k: None,
        )

    assert calls == ["finalize-build-and-test"]
    assert result.steps_failed == [("finalize-build-and-test", "blocked")]
    assert result.skipped == ["finalize-review-epic"]
    assert result.all_passed is False

    store.end_run(run_id, status="finished")
    store.close()


def test_run_finalize_records_crash_and_skips_remaining(tmp_path: Path):
    store = StateStore(tmp_path)
    run_id = store.start_run(mode="epic", epic_id="awt-zmq")

    def fake_run_bead(opts, *, log=None, parent_run=None, **kwargs):
        if opts.bead_id == "finalize-build-and-test":
            raise RuntimeError("agent CLI vanished")
        return _ok_result(opts.bead_id)

    with patch("harbor.finalize.run_bead", fake_run_bead):
        result = run_finalize(
            epic_id="awt-zmq", store=store, run_id=run_id,
            repo_root=tmp_path, log=lambda *a, **k: None,
        )

    assert result.steps_failed == [("finalize-build-and-test", "crash")]
    assert result.skipped == ["finalize-review-epic"]

    store.end_run(run_id, status="finished")
    store.close()


# ----- epic.run_epic -> finalize integration -----

def test_run_epic_runs_finalize_after_drain(tmp_path: Path):
    """When the loop drains successfully, run_epic must invoke run_finalize
    and surface its result on RunEpicResult.finalize."""
    fake_beads = MagicMock()
    fake_beads.ready.side_effect = lambda parent=None: []

    finalize_calls: list[str] = []

    def fake_run_finalize(*, epic_id, **kwargs):
        finalize_calls.append(epic_id)
        return FinalizeResult(
            epic_id=epic_id,
            steps_run=["finalize-build-and-test", "finalize-review-epic"],
            steps_passed=["finalize-build-and-test", "finalize-review-epic"],
        )

    with (
        patch("harbor.epic.Beads", return_value=fake_beads),
        patch("harbor.epic.run_bead"),
        patch("harbor.finalize.run_finalize", fake_run_finalize),
    ):
        opts = RunEpicOptions(epic_id="awt-zmq", repo_root=tmp_path)
        result = run_epic(opts, log=lambda *a, **k: None)

    assert finalize_calls == ["awt-zmq"]
    assert result.exit_reason == "drained"
    assert result.finalize is not None
    assert result.finalize.all_passed is True


def test_run_epic_skips_finalize_when_failed_set_nonempty(tmp_path: Path):
    """If any bead failed during the main loop, the epic isn't shippable —
    finalize must not run."""
    fake_beads = MagicMock()
    counter = {"i": 0}

    def ready_se(parent=None):
        counter["i"] += 1
        if counter["i"] == 1:
            return [{"id": "awt-zmq.1"}]
        return []

    fake_beads.ready.side_effect = ready_se
    fake_run_bead = MagicMock(
        side_effect=lambda opts, **k: _failed_result(opts.bead_id, "blocked")
    )

    finalize_called = MagicMock()

    with (
        patch("harbor.epic.Beads", return_value=fake_beads),
        patch("harbor.epic.run_bead", fake_run_bead),
        patch("harbor.finalize.run_finalize", finalize_called),
    ):
        opts = RunEpicOptions(epic_id="awt-zmq", repo_root=tmp_path, max_concurrency=1)
        result = run_epic(opts, log=lambda *a, **k: None)

    finalize_called.assert_not_called()
    assert result.failed == [("awt-zmq.1", "blocked")]
    assert result.finalize is None


def test_run_epic_finalize_failed_changes_exit_reason(tmp_path: Path):
    fake_beads = MagicMock()
    fake_beads.ready.side_effect = lambda parent=None: []

    def fake_run_finalize(*, epic_id, **kwargs):
        return FinalizeResult(
            epic_id=epic_id,
            steps_run=["finalize-build-and-test"],
            steps_passed=[],
            steps_failed=[("finalize-build-and-test", "blocked")],
            skipped=["finalize-review-epic"],
        )

    with (
        patch("harbor.epic.Beads", return_value=fake_beads),
        patch("harbor.epic.run_bead"),
        patch("harbor.finalize.run_finalize", fake_run_finalize),
    ):
        opts = RunEpicOptions(epic_id="awt-zmq", repo_root=tmp_path)
        result = run_epic(opts, log=lambda *a, **k: None)

    assert result.exit_reason == "finalize_failed"
    assert result.finalize is not None
    assert result.finalize.all_passed is False
