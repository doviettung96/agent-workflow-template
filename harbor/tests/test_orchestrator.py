from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from harbor.orchestrator import (
    FALLBACK_DIR,
    RunBeadOptions,
    parse_files_section,
    run_bead,
    session_name_for,
)


def test_session_name_is_stable_per_repo(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    n1 = session_name_for(a)
    n2 = session_name_for(a)
    n3 = session_name_for(b)
    assert n1 == n2  # stable
    assert n1 != n3  # path-distinct
    assert n1.startswith("harbor-")


def test_parse_files_section_lists_paths():
    desc = (
        "Read:\n- README.md\n\n"
        "Files:\n- harbor/x.py\n- harbor/y.py (helper)\n\n"
        "Verify:\n- echo done\n"
    )
    assert parse_files_section(desc) == ["harbor/x.py", "harbor/y.py"]


def test_parse_files_section_empty_when_missing():
    assert parse_files_section("Read:\n- foo\n") == []


def test_run_bead_happy_path(tmp_path: Path, monkeypatch):
    """End-to-end orchestration with mocked tmux + br + mail.

    The runner-side write of the fallback file is simulated by a stand-in
    that drops the JSON the moment new_window is invoked, so the orchestrator
    sees it on its first poll.
    """
    monkeypatch.chdir(tmp_path)

    bead_payload = {
        "id": "awt-test.5",
        "status": "open",
        "title": "smoke",
        "description": (
            "Read:\n- README\n\nFiles:\n- harbor/x.py\n\nVerify:\n- echo verify-ok\n"
        ),
    }

    fake_beads = MagicMock()
    fake_beads.show.return_value = bead_payload
    fake_beads.update_status.return_value = None
    fake_beads.close.return_value = None

    fake_mail_instance = MagicMock()
    fake_mail_class = MagicMock(return_value=fake_mail_instance)

    fake_tmux_instance = MagicMock()
    fake_tmux_instance.attach_command.return_value = "tmux -L harbor attach -t harbor-X:awt-test.5"

    def new_window_side_effect(session, window, cwd, command):
        # Pretend the runner did its job and dropped the fallback file.
        target_dir = tmp_path / FALLBACK_DIR
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / f"{window}.json").write_text(
            json.dumps(
                {
                    "bead_id": window,
                    "exit_code": 0,
                    "sentinel_status": "ok",
                    "blocker_class": "none",
                    "last_output": "did the work\nHARBOR-DONE: awt-test.5 status=ok classification=none",
                    "profile": "balanced",
                    "model": "gpt-5.3-codex",
                    "effort": "medium",
                }
            ),
            encoding="utf-8",
        )

    fake_tmux_instance.new_window.side_effect = new_window_side_effect

    with (
        patch("harbor.orchestrator.Beads", return_value=fake_beads),
        patch("harbor.orchestrator.Mail", fake_mail_class),
        patch("harbor.orchestrator.Tmux", return_value=fake_tmux_instance),
    ):
        opts = RunBeadOptions(
            bead_id="awt-test.5",
            repo_root=tmp_path,
            poll_interval_s=0.05,
            timeout_s=5.0,
        )
        result = run_bead(opts, log=lambda *a, **k: None)

    assert result.sentinel_status == "ok"
    assert result.exit_code == 0
    assert result.closed is True
    fake_beads.update_status.assert_called_once_with("awt-test.5", "in_progress")
    fake_beads.close.assert_called_once_with("awt-test.5")
    fake_tmux_instance.new_window.assert_called_once()


def test_run_bead_blocker_does_not_close(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    bead_payload = {
        "id": "awt-test.6",
        "status": "open",
        "title": "blocked-case",
        "description": "Read:\n- x\n\nFiles:\n- y\n\nVerify:\n- echo ok\n",
    }
    fake_beads = MagicMock()
    fake_beads.show.return_value = bead_payload
    fake_beads.update_status.return_value = None
    fake_beads.close.return_value = None

    fake_tmux_instance = MagicMock()
    fake_tmux_instance.attach_command.return_value = "<attach>"

    def new_window_side_effect(session, window, cwd, command):
        target_dir = tmp_path / FALLBACK_DIR
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / f"{window}.json").write_text(
            json.dumps(
                {
                    "bead_id": window,
                    "exit_code": 1,
                    "sentinel_status": "blocked",
                    "blocker_class": "contract",
                    "last_output": "needs more info",
                    "profile": "balanced",
                }
            ),
            encoding="utf-8",
        )

    fake_tmux_instance.new_window.side_effect = new_window_side_effect

    with (
        patch("harbor.orchestrator.Beads", return_value=fake_beads),
        patch("harbor.orchestrator.Mail", MagicMock()),
        patch("harbor.orchestrator.Tmux", return_value=fake_tmux_instance),
    ):
        opts = RunBeadOptions(
            bead_id="awt-test.6",
            repo_root=tmp_path,
            poll_interval_s=0.05,
            timeout_s=5.0,
        )
        result = run_bead(opts, log=lambda *a, **k: None)

    assert result.sentinel_status == "blocked"
    assert result.blocker_class == "contract"
    assert result.closed is False
    fake_beads.close.assert_not_called()


def test_run_bead_rejects_already_closed_bead(tmp_path: Path):
    fake_beads = MagicMock()
    fake_beads.show.return_value = {"id": "x", "status": "closed", "description": ""}

    with patch("harbor.orchestrator.Beads", return_value=fake_beads):
        opts = RunBeadOptions(bead_id="x", repo_root=tmp_path)
        with pytest.raises(RuntimeError, match="status=closed"):
            run_bead(opts, log=lambda *a, **k: None)
