from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from harbor.verify import (
    VerifyCommandResult,
    VerifyResult,
    parse_verify_commands,
    run_verify,
)


def test_parse_verify_commands_extracts_dash_lines():
    desc = (
        "Read:\n- foo\n\n"
        "Files:\n- harbor/x.py\n\n"
        "Verify:\n"
        "- python -m pytest harbor/tests/test_x.py\n"
        "- echo done\n\n"
        "Risk: low.\n"
    )
    cmds = parse_verify_commands(desc)
    assert cmds == [
        "python -m pytest harbor/tests/test_x.py",
        "echo done",
    ]


def test_parse_verify_commands_skips_manual_lines():
    desc = (
        "Verify:\n"
        "- Manual: open the webview and click run\n"
        "- python -m pytest tests/\n"
        "- (manual) confirm window appears in tmux\n"
    )
    assert parse_verify_commands(desc) == ["python -m pytest tests/"]


def test_parse_verify_commands_skips_sentence_descriptions():
    desc = (
        "Verify:\n"
        "- All six confirms above pass.\n"
        "- harbor/docs/PHASE1-VALIDATION.md committed.\n"
    )
    # Both end with periods and contain no shell metachars -> documentation
    assert parse_verify_commands(desc) == []


def test_parse_verify_commands_returns_empty_when_no_section():
    assert parse_verify_commands("Read:\n- x\n") == []
    assert parse_verify_commands("") == []


def test_run_verify_skipped_when_no_commands(tmp_path: Path):
    bead = {"description": "Read:\n- x\n"}
    result = run_verify(bead, tmp_path)
    assert result.skipped is True
    assert result.success is False
    assert "no executable commands" in result.render_summary()


def test_run_verify_success_via_target_runtime(tmp_path: Path):
    """Stub out subprocess.run inside verify._route_command so we don't need a
    real target_runtime.py installed in tmp_path. The fallback path runs `sh -c`
    directly when the script is missing — that's what we exercise here."""
    desc = "Verify:\n- echo hello\n- exit 0\n"
    bead = {"description": desc}
    result = run_verify(bead, tmp_path)
    assert result.success is True
    assert all(c.ok for c in result.commands)


def test_run_verify_first_failure_marks_overall_failure(tmp_path: Path):
    desc = "Verify:\n- echo before\n- exit 7\n- echo after\n"
    bead = {"description": desc}
    result = run_verify(bead, tmp_path)
    assert result.success is False
    # All three should still have been attempted
    assert len(result.commands) == 3
    assert result.commands[0].ok is True
    assert result.commands[1].ok is False
    assert result.commands[1].exit_code == 7
