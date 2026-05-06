from __future__ import annotations

import json
from pathlib import Path

import pytest

from harbor.state import StateStore


def test_snapshot_idle_when_no_run(tmp_path: Path):
    s = StateStore(tmp_path)
    snap = s.snapshot()
    assert snap["mode"] == "idle"
    assert snap["epic_id"] is None
    assert snap["workers"] == []
    assert snap["runner"]["active"] is False


def test_start_run_creates_active_run(tmp_path: Path):
    s = StateStore(tmp_path)
    run_id = s.start_run(mode="single", epic_id=None, pid=999)
    snap = s.snapshot()
    assert snap["mode"] == "single"
    assert snap["epic_id"] is None
    assert snap["runner"]["active"] is True
    assert snap["runner"]["pid"] == 999
    assert run_id == s.active_run()["run_id"]


def test_start_run_rejects_invalid_mode(tmp_path: Path):
    s = StateStore(tmp_path)
    with pytest.raises(ValueError):
        s.start_run(mode="bogus", epic_id=None)


def test_record_bead_lifecycle_updates_workers_and_blockers(tmp_path: Path):
    s = StateStore(tmp_path)
    run_id = s.start_run(mode="epic", epic_id="epic-1", pid=1234)

    s.record_bead_start(
        run_id=run_id,
        bead_id="b-1",
        profile="balanced",
        model="gpt-5.3-codex",
        effort="medium",
        window_name="b-1-window",
    )
    snap = s.snapshot()
    assert len(snap["workers"]) == 1
    assert snap["workers"][0]["bead_id"] == "b-1"
    assert snap["workers"][0]["model"] == "gpt-5.3-codex"

    # Successful finish
    s.record_bead_finish(
        run_id=run_id, bead_id="b-1", exit_code=0, sentinel_status="ok", blocker_class=None
    )
    snap = s.snapshot()
    assert snap["workers"] == []  # no longer active
    assert snap["blockers"] == []

    # Now a failure with classification
    s.record_bead_start(
        run_id=run_id,
        bead_id="b-2",
        profile="balanced",
        model="gpt-5.3-codex",
        effort="medium",
        window_name="b-2-window",
    )
    s.record_bead_finish(
        run_id=run_id,
        bead_id="b-2",
        exit_code=1,
        sentinel_status="blocked",
        blocker_class="contract",
    )
    snap = s.snapshot()
    assert snap["workers"] == []
    assert len(snap["blockers"]) == 1
    assert snap["blockers"][0]["bead_id"] == "b-2"
    assert snap["blockers"][0]["classification"] == "contract"


def test_state_json_and_md_are_emitted(tmp_path: Path):
    s = StateStore(tmp_path)
    run_id = s.start_run(mode="epic", epic_id="epic-7", pid=42)
    s.record_bead_start(
        run_id=run_id,
        bead_id="b-9",
        profile="thorough",
        model="m",
        effort="high",
        window_name="b-9-w",
    )

    state_json = tmp_path / ".beads/workflow/state.json"
    state_md = tmp_path / ".beads/workflow/STATE.md"
    assert state_json.exists()
    assert state_md.exists()

    data = json.loads(state_json.read_text(encoding="utf-8"))
    assert data["epic_id"] == "epic-7"
    assert data["runner"]["pid"] == 42
    assert any(w["bead_id"] == "b-9" for w in data["workers"])

    md = state_md.read_text(encoding="utf-8")
    assert "epic-7" in md
    assert "b-9" in md
    assert "thorough" in md


def test_end_run_marks_idle(tmp_path: Path):
    s = StateStore(tmp_path)
    run_id = s.start_run(mode="single", epic_id=None)
    s.end_run(run_id)
    snap = s.snapshot()
    assert snap["mode"] == "idle"
    assert snap["runner"]["active"] is False


def test_event_log_persists(tmp_path: Path):
    s = StateStore(tmp_path)
    run_id = s.start_run(mode="single", epic_id=None)
    s.record_event(run_id=run_id, type="custom", payload={"hello": "world"})
    rows = s._conn.execute(
        "SELECT type, payload FROM events WHERE run_id = ? ORDER BY id", (run_id,)
    ).fetchall()
    types = [r["type"] for r in rows]
    assert types[0] == "run_started"
    assert "custom" in types
    payloads = [json.loads(r["payload"]) for r in rows]
    assert any(p.get("hello") == "world" for p in payloads)
