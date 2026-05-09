from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

import harbor.webui.server as server_mod
from harbor.webui.server import create_app


def _fake_beads() -> MagicMock:
    fake_beads = MagicMock()
    fake_beads.ready.return_value = [
        {"id": "awt-test.1", "title": "Sample bead", "issue_type": "task", "priority": 2},
    ]
    fake_beads.list_in_progress.return_value = []
    return fake_beads


def test_setup_disabled_without_flag(tmp_path: Path):
    client = TestClient(create_app(tmp_path, allow_config_edit=False))
    assert client.get("/setup").status_code == 404
    assert client.post("/actions/profile/init-from-builtins").status_code == 404


def test_setup_init_save_and_reload_round_trip(tmp_path: Path):
    fake_tmux = MagicMock()
    fake_tmux.attach_command.return_value = "tmux -L harbor attach -t harbor-X-awt-test_1"
    with patch.object(server_mod, "Beads", return_value=_fake_beads()), \
         patch.object(server_mod, "Tmux", return_value=fake_tmux):
        client = TestClient(create_app(tmp_path, allow_config_edit=True))

        setup = client.get("/setup")
        assert setup.status_code == 200
        assert "No <code>harbor.yml</code> exists" in setup.text
        assert "balanced" in setup.text
        assert "disabled" in setup.text

        init = client.post("/actions/profile/init-from-builtins", follow_redirects=False)
        assert init.status_code == 303
        cfg_path = tmp_path / "harbor.yml"
        assert cfg_path.exists()
        assert "claude-opus" in cfg_path.read_text(encoding="utf-8")

        save = client.post(
            "/actions/profile/save",
            data={
                "default_profile": "custom",
                "default_shell": "/bin/bash",
                "profile_name": "custom",
                "profile_custom_agent_kind": "codex",
                "profile_custom_command": '["codex"]',
                "profile_custom_args_template": '["-m", "{model}", "--reasoning-effort", "{effort}"]',
                "profile_custom_model": "gpt-test",
                "profile_custom_effort": "high",
                "profile_custom_prompt_injection": "prompt_arg",
                "profile_custom_launch_template": "codex -m {model} @'{prompt_path}'",
                "_action": "save",
            },
            follow_redirects=False,
        )
        assert save.status_code == 303
        written = cfg_path.read_text(encoding="utf-8")
        assert "default_profile: custom" in written
        assert "model: gpt-test" in written
        assert (tmp_path / "harbor.yml.bak").exists()

        dashboard = client.get("/")
        assert dashboard.status_code == 200
        assert '<option value="custom" selected>custom</option>' in dashboard.text
