"""Smoke tests for the FastAPI webview. We don't spin up uvicorn — TestClient
mounts the app in-process. tmux + br are mocked at module level."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import harbor.webui.server as server_mod
from harbor.webui.server import create_app


@pytest.fixture
def app_client(tmp_path: Path):
    fake_beads = MagicMock()
    fake_beads.show.return_value = {
        "id": "awt-test.1",
        "status": "open",
        "title": "Sample bead",
        "description": "Read:\n- README.md\n\nFiles:\n- harbor/x.py\n\nVerify:\n- echo ok\n",
        "issue_type": "task",
        "priority": 2,
    }
    fake_beads.ready.return_value = [
        {"id": "awt-test.1", "title": "Sample bead", "issue_type": "task", "priority": 2},
        {"id": "awt-test.epic", "title": "epic", "issue_type": "epic", "priority": 1},
    ]

    fake_tmux = MagicMock()
    fake_tmux.attach_command.return_value = "tmux -L harbor attach -t harbor-XX:awt-test.1"
    fake_tmux.window_exists.return_value = False
    fake_tmux.capture_pane.return_value = ""

    with patch.object(server_mod, "Beads", return_value=fake_beads), \
         patch.object(server_mod, "Tmux", return_value=fake_tmux):
        app = create_app(tmp_path)
        client = TestClient(app)
        yield client, fake_beads, fake_tmux


def test_dashboard_renders_with_ready_beads(app_client):
    client, _, _ = app_client
    r = client.get("/")
    assert r.status_code == 200
    assert "harbor" in r.text
    assert "awt-test.1" in r.text
    assert "Sample bead" in r.text
    # Epic should be filtered out of the ready list
    assert ">awt-test.epic<" not in r.text


def test_dashboard_status_partial(app_client):
    client, _, _ = app_client
    r = client.get("/_partials/dashboard-status")
    assert r.status_code == 200
    assert "Workers" in r.text


def test_bead_detail_shows_attach_command(app_client):
    client, _, _ = app_client
    r = client.get("/bead/awt-test.1")
    assert r.status_code == 200
    assert "tmux -L harbor attach" in r.text
    assert "harbor/x.py" in r.text  # description rendered


def test_bead_detail_404_for_missing_bead(app_client):
    client, fake_beads, _ = app_client
    fake_beads.show.side_effect = RuntimeError("nope")
    r = client.get("/bead/missing.99")
    assert r.status_code == 404


def test_runner_finished_writes_fallback(tmp_path: Path):
    with patch.object(server_mod, "Beads"), patch.object(server_mod, "Tmux"):
        app = create_app(tmp_path)
        client = TestClient(app)
    payload = {
        "bead_id": "awt-x.1",
        "exit_code": 0,
        "sentinel_status": "ok",
        "blocker_class": "none",
        "last_output": "done",
    }
    r = client.post("/_internal/finished", json=payload)
    assert r.status_code == 200
    fb = tmp_path / ".beads/workflow/runner-finished/awt-x.1.json"
    assert fb.exists()
    assert json.loads(fb.read_text(encoding="utf-8"))["sentinel_status"] == "ok"


def test_runner_finished_rejects_missing_id(tmp_path: Path):
    with patch.object(server_mod, "Beads"), patch.object(server_mod, "Tmux"):
        app = create_app(tmp_path)
        client = TestClient(app)
    r = client.post("/_internal/finished", json={"exit_code": 0})
    assert r.status_code == 400


def test_run_bead_action_spawns_thread(app_client, tmp_path: Path):
    client, _, _ = app_client

    spawn_calls: list[tuple] = []

    def fake_spawn_run(bead_id, profile, model, effort):
        spawn_calls.append((bead_id, profile, model, effort))

    # Reach into the closure: the easiest way to assert is to patch run_bead.
    with patch.object(server_mod, "run_bead") as mock_run_bead:
        # Make run_bead block briefly so the thread is "active" at redirect-time
        import threading
        def slow_run(opts, log=None):
            threading.Event().wait(0.05)
        mock_run_bead.side_effect = slow_run

        r = client.post(
            "/actions/run-bead/awt-test.1",
            data={"profile": "balanced", "model": "", "effort": ""},
            follow_redirects=False,
        )
    assert r.status_code == 303
    assert r.headers["location"] == "/bead/awt-test.1"
    assert mock_run_bead.called


def test_run_bead_action_rejects_unknown_profile(app_client):
    client, _, _ = app_client
    r = client.post(
        "/actions/run-bead/awt-test.1",
        data={"profile": "no-such-profile"},
    )
    assert r.status_code == 400


def test_kill_writes_synthetic_fallback_and_kills_window(app_client, tmp_path: Path):
    client, _, fake_tmux = app_client
    fake_tmux.window_exists.return_value = True

    r = client.post("/actions/kill/awt-test.1", follow_redirects=False)
    assert r.status_code == 303
    fake_tmux.kill_window.assert_called_once()
    fb = tmp_path / ".beads/workflow/runner-finished/awt-test.1.json"
    assert fb.exists()
    data = json.loads(fb.read_text(encoding="utf-8"))
    assert data["sentinel_status"] == "blocked"
    assert data["blocker_class"] == "env"
