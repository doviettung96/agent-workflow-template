"""Run a bead's `Verify:` commands after the agent reports done.

Verify commands are routed through `scripts/shared/target_runtime.py run --`
so SSH-target deployments work the same as local. We parse the bead
description's `Verify:` block: each `- <cmd>` line is one shell command, except
lines that obviously document a manual check (`Manual:`, `(manual)`, etc.).

If no executable verify commands are present, harbor returns
`VerifyResult.skipped()` so the daemon can decide whether to require human
confirmation in the webview.
"""
from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_SECTION_RE = re.compile(r"^([A-Z][A-Za-z]+):\s*$", re.MULTILINE)
_LIST_LINE_RE = re.compile(r"^\s*-\s+(.+)$")
_MANUAL_PREFIXES = ("manual:", "(manual)", "human:", "by hand:")


@dataclass(frozen=True)
class VerifyCommandResult:
    command: str
    exit_code: int
    stdout: str
    stderr: str
    skipped_reason: str = ""

    @property
    def ok(self) -> bool:
        return self.skipped_reason == "" and self.exit_code == 0

    @property
    def skipped(self) -> bool:
        return self.skipped_reason != ""


@dataclass(frozen=True)
class VerifyResult:
    success: bool
    commands: list[VerifyCommandResult] = field(default_factory=list)
    skipped: bool = False

    @classmethod
    def empty_skipped(cls) -> "VerifyResult":
        return cls(success=False, commands=[], skipped=True)

    def render_summary(self) -> str:
        if self.skipped:
            return "verify: no executable commands found in bead's Verify: section (skipped)"
        lines: list[str] = []
        for c in self.commands:
            tag = "OK" if c.ok else ("SKIP" if c.skipped else "FAIL")
            lines.append(f"[{tag}] {c.command}")
            if not c.ok and not c.skipped and c.stderr.strip():
                lines.append(f"    stderr: {c.stderr.strip().splitlines()[-1][:200]}")
        return "\n".join(lines)


def parse_verify_commands(description: str) -> list[str]:
    """Pull executable commands out of the `Verify:` section of a bead description."""
    if not description:
        return []
    sections = list(_SECTION_RE.finditer(description))
    verify_idx = next((i for i, m in enumerate(sections) if m.group(1).lower() == "verify"), None)
    if verify_idx is None:
        return []
    start = sections[verify_idx].end()
    end = sections[verify_idx + 1].start() if verify_idx + 1 < len(sections) else len(description)
    block = description[start:end]

    commands: list[str] = []
    for raw_line in block.splitlines():
        m = _LIST_LINE_RE.match(raw_line)
        if not m:
            continue
        body = m.group(1).strip()
        low = body.lower()
        if any(low.startswith(prefix) for prefix in _MANUAL_PREFIXES):
            continue
        # If body is a sentence rather than a command (no shell-ish chars and ends with a period),
        # treat as documentation.
        if body.endswith(".") and " " in body and not any(c in body for c in "$&|()<>;"):
            continue
        commands.append(body)
    return commands


def _route_command(repo_root: Path, command: str) -> VerifyCommandResult:
    """Run one verify command through target_runtime.py."""
    target_runtime = repo_root / "scripts" / "shared" / "target_runtime.py"
    if not target_runtime.exists():
        # Fall back to running the command via the platform shell.
        cp = subprocess.run(
            command,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
            shell=True,
            encoding="utf-8",
            errors="replace",
        )
        return VerifyCommandResult(
            command=command,
            exit_code=cp.returncode,
            stdout=cp.stdout or "",
            stderr=cp.stderr or "",
        )

    cp = subprocess.run(
        [sys.executable, str(target_runtime), "run", "--", *command.split()],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
        encoding="utf-8",
        errors="replace",
    )
    return VerifyCommandResult(
        command=command,
        exit_code=cp.returncode,
        stdout=cp.stdout or "",
        stderr=cp.stderr or "",
    )


def run_verify(bead: dict[str, Any], repo_root: str | Path) -> VerifyResult:
    """Run every executable verify command in `bead`'s description, in order."""
    description = bead.get("description") or ""
    commands = parse_verify_commands(description)
    if not commands:
        return VerifyResult.empty_skipped()

    repo = Path(repo_root).resolve()
    results: list[VerifyCommandResult] = []
    success = True
    for cmd in commands:
        r = _route_command(repo, cmd)
        results.append(r)
        if not r.ok:
            success = False
    return VerifyResult(success=success, commands=results, skipped=False)
