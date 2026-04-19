"""Log-based observers — hook_log (tails a local file), logcat (android), packet (file-grep)."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from pathlib import Path


class BridgeDownError(RuntimeError):
    """observe log path missing / adb not usable."""


def _tail_file_match(path: Path, start_size: int, tag: str, pattern: str | None, timeout_s: float) -> tuple[bool, str | None, int]:
    """Poll-tail a file from start_size for a line containing tag (and optional regex)."""
    regex = re.compile(pattern) if pattern else None
    deadline = time.monotonic() + timeout_s
    pos = start_size
    buffer = b""
    while time.monotonic() < deadline:
        try:
            with path.open("rb") as fh:
                fh.seek(pos)
                chunk = fh.read()
                pos = fh.tell()
        except FileNotFoundError:
            time.sleep(0.05)
            continue
        if chunk:
            buffer += chunk
            while b"\n" in buffer:
                line_bytes, buffer = buffer.split(b"\n", 1)
                line = line_bytes.decode("utf-8", errors="replace")
                if tag in line and (regex is None or regex.search(line)):
                    elapsed_ms = int((time.monotonic() - (deadline - timeout_s)) * 1000)
                    return True, line, elapsed_ms
        time.sleep(0.05)
    return False, None, int(timeout_s * 1000)


def observe(target: dict, spec: dict, started_mono: float) -> dict:
    kind = spec.get("kind")
    timeout_s = float(spec.get("timeout_ms", 2000)) / 1000.0

    if kind == "hook_log":
        log_rel = target.get("observe_log")
        if not log_rel:
            raise BridgeDownError("target.observe_log not set")
        path = Path(log_rel)
        if not path.is_absolute():
            path = Path.cwd() / path
        if not path.parent.is_dir():
            raise BridgeDownError(f"observe_log parent dir missing: {path.parent}")
        start_size = path.stat().st_size if path.is_file() else 0
        tag = spec.get("tag")
        if not tag:
            raise ValueError("hook_log observer requires 'tag'")
        matched, evidence, elapsed_ms = _tail_file_match(
            path, start_size, tag, spec.get("pattern"), timeout_s,
        )
        return {"bridge": "hook_log", "matched": matched, "elapsed_ms": elapsed_ms, "evidence": evidence, "error": None}

    if kind == "logcat":
        if target.get("platform") != "android":
            raise BridgeDownError("logcat observer requires android platform")
        adb = target.get("adb_path") or os.environ.get("ADB_PATH") or shutil.which("adb") or shutil.which("adb.exe")
        if not adb:
            raise BridgeDownError("adb binary not found for logcat")
        device = target.get("device")
        if not device:
            raise BridgeDownError("target.device not set for logcat")
        tag = spec.get("tag")
        if not tag:
            raise ValueError("logcat observer requires 'tag'")
        regex = re.compile(spec["pattern"]) if spec.get("pattern") else None
        # Clear existing logcat buffer so we only see events after trigger.
        subprocess.run([adb, "-s", device, "logcat", "-c"], capture_output=True, text=True, timeout=5.0)
        proc = subprocess.Popen(
            [adb, "-s", device, "logcat", "-v", "raw", "-s", f"{tag}:*"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        deadline = time.monotonic() + timeout_s
        matched = False
        evidence = None
        try:
            while time.monotonic() < deadline:
                if proc.stdout is None:
                    break
                line = proc.stdout.readline()
                if not line:
                    if proc.poll() is not None:
                        break
                    continue
                line = line.rstrip()
                if regex is None or regex.search(line):
                    matched = True
                    evidence = line
                    break
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                proc.kill()
        return {"bridge": "logcat", "matched": matched, "elapsed_ms": int(timeout_s * 1000),
                "evidence": evidence, "error": None}

    if kind == "packet":
        log_rel = spec.get("log_path")
        if not log_rel:
            raise ValueError("packet observer requires 'log_path'")
        path = Path(log_rel)
        if not path.is_absolute():
            path = Path.cwd() / path
        start_size = path.stat().st_size if path.is_file() else 0
        tag = spec.get("tag", "")
        matched, evidence, elapsed_ms = _tail_file_match(
            path, start_size, tag, spec.get("pattern"), timeout_s,
        )
        return {"bridge": "packet", "matched": matched, "elapsed_ms": elapsed_ms, "evidence": evidence, "error": None}

    raise ValueError(f"log_tail does not handle kind={kind!r}")


def probe(target: dict) -> dict:
    log_rel = target.get("observe_log")
    if not log_rel:
        return {"kind": "hook_log", "ok": True, "detail": "no observe_log set (hook_log observers disabled)"}
    path = Path(log_rel)
    if not path.is_absolute():
        path = Path.cwd() / path
    if not path.parent.is_dir():
        return {"kind": "hook_log", "ok": False, "detail": f"parent dir missing: {path.parent}"}
    if path.is_file():
        size = path.stat().st_size
        return {"kind": "hook_log", "ok": True, "detail": f"{path} ({size} bytes)"}
    return {"kind": "hook_log", "ok": True, "detail": f"{path} (not yet written; parent exists)"}
