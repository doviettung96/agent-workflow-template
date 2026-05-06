"""Unit tests for harbor.tmux. subprocess.run is mocked so tests don't need a real tmux."""
from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest

from harbor.tmux import DEFAULT_SERVER, Tmux, TmuxError


def _completed(returncode: int = 0, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


def test_default_server_is_harbor():
    assert Tmux().server == "harbor"
    assert DEFAULT_SERVER == "harbor"


def test_ensure_session_creates_when_missing():
    t = Tmux()
    calls: list[list[str]] = []

    def fake_run(argv, **kwargs):
        calls.append(argv)
        if argv[3] == "has-session":
            return _completed(returncode=1)
        return _completed(returncode=0)

    with patch("harbor.tmux.subprocess.run", side_effect=fake_run):
        t.ensure_session("s1", "/tmp/repo")

    assert calls[0][:4] == ["tmux", "-L", "harbor", "has-session"]
    assert calls[1][:4] == ["tmux", "-L", "harbor", "new-session"]
    assert "-d" in calls[1] and "-A" in calls[1]
    assert "-s" in calls[1] and "s1" in calls[1]
    assert "-c" in calls[1] and "/tmp/repo" in calls[1]


def test_ensure_session_skips_when_exists():
    t = Tmux()
    calls: list[list[str]] = []

    def fake_run(argv, **kwargs):
        calls.append(argv)
        return _completed(returncode=0)  # has-session succeeds

    with patch("harbor.tmux.subprocess.run", side_effect=fake_run):
        t.ensure_session("already", "/tmp")

    assert len(calls) == 1  # only has-session, no new-session
    assert calls[0][3] == "has-session"


def test_new_window_then_send_keys():
    """new_window opens an empty pane then types the command via send-keys.
    Works on both real tmux and Windows psmux (which doesn't accept a command
    argument on new-window)."""
    t = Tmux()
    captured: list[list[str]] = []

    def fake_run(argv, **kwargs):
        captured.append(argv)
        return _completed()

    with patch("harbor.tmux.subprocess.run", side_effect=fake_run):
        t.new_window("sess", "bead-7", "/repo", "harbor-bead-runner bead-7")

    # First call: new-window without command
    argv0 = captured[0]
    assert argv0[3:5] == ["new-window", "-d"]
    assert argv0[5:7] == ["-t", "sess:"]
    assert argv0[7:9] == ["-n", "bead-7"]
    assert argv0[9:11] == ["-c", "/repo"]
    assert "sh" not in argv0  # no shell-command tail

    # Second call: send-keys with the command + Enter
    argv1 = captured[1]
    assert argv1[3] == "send-keys"
    assert argv1[5] == "sess:bead-7"
    assert argv1[6] == "harbor-bead-runner bead-7"
    assert argv1[-1] == "Enter"


def test_new_window_skips_send_keys_when_command_empty():
    t = Tmux()
    captured: list[list[str]] = []

    def fake_run(argv, **kwargs):
        captured.append(argv)
        return _completed()

    with patch("harbor.tmux.subprocess.run", side_effect=fake_run):
        t.new_window("sess", "bead-7", "/repo", "")

    assert len(captured) == 1
    assert captured[0][3] == "new-window"


def test_window_exists_parses_list():
    t = Tmux()

    def fake_run(argv, **kwargs):
        return _completed(stdout="alpha\nbeta\nbead-3\n")

    with patch("harbor.tmux.subprocess.run", side_effect=fake_run):
        assert t.window_exists("s", "bead-3") is True
        assert t.window_exists("s", "missing") is False


def test_list_windows_parses_pairs():
    t = Tmux()

    def fake_run(argv, **kwargs):
        return _completed(stdout="alpha|@1\nbeta|@2\n\n")

    with patch("harbor.tmux.subprocess.run", side_effect=fake_run):
        assert t.list_windows("s") == [("alpha", "@1"), ("beta", "@2")]


def test_send_keys_appends_enter_by_default():
    t = Tmux()
    captured: list[list[str]] = []

    def fake_run(argv, **kwargs):
        captured.append(argv)
        return _completed()

    with patch("harbor.tmux.subprocess.run", side_effect=fake_run):
        t.send_keys("s", "w", "echo hi")
        t.send_keys("s", "w", "echo no-enter", enter=False)

    assert captured[0][-1] == "Enter"
    assert captured[1][-1] == "echo no-enter"


def test_capture_pane_passes_history_size():
    t = Tmux()
    captured: list[list[str]] = []

    def fake_run(argv, **kwargs):
        captured.append(argv)
        return _completed(stdout="line1\nline2\n")

    with patch("harbor.tmux.subprocess.run", side_effect=fake_run):
        out = t.capture_pane("s", "w", lines=50)

    assert out == "line1\nline2\n"
    assert "-S" in captured[0]
    assert "-50" in captured[0]


def test_kill_window_uses_session_window_target():
    t = Tmux()
    captured: list[list[str]] = []

    def fake_run(argv, **kwargs):
        captured.append(argv)
        return _completed()

    with patch("harbor.tmux.subprocess.run", side_effect=fake_run):
        t.kill_window("s", "bead-3")

    assert captured[0][3] == "kill-window"
    assert captured[0][5] == "s:bead-3"


def test_attach_command_quotes_server_and_target():
    t = Tmux(server="my server")
    cmd = t.attach_command("epic-1", "bead-3")
    # shlex.quote should wrap the whitespace-containing server name in quotes
    assert "'my server'" in cmd
    assert "epic-1:bead-3" in cmd


def test_run_raises_tmux_error_on_failure():
    t = Tmux()

    def fake_run(argv, **kwargs):
        return _completed(returncode=2, stderr="no such session")

    with patch("harbor.tmux.subprocess.run", side_effect=fake_run):
        with pytest.raises(TmuxError) as ei:
            t._run("kill-session", "-t", "nope")
    assert "no such session" in str(ei.value)
    assert ei.value.returncode == 2
