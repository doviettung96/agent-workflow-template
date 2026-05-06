from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

import harbor.runner as runner
from harbor.agent import AgentProfile


@pytest.fixture
def fake_bead():
    return {
        "id": "awt-test.1",
        "title": "fake bead",
        "description": (
            "Read:\n- README.md\n\n"
            "Files:\n- harbor/SMOKE.md\n\n"
            "Verify:\n- echo done\n"
        ),
    }


def test_last_lines_returns_last_n():
    text = "\n".join(f"line{i}" for i in range(50))
    out = runner._last_lines(text, 5)
    assert out.splitlines() == ["line45", "line46", "line47", "line48", "line49"]


def test_write_fallback_creates_file(tmp_path: Path):
    payload = {"bead_id": "awt-1.1", "exit_code": 0, "sentinel_status": "ok"}
    p = runner._write_fallback(tmp_path, payload)
    assert p.exists()
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["bead_id"] == "awt-1.1"


def test_notify_daemon_returns_false_when_unreachable():
    # Daemon URL no one is listening on.
    ok = runner._notify_daemon("http://127.0.0.1:1", {"bead_id": "x"})
    assert ok is False


def test_dry_run_does_not_spawn_agent(fake_bead, tmp_path: Path, monkeypatch, capsys):
    """`--dry-run` should print the prompt preview then return 0 without exec'ing anything."""

    monkeypatch.chdir(tmp_path)

    def fake_show(bead_id):
        return fake_bead

    spawn_called = {"count": 0}

    def fake_spawn(*args, **kwargs):
        spawn_called["count"] += 1
        return 0, ""

    with patch.object(runner, "Beads") as MockBeads:
        MockBeads.return_value.show = fake_show
        with patch.object(runner, "_spawn_agent", side_effect=fake_spawn):
            rc = runner.main(["awt-test.1", "--dry-run", "--repo-root", str(tmp_path)])

    captured = capsys.readouterr()
    assert rc == 0
    assert spawn_called["count"] == 0
    assert "prompt preview" in captured.out
    assert "awt-test.1" in captured.out


def test_full_flow_calls_spawn_and_writes_fallback_on_no_daemon(
    fake_bead, tmp_path: Path, monkeypatch
):
    monkeypatch.chdir(tmp_path)

    fake_output = (
        "[agent log lines]\n"
        "did the work\n"
        "HARBOR-DONE: awt-test.1 status=ok classification=none\n"
    )

    def fake_spawn(profile, model, effort, prompt):
        # Profile should be the default 'balanced'
        assert isinstance(profile, AgentProfile)
        assert profile.name == "balanced"
        return 0, fake_output

    def fake_show(bead_id):
        return fake_bead

    with patch.object(runner, "Beads") as MockBeads:
        MockBeads.return_value.show = fake_show
        with patch.object(runner, "_spawn_agent", side_effect=fake_spawn):
            with patch.object(runner, "_notify_daemon", return_value=False):
                rc = runner.main(["awt-test.1", "--repo-root", str(tmp_path)])

    assert rc == 0
    fallback = tmp_path / ".beads/workflow/runner-finished/awt-test.1.json"
    assert fallback.exists()
    data = json.loads(fallback.read_text(encoding="utf-8"))
    assert data["bead_id"] == "awt-test.1"
    assert data["sentinel_status"] == "ok"
    assert data["blocker_class"] == "none"


def test_blocker_classification_propagates(fake_bead, tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fake_output = (
        "explained why\n"
        "HARBOR-DONE: awt-test.1 status=blocked classification=contract\n"
    )
    with patch.object(runner, "Beads") as MockBeads:
        MockBeads.return_value.show = lambda x: fake_bead
        with patch.object(runner, "_spawn_agent", return_value=(7, fake_output)):
            with patch.object(runner, "_notify_daemon", return_value=False):
                rc = runner.main(["awt-test.1", "--repo-root", str(tmp_path)])

    assert rc == 7
    fallback = tmp_path / ".beads/workflow/runner-finished/awt-test.1.json"
    data = json.loads(fallback.read_text(encoding="utf-8"))
    assert data["sentinel_status"] == "blocked"
    assert data["blocker_class"] == "contract"
    assert data["exit_code"] == 7


def test_no_sentinel_recorded_as_none(fake_bead, tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fake_output = "agent crashed without sentinel\n"
    with patch.object(runner, "Beads") as MockBeads:
        MockBeads.return_value.show = lambda x: fake_bead
        with patch.object(runner, "_spawn_agent", return_value=(2, fake_output)):
            with patch.object(runner, "_notify_daemon", return_value=False):
                rc = runner.main(["awt-test.1", "--repo-root", str(tmp_path)])

    fallback = tmp_path / ".beads/workflow/runner-finished/awt-test.1.json"
    data = json.loads(fallback.read_text(encoding="utf-8"))
    assert data["sentinel_status"] is None
    assert data["blocker_class"] is None
    assert rc == 2
