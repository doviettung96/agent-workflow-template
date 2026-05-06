from __future__ import annotations

import json
import subprocess
from unittest.mock import patch

import pytest

from harbor.beads import Beads, BeadsError


def _completed(returncode: int = 0, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


def test_show_unwraps_list():
    b = Beads()
    payload = {"id": "awt-zmq.1", "status": "open", "title": "scaffold"}

    def fake_run(argv, **kwargs):
        assert argv[0] == "br"
        assert argv[1:5] == ["show", "awt-zmq.1", "--json", "--no-db"]
        return _completed(stdout=json.dumps([payload]))

    with patch("harbor.beads.subprocess.run", side_effect=fake_run):
        assert b.show("awt-zmq.1") == payload


def test_show_accepts_dict_for_forward_compat():
    b = Beads()
    payload = {"id": "x", "status": "open"}

    def fake_run(argv, **kwargs):
        return _completed(stdout=json.dumps(payload))

    with patch("harbor.beads.subprocess.run", side_effect=fake_run):
        assert b.show("x") == payload


def test_show_raises_on_empty_list():
    b = Beads()

    def fake_run(argv, **kwargs):
        return _completed(stdout="[]")

    with patch("harbor.beads.subprocess.run", side_effect=fake_run):
        with pytest.raises(BeadsError):
            b.show("missing")


def test_ready_with_parent_passes_flag():
    b = Beads()
    captured: list[list[str]] = []

    def fake_run(argv, **kwargs):
        captured.append(argv)
        return _completed(stdout="[]")

    with patch("harbor.beads.subprocess.run", side_effect=fake_run):
        assert b.ready("epic-1") == []

    argv = captured[0]
    assert "--parent" in argv
    assert argv[argv.index("--parent") + 1] == "epic-1"


def test_ready_without_parent_omits_flag():
    b = Beads()
    captured: list[list[str]] = []

    def fake_run(argv, **kwargs):
        captured.append(argv)
        return _completed(stdout="[]")

    with patch("harbor.beads.subprocess.run", side_effect=fake_run):
        b.ready()

    assert "--parent" not in captured[0]


def test_ready_handles_dict_envelope():
    b = Beads()

    def fake_run(argv, **kwargs):
        return _completed(stdout=json.dumps({"issues": [{"id": "a"}, {"id": "b"}]}))

    with patch("harbor.beads.subprocess.run", side_effect=fake_run):
        out = b.ready()
    assert [i["id"] for i in out] == ["a", "b"]


def test_ready_handles_empty_output():
    b = Beads()

    def fake_run(argv, **kwargs):
        return _completed(stdout="")

    with patch("harbor.beads.subprocess.run", side_effect=fake_run):
        assert b.ready() == []


def test_update_status_invokes_correct_argv():
    b = Beads()
    captured: list[list[str]] = []

    def fake_run(argv, **kwargs):
        captured.append(argv)
        return _completed()

    with patch("harbor.beads.subprocess.run", side_effect=fake_run):
        b.update_status("awt-zmq.1", "in_progress")

    assert captured[0] == ["br", "update", "awt-zmq.1", "--status", "in_progress", "--no-db"]


def test_close_with_reason_appends_flag():
    b = Beads()
    captured: list[list[str]] = []

    def fake_run(argv, **kwargs):
        captured.append(argv)
        return _completed()

    with patch("harbor.beads.subprocess.run", side_effect=fake_run):
        b.close("awt-zmq.1", reason="verified")

    argv = captured[0]
    assert argv[:4] == ["br", "close", "awt-zmq.1", "--no-db"]
    assert "--reason" in argv
    assert argv[argv.index("--reason") + 1] == "verified"


def test_failure_raises_beads_error_with_context():
    b = Beads()

    def fake_run(argv, **kwargs):
        return _completed(returncode=1, stderr="not found")

    with patch("harbor.beads.subprocess.run", side_effect=fake_run):
        with pytest.raises(BeadsError) as ei:
            b.show("missing")
    assert ei.value.returncode == 1
    assert "not found" in str(ei.value)
