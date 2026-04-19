"""ADB input backend — adb_tap / adb_swipe / adb_keyevent / adb_text."""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any


class BridgeDownError(RuntimeError):
    """adb binary or device not usable."""


def _resolve_adb(target: dict) -> str:
    path = target.get("adb_path")
    if path and os.path.isfile(path):
        return path
    env = os.environ.get("ADB_PATH")
    if env and os.path.isfile(env):
        return env
    found = shutil.which("adb") or shutil.which("adb.exe")
    if found:
        return found
    raise BridgeDownError("adb binary not found (set target.adb_path, ADB_PATH env, or add adb to PATH)")


def _device_args(target: dict) -> list[str]:
    device = target.get("device")
    if not device:
        raise BridgeDownError("target.device is required for android actions")
    return ["-s", str(device)]


def _run(adb: str, device_args: list[str], shell_cmd: list[str], timeout: float = 10.0) -> str:
    try:
        result = subprocess.run(
            [adb, *device_args, "shell", *shell_cmd],
            capture_output=True, text=True, timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise BridgeDownError(f"adb not executable: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"adb shell timed out: {exc}") from exc
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        if "no devices" in stderr.lower() or "device not found" in stderr.lower() or "not found" in stderr.lower():
            raise BridgeDownError(f"adb: {stderr}")
        raise RuntimeError(f"adb failed (rc={result.returncode}): {stderr or result.stdout}")
    return result.stdout


def _keycode(code: Any) -> str:
    if isinstance(code, int):
        return str(code)
    return str(code)  # adb accepts KEYCODE_* names directly in recent versions


def invoke(target: dict, spec: dict) -> None:
    adb = _resolve_adb(target)
    dev = _device_args(target)
    kind = spec.get("kind")

    if kind == "adb_tap":
        x, y = spec["coords"]
        _run(adb, dev, ["input", "tap", str(int(x)), str(int(y))])
        return

    if kind == "adb_swipe":
        x1, y1 = spec["from"]
        x2, y2 = spec["to"]
        dur = int(spec.get("duration_ms", 100))
        _run(adb, dev, ["input", "swipe", str(int(x1)), str(int(y1)), str(int(x2)), str(int(y2)), str(dur)])
        return

    if kind == "adb_keyevent":
        _run(adb, dev, ["input", "keyevent", _keycode(spec["code"])])
        return

    if kind == "adb_text":
        text = str(spec["text"]).replace(" ", "%s")
        _run(adb, dev, ["input", "text", text])
        return

    raise ValueError(f"adb_input does not handle kind={kind!r}")


def probe(target: dict) -> dict:
    try:
        adb = _resolve_adb(target)
    except BridgeDownError as exc:
        return {"kind": "adb", "ok": False, "detail": str(exc)}

    device = target.get("device")
    if not device:
        return {"kind": "adb", "ok": False, "detail": "target.device not set"}

    try:
        result = subprocess.run([adb, "devices"], capture_output=True, text=True, timeout=5.0)
    except Exception as exc:
        return {"kind": "adb", "ok": False, "detail": f"adb devices failed: {exc}"}
    if result.returncode != 0:
        return {"kind": "adb", "ok": False, "detail": (result.stderr or result.stdout or "").strip()}

    lines = [ln.strip() for ln in (result.stdout or "").splitlines() if ln.strip() and not ln.startswith("List of devices")]
    for ln in lines:
        parts = ln.split()
        if parts and parts[0] == device:
            state = parts[1] if len(parts) > 1 else ""
            return {"kind": "adb", "ok": state == "device", "detail": f"{device} {state or 'unknown'}"}
    return {"kind": "adb", "ok": False, "detail": f"device {device} not found among {[l.split()[0] for l in lines]}"}
