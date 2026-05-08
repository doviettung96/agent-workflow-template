from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


TEMPLATE_ROOT = Path(__file__).resolve().parents[2]


def _assert_harbor_scaffold(repo: Path) -> None:
    assert (repo / "harbor" / "pyproject.toml").is_file()
    assert (repo / "harbor" / "harbor" / "__main__.py").is_file()
    assert (repo / "harbor.yml").is_file()
    assert (repo / "skills" / "build-and-test" / "SKILL.md").is_file()
    assert (repo / "skills" / "review-epic" / "SKILL.md").is_file()


def test_windows_scaffold_ships_harbor(tmp_path: Path) -> None:
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if not shell:
        pytest.skip("PowerShell is not available")

    repo = tmp_path / "windows-downstream"
    repo.mkdir()
    script = TEMPLATE_ROOT / "scripts" / "windows" / "scaffold-repo-files.ps1"

    result = subprocess.run(
        [
            shell,
            "-NoProfile",
            "-File",
            str(script),
            "-RepoPath",
            str(repo),
            "-Prefix",
            "smoke",
            "-Profile",
            "generic",
        ],
        cwd=TEMPLATE_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    _assert_harbor_scaffold(repo)


def test_posix_scaffold_ships_harbor(tmp_path: Path) -> None:
    shell = shutil.which("bash")
    if not shell:
        pytest.skip("bash is not available")
    probe = subprocess.run(
        [shell, "--version"],
        text=True,
        capture_output=True,
        check=False,
    )
    if probe.returncode != 0:
        pytest.skip("bash is present but not usable in this environment")

    repo = tmp_path / "posix-downstream"
    script = TEMPLATE_ROOT / "scripts" / "posix" / "scaffold-repo-files.sh"

    result = subprocess.run(
        [shell, str(script), str(repo), "smoke", "generic"],
        cwd=TEMPLATE_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    _assert_harbor_scaffold(repo)
