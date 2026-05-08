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


def test_dashboard_filters_ready_beads_by_local_issue_prefix(tmp_path: Path):
    beads_dir = tmp_path / ".beads"
    beads_dir.mkdir()
    (beads_dir / "config.yaml").write_text("issue_prefix: awt\n", encoding="utf-8")

    fake_beads = MagicMock()
    fake_beads.ready.return_value = [
        {"id": "awt-test.1", "title": "Local bead", "issue_type": "task", "priority": 2},
        {"id": "vvn-test.1", "title": "Synced bead", "issue_type": "task", "priority": 2},
        {"id": "awt-test.epic", "title": "Local epic", "issue_type": "epic", "priority": 1},
    ]
    fake_tmux = MagicMock()
    fake_tmux.attach_command.return_value = "tmux -L harbor attach -t harbor-XX:awt-test.1"

    with patch.object(server_mod, "Beads", return_value=fake_beads), \
         patch.object(server_mod, "Tmux", return_value=fake_tmux):
        client = TestClient(create_app(tmp_path))
        r = client.get("/")

    assert r.status_code == 200
    assert "awt-test.1" in r.text
    assert "Local bead" in r.text
    assert "vvn-test.1" not in r.text
    assert "showing 1 ready" in r.text
    assert "awt-*" in r.text
    assert "/?prefix=all" in r.text


def test_dashboard_prefix_all_bypasses_local_issue_prefix(tmp_path: Path):
    beads_dir = tmp_path / ".beads"
    beads_dir.mkdir()
    (beads_dir / "config.yaml").write_text("issue_prefix: awt\n", encoding="utf-8")

    fake_beads = MagicMock()
    fake_beads.ready.return_value = [
        {"id": "awt-test.1", "title": "Local bead", "issue_type": "task", "priority": 2},
        {"id": "vvn-test.1", "title": "Synced bead", "issue_type": "task", "priority": 2},
    ]

    with patch.object(server_mod, "Beads", return_value=fake_beads), \
         patch.object(server_mod, "Tmux", return_value=MagicMock()):
        client = TestClient(create_app(tmp_path))
        r = client.get("/?prefix=all")

    assert r.status_code == 200
    assert "awt-test.1" in r.text
    assert "vvn-test.1" in r.text
    assert "showing all 2 ready beads" in r.text
    assert "show awt-* only" in r.text


def test_dashboard_missing_beads_config_shows_all_ready_beads(tmp_path: Path):
    fake_beads = MagicMock()
    fake_beads.ready.return_value = [
        {"id": "awt-test.1", "title": "Local bead", "issue_type": "task", "priority": 2},
        {"id": "vvn-test.1", "title": "Synced bead", "issue_type": "task", "priority": 2},
    ]

    with patch.object(server_mod, "Beads", return_value=fake_beads), \
         patch.object(server_mod, "Tmux", return_value=MagicMock()):
        client = TestClient(create_app(tmp_path))
        r = client.get("/")

    assert r.status_code == 200
    assert "awt-test.1" in r.text
    assert "vvn-test.1" in r.text
    assert "showing all 2 ready beads" in r.text
    assert "/?prefix=all" not in r.text


def test_dashboard_status_partial(app_client):
    client, _, _ = app_client
    r = client.get("/_partials/dashboard-status")
    assert r.status_code == 200
    assert "Workers" in r.text


def test_dashboard_renders_stuck_panel_when_bead_is_stuck(app_client, tmp_path: Path):
    """When StateStore has a stuck bead-run, the dashboard's red 'needs your
    help' panel must surface it. Drives awt-zmq.14 acceptance."""
    from harbor.state import StateStore

    client, _, _ = app_client
    store = StateStore(tmp_path)
    run_id = store.start_run(mode="single", epic_id=None, pid=42)
    store.record_bead_start(
        run_id=run_id, bead_id="awt-stuck.1", profile="balanced",
        model="m", effort="medium", window_name="awt-stuck.1",
    )
    store.record_bead_stuck(
        run_id=run_id, bead_id="awt-stuck.1",
        sentinel_status="blocked", blocker_class="clarify",
    )

    r = client.get("/_partials/dashboard-status")
    assert r.status_code == 200
    assert "Stuck" in r.text
    assert "needs your help" in r.text
    assert "awt-stuck.1" in r.text
    assert "clarify" in r.text


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


def _bead_with_dep(bead_id: str, dep_id: str, dep_status: str) -> tuple[dict, dict]:
    """Build a (bead, blocker_target) pair where `bead_id` has a `blocks`
    dependency on `dep_id` whose target has status=`dep_status`."""
    bead = {
        "id": bead_id,
        "status": "open",
        "title": "Blocked bead",
        "description": "blocked",
        "issue_type": "task",
        "priority": 2,
        "dependencies": [
            {"depends_on_id": dep_id, "type": "blocks"},
        ],
    }
    target = {
        "id": dep_id,
        "status": dep_status,
        "title": "Prereq bead",
        "issue_type": "task",
        "priority": 2,
    }
    return bead, target


def _show_router(beads_by_id: dict[str, dict]):
    """Make fake_beads.show route by id, raising for unknown ids."""
    def _show(bead_id: str) -> dict:
        if bead_id not in beads_by_id:
            raise RuntimeError(f"no such bead {bead_id!r}")
        return beads_by_id[bead_id]
    return _show


def test_run_bead_action_rejects_blocked_bead_without_force(tmp_path: Path):
    bead, target = _bead_with_dep("awt-test.5", "awt-test.4", "open")
    fake_beads = MagicMock()
    fake_beads.show.side_effect = _show_router({"awt-test.5": bead, "awt-test.4": target})
    fake_beads.ready.return_value = []
    fake_tmux = MagicMock()
    fake_tmux.attach_command.return_value = "tmux -L harbor attach -t harbor-X-awt-test_5"

    with patch.object(server_mod, "Beads", return_value=fake_beads), \
         patch.object(server_mod, "Tmux", return_value=fake_tmux), \
         patch.object(server_mod, "run_bead") as mock_run_bead:
        client = TestClient(create_app(tmp_path))
        r = client.post(
            "/actions/run-bead/awt-test.5",
            data={"profile": "balanced"},
            follow_redirects=False,
        )

    assert r.status_code == 409
    assert "blocked by" in r.text
    assert "awt-test.4" in r.text
    assert not mock_run_bead.called


def test_run_bead_action_allows_blocked_bead_with_force(tmp_path: Path):
    bead, target = _bead_with_dep("awt-test.5", "awt-test.4", "open")
    fake_beads = MagicMock()
    fake_beads.show.side_effect = _show_router({"awt-test.5": bead, "awt-test.4": target})
    fake_beads.ready.return_value = []
    fake_tmux = MagicMock()
    fake_tmux.attach_command.return_value = "tmux -L harbor attach -t harbor-X-awt-test_5"

    with patch.object(server_mod, "Beads", return_value=fake_beads), \
         patch.object(server_mod, "Tmux", return_value=fake_tmux), \
         patch.object(server_mod, "run_bead") as mock_run_bead:
        import threading as _threading
        mock_run_bead.side_effect = lambda opts, log=None: _threading.Event().wait(0.05)
        client = TestClient(create_app(tmp_path))
        r = client.post(
            "/actions/run-bead/awt-test.5",
            data={"profile": "balanced", "force": "1"},
            follow_redirects=False,
        )

    assert r.status_code == 303
    assert r.headers["location"] == "/bead/awt-test.5"
    assert mock_run_bead.called


def test_run_bead_action_skips_parent_child_when_checking_blockers(tmp_path: Path):
    """parent-child deps are hierarchy, not runtime ordering — a child should
    still be runnable while its epic parent is open."""
    bead = {
        "id": "awt-test.6",
        "status": "open",
        "title": "Child of open epic",
        "description": "child",
        "issue_type": "task",
        "priority": 2,
        "dependencies": [
            {"depends_on_id": "awt-test.epic", "type": "parent-child"},
        ],
    }
    epic = {"id": "awt-test.epic", "status": "open", "title": "Epic", "issue_type": "epic", "priority": 1}
    fake_beads = MagicMock()
    fake_beads.show.side_effect = _show_router({"awt-test.6": bead, "awt-test.epic": epic})
    fake_beads.ready.return_value = []
    fake_tmux = MagicMock()
    fake_tmux.attach_command.return_value = "tmux -L harbor attach -t harbor-X-awt-test_6"

    with patch.object(server_mod, "Beads", return_value=fake_beads), \
         patch.object(server_mod, "Tmux", return_value=fake_tmux), \
         patch.object(server_mod, "run_bead") as mock_run_bead:
        import threading as _threading
        mock_run_bead.side_effect = lambda opts, log=None: _threading.Event().wait(0.05)
        client = TestClient(create_app(tmp_path))
        r = client.post(
            "/actions/run-bead/awt-test.6",
            data={"profile": "balanced"},
            follow_redirects=False,
        )

    assert r.status_code == 303
    assert mock_run_bead.called


def test_run_bead_action_rejects_closed_bead(tmp_path: Path):
    bead = {
        "id": "awt-test.7",
        "status": "closed",
        "title": "Already done",
        "description": "done",
        "issue_type": "task",
        "priority": 2,
    }
    fake_beads = MagicMock()
    fake_beads.show.return_value = bead
    fake_beads.ready.return_value = []

    with patch.object(server_mod, "Beads", return_value=fake_beads), \
         patch.object(server_mod, "Tmux", return_value=MagicMock()), \
         patch.object(server_mod, "run_bead") as mock_run_bead:
        client = TestClient(create_app(tmp_path))
        r = client.post(
            "/actions/run-bead/awt-test.7",
            data={"profile": "balanced"},
        )

    assert r.status_code == 409
    assert "closed" in r.text
    assert not mock_run_bead.called


def test_bead_detail_renders_blockers_panel(tmp_path: Path):
    bead, target = _bead_with_dep("awt-test.8", "awt-test.7", "in_progress")
    fake_beads = MagicMock()
    fake_beads.show.side_effect = _show_router({"awt-test.8": bead, "awt-test.7": target})
    fake_tmux = MagicMock()
    fake_tmux.attach_command.return_value = "tmux -L harbor attach -t harbor-X-awt-test_8"
    fake_tmux.has_session.return_value = False

    with patch.object(server_mod, "Beads", return_value=fake_beads), \
         patch.object(server_mod, "Tmux", return_value=fake_tmux):
        client = TestClient(create_app(tmp_path))
        r = client.get("/bead/awt-test.8")

    assert r.status_code == 200
    assert "Blocked by unresolved dependencies" in r.text
    assert "awt-test.7" in r.text
    # Force checkbox is rendered
    assert 'name="force"' in r.text


def test_kill_writes_synthetic_fallback_and_kills_session(app_client, tmp_path: Path):
    client, _, fake_tmux = app_client
    fake_tmux.has_session.return_value = True

    r = client.post("/actions/kill/awt-test.1", follow_redirects=False)
    assert r.status_code == 303
    fake_tmux.kill_session.assert_called_once()
    fb = tmp_path / ".beads/workflow/runner-finished/awt-test.1.json"
    assert fb.exists()
    data = json.loads(fb.read_text(encoding="utf-8"))
    assert data["sentinel_status"] == "blocked"
    assert data["blocker_class"] == "env"
