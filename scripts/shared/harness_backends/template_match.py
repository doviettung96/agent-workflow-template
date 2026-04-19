"""Locate step — template matching against a captured window.

Composable locate → click pattern:
    invoke:
      - { kind: locate, method: template_match, template: assets/icon.png, output: pos }
      - { kind: postmessage_click, coords: $pos }

Window capture lives in this module because template_match is the only v1 consumer;
pull it into its own backend when a second consumer appears.

Dependencies (lazy-imported so the rest of the harness works without them):
    pip install opencv-python numpy
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


class BridgeDownError(RuntimeError):
    """window not found / adb not usable / capture API failed / cv2 not installed."""


class LocateFailure(RuntimeError):
    """Template match fell below confidence threshold."""


_IS_WINDOWS = sys.platform == "win32"


def _import_cv():
    try:
        import cv2  # noqa: F401
        import numpy as np  # noqa: F401
    except ImportError as exc:
        raise BridgeDownError(
            "template_match requires opencv-python and numpy. "
            "Install with: pip install opencv-python numpy"
        ) from exc
    return cv2, np


# -------- Window capture (PC) --------

if _IS_WINDOWS:
    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

    _user32.FindWindowW.argtypes = [wt.LPCWSTR, wt.LPCWSTR]
    _user32.FindWindowW.restype = wt.HWND
    _user32.EnumWindows.argtypes = [ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM), wt.LPARAM]
    _user32.EnumWindows.restype = wt.BOOL
    _user32.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
    _user32.GetWindowTextW.restype = ctypes.c_int
    _user32.IsWindowVisible.argtypes = [wt.HWND]
    _user32.IsWindowVisible.restype = wt.BOOL
    _user32.GetClientRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
    _user32.GetClientRect.restype = wt.BOOL
    _user32.GetDC.argtypes = [wt.HWND]
    _user32.GetDC.restype = wt.HDC
    _user32.ReleaseDC.argtypes = [wt.HWND, wt.HDC]
    _user32.ReleaseDC.restype = ctypes.c_int
    _user32.PrintWindow.argtypes = [wt.HWND, wt.HDC, wt.UINT]
    _user32.PrintWindow.restype = wt.BOOL

    _gdi32.CreateCompatibleDC.argtypes = [wt.HDC]
    _gdi32.CreateCompatibleDC.restype = wt.HDC
    _gdi32.CreateCompatibleBitmap.argtypes = [wt.HDC, ctypes.c_int, ctypes.c_int]
    _gdi32.CreateCompatibleBitmap.restype = wt.HBITMAP
    _gdi32.SelectObject.argtypes = [wt.HDC, wt.HGDIOBJ]
    _gdi32.SelectObject.restype = wt.HGDIOBJ
    _gdi32.DeleteObject.argtypes = [wt.HGDIOBJ]
    _gdi32.DeleteObject.restype = wt.BOOL
    _gdi32.DeleteDC.argtypes = [wt.HDC]
    _gdi32.DeleteDC.restype = wt.BOOL

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG),
            ("biPlanes", wt.WORD), ("biBitCount", wt.WORD), ("biCompression", wt.DWORD),
            ("biSizeImage", wt.DWORD), ("biXPelsPerMeter", wt.LONG),
            ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD), ("biClrImportant", wt.DWORD),
        ]

    class BITMAPINFO(ctypes.Structure):
        _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wt.DWORD * 3)]

    _gdi32.GetDIBits.argtypes = [
        wt.HDC, wt.HBITMAP, wt.UINT, wt.UINT, ctypes.c_void_p,
        ctypes.POINTER(BITMAPINFO), wt.UINT,
    ]
    _gdi32.GetDIBits.restype = ctypes.c_int

    PW_CLIENTONLY = 0x00000001
    PW_RENDERFULLCONTENT = 0x00000002
    DIB_RGB_COLORS = 0


def _find_window_hwnd(substring: str) -> int:
    if not _IS_WINDOWS:
        raise BridgeDownError("PC capture requires Windows")
    matches: list[int] = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def _cb(hwnd, lparam):  # noqa: ARG001
        if not _user32.IsWindowVisible(hwnd):
            return True
        length = _user32.GetWindowTextW(hwnd, None, 0)
        if length <= 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        _user32.GetWindowTextW(hwnd, buf, length + 1)
        if substring in buf.value:
            matches.append(hwnd)
        return True

    _user32.EnumWindows(_cb, 0)
    if not matches:
        raise BridgeDownError(f"window not found matching substring: {substring!r}")
    return matches[0]


def _capture_pc_window(target: dict):
    """Return (BGR numpy array, width, height) for the target window's client area."""
    cv2, np = _import_cv()
    title = target.get("window")
    if not title:
        raise BridgeDownError("target.window required for PC capture")
    hwnd = _find_window_hwnd(str(title))

    rect = wt.RECT()
    if not _user32.GetClientRect(hwnd, ctypes.byref(rect)):
        raise BridgeDownError(f"GetClientRect failed, GetLastError={ctypes.get_last_error()}")
    width = rect.right - rect.left
    height = rect.bottom - rect.top
    if width <= 0 or height <= 0:
        raise BridgeDownError(f"target window has empty client rect ({width}x{height})")

    hdc_win = _user32.GetDC(hwnd)
    if not hdc_win:
        raise BridgeDownError("GetDC failed")
    hdc_mem = _gdi32.CreateCompatibleDC(hdc_win)
    hbitmap = _gdi32.CreateCompatibleBitmap(hdc_win, width, height)
    old = _gdi32.SelectObject(hdc_mem, hbitmap)
    try:
        ok = _user32.PrintWindow(hwnd, hdc_mem, PW_CLIENTONLY | PW_RENDERFULLCONTENT)
        if not ok:
            raise BridgeDownError("PrintWindow returned 0 (window may not support capture)")

        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = width
        bmi.bmiHeader.biHeight = -height   # top-down row order
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = 0
        buf = (ctypes.c_ubyte * (width * height * 4))()
        got = _gdi32.GetDIBits(hdc_mem, hbitmap, 0, height, buf, ctypes.byref(bmi), DIB_RGB_COLORS)
        if got == 0:
            raise BridgeDownError("GetDIBits returned 0 rows")
    finally:
        _gdi32.SelectObject(hdc_mem, old)
        _gdi32.DeleteObject(hbitmap)
        _gdi32.DeleteDC(hdc_mem)
        _user32.ReleaseDC(hwnd, hdc_win)

    arr = np.frombuffer(buf, dtype=np.uint8).reshape((height, width, 4))
    return cv2.cvtColor(arr, cv2.COLOR_BGRA2BGR), width, height


# -------- Android capture --------

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
    raise BridgeDownError("adb binary not found for android screencap")


def _capture_android(target: dict):
    cv2, np = _import_cv()
    adb = _resolve_adb(target)
    device = target.get("device")
    if not device:
        raise BridgeDownError("target.device required for android capture")
    result = subprocess.run(
        [adb, "-s", device, "exec-out", "screencap", "-p"],
        capture_output=True, timeout=15.0,
    )
    if result.returncode != 0:
        stderr = (result.stderr or b"").decode("utf-8", errors="replace").strip()
        raise BridgeDownError(f"adb screencap failed: {stderr}")
    png = result.stdout
    if not png:
        raise BridgeDownError("adb screencap returned empty output")
    arr = np.frombuffer(png, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise BridgeDownError("cv2.imdecode could not parse screencap output as PNG")
    h, w = img.shape[:2]
    return img, w, h


def _capture(target: dict):
    platform = target.get("platform")
    if platform == "pc":
        return _capture_pc_window(target)
    if platform == "android":
        return _capture_android(target)
    raise BridgeDownError(f"capture not supported for platform={platform!r}")


# -------- Locate step --------

def locate(target: dict, spec: dict) -> dict[str, Any]:
    """Locate a template image in the captured game window.

    Spec fields:
      method: "template_match" (only method in v1)
      template: path (relative to repo root) to the reference image
      region: [x1, y1, x2, y2] optional — search only inside this rect of the capture
      threshold: float, default 0.85 — cv2 TM_CCOEFF_NORMED minimum match
      output: str, default "pos" — scope variable name for the resulting center coords

    Returns a dict merged into the chain's scope:
      {<output>: [cx, cy], <output>_confidence: <float>}

    Raises LocateFailure if the best match is below threshold.
    Raises BridgeDownError for infrastructure issues (window missing, cv2 missing, etc.).
    """
    method = spec.get("method", "template_match")
    if method != "template_match":
        raise ValueError(f"locate method {method!r} not supported in v1 (only 'template_match')")

    template_rel = spec.get("template")
    if not template_rel:
        raise ValueError("locate requires 'template' path")
    template_path = Path(template_rel)
    if not template_path.is_absolute():
        template_path = Path.cwd() / template_path
    if not template_path.is_file():
        raise BridgeDownError(f"template image not found: {template_path}")

    threshold = float(spec.get("threshold", 0.85))
    region = spec.get("region")
    output_var = str(spec.get("output", "pos"))
    retry_timeout_ms = int(spec.get("retry_timeout_ms", 0))
    retry_interval_ms = int(spec.get("retry_interval_ms", 150))

    cv2, np = _import_cv()
    needle = cv2.imread(str(template_path), cv2.IMREAD_COLOR)
    if needle is None:
        raise BridgeDownError(f"cv2 could not read template: {template_path}")
    nh, nw = needle.shape[:2]

    deadline = time.monotonic() + (retry_timeout_ms / 1000.0 if retry_timeout_ms > 0 else 0)
    best_confidence = 0.0
    while True:
        haystack, cap_w, cap_h = _capture(target)
        if region:
            x1, y1, x2, y2 = [int(v) for v in region]
            x1 = max(0, min(x1, cap_w))
            x2 = max(0, min(x2, cap_w))
            y1 = max(0, min(y1, cap_h))
            y2 = max(0, min(y2, cap_h))
            haystack = haystack[y1:y2, x1:x2]
            if haystack.size == 0:
                raise ValueError(f"region {region} produced empty slice of {cap_w}x{cap_h} capture")
            ox, oy = x1, y1
        else:
            ox = oy = 0

        hh, hw = haystack.shape[:2]
        if nh > hh or nw > hw:
            raise ValueError(f"template {nw}x{nh} larger than search area {hw}x{hh}")

        result = cv2.matchTemplate(haystack, needle, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        confidence = float(max_val)
        best_confidence = max(best_confidence, confidence)

        if confidence >= threshold:
            cx = int(max_loc[0] + nw // 2 + ox)
            cy = int(max_loc[1] + nh // 2 + oy)
            return {output_var: [cx, cy], f"{output_var}_confidence": confidence}

        if retry_timeout_ms <= 0 or time.monotonic() >= deadline:
            raise LocateFailure(
                f"template {template_rel!r} best match {best_confidence:.3f} < threshold {threshold:.3f}"
                f"{' after retry' if retry_timeout_ms > 0 else ''}"
            )
        time.sleep(retry_interval_ms / 1000.0)


def probe(target: dict) -> dict:
    """Smoke-check capture + cv2 import. Called only on demand — not part of `harness probe`."""
    try:
        _import_cv()
    except BridgeDownError as exc:
        return {"kind": "template_match", "ok": False, "detail": str(exc)}
    try:
        _, w, h = _capture(target)
        return {"kind": "template_match", "ok": True, "detail": f"captured {w}x{h}"}
    except BridgeDownError as exc:
        return {"kind": "template_match", "ok": False, "detail": str(exc)}
