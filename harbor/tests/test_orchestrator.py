from __future__ import annotations

import json
from itertools import count
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from harbor.orchestrator import (
    FALLBACK_DIR,
    PROMPTS_DIR,
    RunBeadOptions,
    inject_prompt,
    parse_files_section,
    run_bead,
    session_name_for,
    window_name_for,
)


# ---------- pure helpers ----------

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


def test_window_name_for_replaces_dots():
    """tmux's target syntax uses `.` as the pane separator, so a bead-id like
    `awt-zmq.99` would otherwise mistarget. Sanitization keeps the bead-id
    intact for state but gives tmux a safe window name."""
    assert window_name_for("awt-zmq.99") == "awt-zmq_99"
    assert window_name_for("plain") == "plain"
    assert window_name_for("a.b.c") == "a_b_c"


# ---------- prompt injection ----------

def test_inject_prompt_file_ref_types_at_path(tmp_path: Path):
    from harbor.agent import AgentProfile

    profile = AgentProfile(
        name="p", agent_kind="codex", command=["codex"], args_template=[],
        prompt_injection="file_ref",
    )
    fake_tmux = MagicMock()
    prompt_path = tmp_path / "prompt.md"
    prompt_path.write_text("hi", encoding="utf-8")

    inject_prompt(fake_tmux, "sess", "win", profile, "ignored body", prompt_path)

    fake_tmux.send_keys.assert_called_once()
    args, _ = fake_tmux.send_keys.call_args
    # send_keys(session, window, "@<absolute-posix-path>")
    assert args[0] == "sess" and args[1] == "win"
    assert args[2].startswith("@")
    assert prompt_path.resolve().as_posix() in args[2]
    fake_tmux.send_keys_literal.assert_not_called()


def test_inject_prompt_send_keys_pastes_body(tmp_path: Path):
    from harbor.agent import AgentProfile

    profile = AgentProfile(
        name="p", agent_kind="custom", command=["fake"], args_template=[],
        prompt_injection="send_keys",
    )
    fake_tmux = MagicMock()
    inject_prompt(fake_tmux, "s", "w", profile, "line1\nline2", tmp_path / "x.md")

    fake_tmux.send_keys_literal.assert_called_once_with("s", "w", "line1\nline2", enter=True)
    fake_tmux.send_keys.assert_not_called()


def test_inject_prompt_stdin_rejected_for_interactive():
    from harbor.agent import AgentProfile

    profile = AgentProfile(
        name="p", agent_kind="codex", command=["codex"], args_template=[],
        prompt_injection="stdin",
    )
    fake_tmux = MagicMock()
    with pytest.raises(ValueError, match="stdin"):
        inject_prompt(fake_tmux, "s", "w", profile, "body", Path("x.md"))


def test_inject_prompt_prompt_arg_is_noop(tmp_path: Path):
    """For prompt_arg profiles the prompt rode in on the launch command — there
    is nothing to inject afterwards."""
    from harbor.agent import AgentProfile

    profile = AgentProfile(
        name="p", agent_kind="codex", command=["codex"], args_template=[],
        prompt_injection="prompt_arg",
        launch_template="codex (Get-Content -Raw '{prompt_path}')",
    )
    fake_tmux = MagicMock()
    inject_prompt(fake_tmux, "s", "w", profile, "body", tmp_path / "x.md")
    fake_tmux.send_keys.assert_not_called()
    fake_tmux.send_keys_literal.assert_not_called()


def test_launch_agent_uses_launch_template_when_set(tmp_path: Path):
    from harbor.agent import AgentProfile
    from harbor.orchestrator import launch_agent

    profile = AgentProfile(
        name="codex-fast", agent_kind="codex", command=["codex"], args_template=[],
        model="gpt-5.5", effort="low",
        prompt_injection="prompt_arg",
        launch_template=(
            "codex -m {model} -c model_reasoning_effort={effort} --no-alt-screen "
            "(Get-Content -Raw '{prompt_path}')"
        ),
    )
    prompt_path = tmp_path / "p.md"
    prompt_path.write_text("hi", encoding="utf-8")
    fake_tmux = MagicMock()

    cmd = launch_agent(fake_tmux, "s", "w", profile, None, None, prompt_path)

    assert "codex -m gpt-5.5" in cmd
    assert "model_reasoning_effort=low" in cmd
    assert "--no-alt-screen" in cmd
    assert prompt_path.resolve().as_posix() in cmd
    fake_tmux.send_keys.assert_called_once_with("s", "w", cmd)


def test_launch_agent_falls_back_to_argv_when_no_launch_template(tmp_path: Path):
    from harbor.agent import AgentProfile
    from harbor.orchestrator import launch_agent

    profile = AgentProfile(
        name="x", agent_kind="claude", command=["claude"],
        args_template=["--model", "{model}"],
        model="claude-opus-4-7",
    )
    fake_tmux = MagicMock()
    cmd = launch_agent(fake_tmux, "s", "w", profile, None, None, tmp_path / "p.md")
    assert cmd == "claude --model claude-opus-4-7"
    fake_tmux.send_keys.assert_called_once_with("s", "w", cmd)


# ---------- run_bead end-to-end (mocked tmux + br + mail) ----------

@pytest.fixture
def bead_payload():
    return {
        "id": "awt-test.5",
        "status": "open",
        "title": "smoke",
        "description": (
            "Read:\n- README\n\nFiles:\n- harbor/x.py\n\nVerify:\n- echo verify-ok\n"
        ),
    }


def _make_pane_with_sentinel(bead_id: str, status: str, classification: str) -> str:
    return (
        "[agent prelude]\n"
        f"... did some work on {bead_id} ...\n"
        f"HARBOR-DONE: {bead_id} status={status} classification={classification}\n"
    )


def _capture_pane_sequence(*panes: str):
    """Build a side_effect for capture_pane that returns each pane in order, and
    keeps yielding the last one once exhausted."""
    panes_list = list(panes)

    def _se(*_args, **_kwargs):
        if len(panes_list) > 1:
            return panes_list.pop(0)
        return panes_list[0]
    return _se


def test_run_bead_happy_path(tmp_path: Path, bead_payload, monkeypatch):
    monkeypatch.chdir(tmp_path)

    fake_beads = MagicMock()
    fake_beads.show.return_value = bead_payload
    fake_beads.update_status.return_value = None
    fake_beads.close.return_value = None

    fake_tmux_instance = MagicMock()
    fake_tmux_instance.attach_command.return_value = "tmux -L harbor attach -t harbor-X-awt-test_5"
    fake_tmux_instance.has_session.return_value = True
    # The first poll already sees the sentinel.
    fake_tmux_instance.capture_pane.side_effect = _capture_pane_sequence(
        _make_pane_with_sentinel("awt-test.5", "ok", "none"),
    )

    with (
        patch("harbor.orchestrator.Beads", return_value=fake_beads),
        patch("harbor.orchestrator.Mail", MagicMock()),
        patch("harbor.orchestrator.Tmux", return_value=fake_tmux_instance),
        patch("harbor.orchestrator.run_verify") as fake_verify,
    ):
        fake_verify.return_value = MagicMock(success=True, skipped=False, render_summary=lambda: "ok")
        opts = RunBeadOptions(
            bead_id="awt-test.5",
            repo_root=tmp_path,
            poll_interval_s=0.01,
            timeout_s=5.0,
            agent_startup_delay_s=0.0,
        )
        result = run_bead(opts, log=lambda *a, **k: None)

    assert result.sentinel_status == "ok"
    assert result.exit_code == 0
    assert result.closed is True
    fake_beads.update_status.assert_called_once_with("awt-test.5", "in_progress")
    fake_beads.close.assert_called_once_with("awt-test.5")
    # Per-bead-session model: ensure_session is the spawn step, no new_window.
    fake_tmux_instance.ensure_session.assert_called_once()
    assert fake_tmux_instance.send_keys.call_count >= 1  # agent CLI launch
    fake_tmux_instance.capture_pane.assert_called()
    # Prompt file should have been persisted.
    prompt_path = tmp_path / PROMPTS_DIR / "awt-test.5.md"
    assert prompt_path.exists()
    assert "awt-test.5" in prompt_path.read_text(encoding="utf-8")


def test_run_bead_blocker_marks_stuck_then_recovers_on_reemission(
    tmp_path: Path, bead_payload, monkeypatch
):
    """Sentinel #1 is blocked → run records `stuck` and keeps polling.
    Sentinel #2 is ok → run runs verify, closes the bead, exits."""
    monkeypatch.chdir(tmp_path)
    bead_payload = {**bead_payload, "id": "awt-test.6"}

    fake_beads = MagicMock()
    fake_beads.show.return_value = bead_payload
    fake_beads.update_status.return_value = None
    fake_beads.close.return_value = None

    fake_tmux_instance = MagicMock()
    fake_tmux_instance.attach_command.return_value = "<attach>"
    fake_tmux_instance.has_session.return_value = True
    fake_tmux_instance.capture_pane.side_effect = _capture_pane_sequence(
        # Iteration 1: just the blocked sentinel
        _make_pane_with_sentinel("awt-test.6", "blocked", "clarify"),
        # Iteration 2: still only the same sentinel (count unchanged → no-op)
        _make_pane_with_sentinel("awt-test.6", "blocked", "clarify"),
        # Iteration 3: agent re-emits ok after the (imagined) clarification
        _make_pane_with_sentinel("awt-test.6", "blocked", "clarify")
        + _make_pane_with_sentinel("awt-test.6", "ok", "none"),
    )

    with (
        patch("harbor.orchestrator.Beads", return_value=fake_beads),
        patch("harbor.orchestrator.Mail", MagicMock()),
        patch("harbor.orchestrator.Tmux", return_value=fake_tmux_instance),
        patch("harbor.orchestrator.run_verify") as fake_verify,
    ):
        fake_verify.return_value = MagicMock(success=True, skipped=False, render_summary=lambda: "ok")
        opts = RunBeadOptions(
            bead_id="awt-test.6",
            repo_root=tmp_path,
            poll_interval_s=0.005,
            timeout_s=5.0,
            agent_startup_delay_s=0.0,
        )
        result = run_bead(opts, log=lambda *a, **k: None)

    assert result.sentinel_status == "ok"
    assert result.closed is True
    fake_beads.close.assert_called_once_with("awt-test.6")

    # The stuck record should have been written before the resume; assert via state file.
    state_json = tmp_path / ".beads/workflow/state.json"
    assert state_json.exists()


def test_run_bead_blocked_pane_left_alive_when_no_reemission(
    tmp_path: Path, bead_payload, monkeypatch
):
    """If the agent only emits a blocker and never recovers, run_bead times out
    but leaves the pane alive and the bead open."""
    monkeypatch.chdir(tmp_path)
    bead_payload = {**bead_payload, "id": "awt-test.7"}

    fake_beads = MagicMock()
    fake_beads.show.return_value = bead_payload
    fake_beads.update_status.return_value = None
    fake_beads.close.return_value = None

    fake_tmux_instance = MagicMock()
    fake_tmux_instance.attach_command.return_value = "<attach>"
    fake_tmux_instance.has_session.return_value = True
    fake_tmux_instance.capture_pane.return_value = _make_pane_with_sentinel(
        "awt-test.7", "blocked", "contract"
    )

    with (
        patch("harbor.orchestrator.Beads", return_value=fake_beads),
        patch("harbor.orchestrator.Mail", MagicMock()),
        patch("harbor.orchestrator.Tmux", return_value=fake_tmux_instance),
    ):
        opts = RunBeadOptions(
            bead_id="awt-test.7",
            repo_root=tmp_path,
            poll_interval_s=0.005,
            timeout_s=0.05,  # tiny — force timeout
            agent_startup_delay_s=0.0,
        )
        result = run_bead(opts, log=lambda *a, **k: None)

    assert result.closed is False
    fake_beads.close.assert_not_called()
    # Session not killed by harbor (keep_pane_after_finish default True; and
    # blocker path never auto-kills).
    fake_tmux_instance.kill_session.assert_not_called()


def test_run_bead_handles_kill_signal(tmp_path: Path, bead_payload, monkeypatch):
    """Webview /actions/kill writes a synthetic JSON to runner-finished. The
    orchestrator should pick it up and exit with the encoded blocker."""
    monkeypatch.chdir(tmp_path)
    bead_payload = {**bead_payload, "id": "awt-test.8"}

    fake_beads = MagicMock()
    fake_beads.show.return_value = bead_payload
    fake_tmux_instance = MagicMock()
    fake_tmux_instance.attach_command.return_value = "<attach>"
    fake_tmux_instance.has_session.return_value = True
    # Empty pane — no sentinel
    fake_tmux_instance.capture_pane.return_value = "agent running...\n"

    # Drop the kill-signal file BEFORE run_bead starts polling.
    target = tmp_path / FALLBACK_DIR
    target.mkdir(parents=True, exist_ok=True)

    def ensure_session_se(session, cwd, *, default_shell=None):
        # Simulate user clicking 'kill' immediately after the session spawns.
        # The kill-signal file is keyed on bead_id, matching how the webview
        # writes it.
        bead_id = "awt-test.8"
        (target / f"{bead_id}.json").write_text(
            json.dumps(
                {
                    "bead_id": bead_id, "exit_code": 137,
                    "sentinel_status": "blocked", "blocker_class": "env",
                    "last_output": "(killed by webui)",
                }
            ),
            encoding="utf-8",
        )

    fake_tmux_instance.ensure_session.side_effect = ensure_session_se

    with (
        patch("harbor.orchestrator.Beads", return_value=fake_beads),
        patch("harbor.orchestrator.Mail", MagicMock()),
        patch("harbor.orchestrator.Tmux", return_value=fake_tmux_instance),
    ):
        opts = RunBeadOptions(
            bead_id="awt-test.8",
            repo_root=tmp_path,
            poll_interval_s=0.005,
            timeout_s=5.0,
            agent_startup_delay_s=0.0,
        )
        result = run_bead(opts, log=lambda *a, **k: None)

    assert result.closed is False
    assert result.sentinel_status == "blocked"
    assert result.blocker_class == "env"


def test_run_bead_window_disappearance_aborts(tmp_path: Path, bead_payload, monkeypatch):
    monkeypatch.chdir(tmp_path)
    bead_payload = {**bead_payload, "id": "awt-test.9"}

    fake_beads = MagicMock()
    fake_beads.show.return_value = bead_payload
    fake_tmux_instance = MagicMock()
    fake_tmux_instance.attach_command.return_value = "<attach>"

    # Session initially exists (so we get past start), then "dies".
    exists_calls = count()

    def has_session(_s):
        return next(exists_calls) < 1

    fake_tmux_instance.has_session.side_effect = has_session
    fake_tmux_instance.capture_pane.return_value = "still warming up...\n"

    with (
        patch("harbor.orchestrator.Beads", return_value=fake_beads),
        patch("harbor.orchestrator.Mail", MagicMock()),
        patch("harbor.orchestrator.Tmux", return_value=fake_tmux_instance),
    ):
        opts = RunBeadOptions(
            bead_id="awt-test.9",
            repo_root=tmp_path,
            poll_interval_s=0.005,
            timeout_s=5.0,
            agent_startup_delay_s=0.0,
        )
        result = run_bead(opts, log=lambda *a, **k: None)

    assert result.closed is False
    assert result.sentinel_status == "blocked"
    assert result.blocker_class == "env"


def test_run_bead_clears_stale_kill_signal(tmp_path: Path, bead_payload, monkeypatch):
    """A leftover runner-finished/<id>.json from a prior run must not short-circuit."""
    monkeypatch.chdir(tmp_path)
    bead_payload = {**bead_payload, "id": "awt-test.10"}

    target = tmp_path / FALLBACK_DIR
    target.mkdir(parents=True, exist_ok=True)
    stale = target / "awt-test.10.json"
    stale.write_text(
        json.dumps({"bead_id": "awt-test.10", "sentinel_status": "blocked", "blocker_class": "env"}),
        encoding="utf-8",
    )

    fake_beads = MagicMock()
    fake_beads.show.return_value = bead_payload
    fake_tmux_instance = MagicMock()
    fake_tmux_instance.attach_command.return_value = "<attach>"
    fake_tmux_instance.has_session.return_value = True
    # Sentinel emitted on first poll so run completes naturally.
    fake_tmux_instance.capture_pane.return_value = _make_pane_with_sentinel(
        "awt-test.10", "ok", "none"
    )

    with (
        patch("harbor.orchestrator.Beads", return_value=fake_beads),
        patch("harbor.orchestrator.Mail", MagicMock()),
        patch("harbor.orchestrator.Tmux", return_value=fake_tmux_instance),
        patch("harbor.orchestrator.run_verify") as fake_verify,
    ):
        fake_verify.return_value = MagicMock(success=True, skipped=False, render_summary=lambda: "ok")
        opts = RunBeadOptions(
            bead_id="awt-test.10",
            repo_root=tmp_path,
            poll_interval_s=0.005,
            timeout_s=5.0,
            agent_startup_delay_s=0.0,
        )
        result = run_bead(opts, log=lambda *a, **k: None)

    # Stale kill should have been removed at run start, so we got the ok exit.
    assert result.closed is True
    assert result.sentinel_status == "ok"


def test_run_bead_rejects_already_closed_bead(tmp_path: Path):
    fake_beads = MagicMock()
    fake_beads.show.return_value = {"id": "x", "status": "closed", "description": ""}

    with patch("harbor.orchestrator.Beads", return_value=fake_beads):
        opts = RunBeadOptions(bead_id="x", repo_root=tmp_path)
        with pytest.raises(RuntimeError, match="status=closed"):
            run_bead(opts, log=lambda *a, **k: None)
