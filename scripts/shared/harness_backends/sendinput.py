"""PC input backend — SendInput (foreground) + PostMessage (background).

All Win32 calls go through ctypes to avoid a pywin32 dependency. Non-Windows
platforms can still import the module — functions raise BridgeDownError on use.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import sys
from typing import Any


class BridgeDownError(RuntimeError):
    """win32 API / target window not usable."""


_IS_WINDOWS = sys.platform == "win32"


# ---- Win32 setup (only loaded on Windows) ----

if _IS_WINDOWS:
    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    _user32.FindWindowW.argtypes = [wt.LPCWSTR, wt.LPCWSTR]
    _user32.FindWindowW.restype = wt.HWND
    _user32.EnumWindows.argtypes = [ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM), wt.LPARAM]
    _user32.EnumWindows.restype = wt.BOOL
    _user32.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
    _user32.GetWindowTextW.restype = ctypes.c_int
    _user32.IsWindowVisible.argtypes = [wt.HWND]
    _user32.IsWindowVisible.restype = wt.BOOL
    _user32.SetForegroundWindow.argtypes = [wt.HWND]
    _user32.SetForegroundWindow.restype = wt.BOOL
    _user32.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
    _user32.PostMessageW.restype = wt.BOOL
    _user32.SendInput.argtypes = [wt.UINT, ctypes.c_void_p, ctypes.c_int]
    _user32.SendInput.restype = wt.UINT
    _user32.MapVirtualKeyW.argtypes = [wt.UINT, wt.UINT]
    _user32.MapVirtualKeyW.restype = wt.UINT
    _user32.VkKeyScanW.argtypes = [wt.WCHAR]
    _user32.VkKeyScanW.restype = ctypes.c_short

    INPUT_MOUSE = 0
    INPUT_KEYBOARD = 1
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004
    MOUSEEVENTF_RIGHTDOWN = 0x0008
    MOUSEEVENTF_RIGHTUP = 0x0010
    MOUSEEVENTF_MIDDLEDOWN = 0x0020
    MOUSEEVENTF_MIDDLEUP = 0x0040
    MOUSEEVENTF_MOVE = 0x0001
    MOUSEEVENTF_ABSOLUTE = 0x8000
    KEYEVENTF_KEYUP = 0x0002
    KEYEVENTF_SCANCODE = 0x0008
    WM_LBUTTONDOWN = 0x0201
    WM_LBUTTONUP = 0x0202
    WM_RBUTTONDOWN = 0x0204
    WM_RBUTTONUP = 0x0205
    VK_SHIFT = 0x10
    VK_CONTROL = 0x11
    VK_MENU = 0x12   # alt

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [("dx", wt.LONG), ("dy", wt.LONG), ("mouseData", wt.DWORD),
                    ("dwFlags", wt.DWORD), ("time", wt.DWORD), ("dwExtraInfo", ctypes.c_void_p)]

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD),
                    ("time", wt.DWORD), ("dwExtraInfo", ctypes.c_void_p)]

    class _INPUT_UNION(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]

    class INPUT(ctypes.Structure):
        _anonymous_ = ("u",)
        _fields_ = [("type", wt.DWORD), ("u", _INPUT_UNION)]


def _require_windows() -> None:
    if not _IS_WINDOWS:
        raise BridgeDownError("sendinput backend requires Windows")


def _find_window_by_title(substring: str) -> int:
    _require_windows()
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
        title = buf.value
        if substring in title:
            matches.append(hwnd)
        return True

    _user32.EnumWindows(_cb, 0)
    if not matches:
        raise BridgeDownError(f"window not found matching substring: {substring!r}")
    return matches[0]


def _resolve_hwnd(target: dict) -> int:
    if target.get("pid"):
        # pid targeting not yet supported; fall back to window title
        pass
    title = target.get("window")
    if not title:
        raise BridgeDownError("target.window is required for pc actions")
    return _find_window_by_title(str(title))


def _send_mouse(flags: int, x: int = 0, y: int = 0) -> None:
    mi = MOUSEINPUT(dx=x, dy=y, mouseData=0, dwFlags=flags, time=0, dwExtraInfo=None)
    inp = INPUT(type=INPUT_MOUSE)
    inp.mi = mi
    n = _user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))
    if n != 1:
        err = ctypes.get_last_error()
        raise RuntimeError(f"SendInput(mouse) failed, GetLastError={err}")


def _send_key(vk: int, up: bool, modifiers: list[int] | None = None) -> None:
    seq = []
    for mod in modifiers or []:
        seq.append((mod, False))
    seq.append((vk, up))
    for mod in reversed(modifiers or []):
        if up:
            seq.append((mod, True))
    inputs = (INPUT * len(seq))()
    for i, (k, is_up) in enumerate(seq):
        flags = KEYEVENTF_KEYUP if is_up else 0
        inputs[i] = INPUT(type=INPUT_KEYBOARD)
        inputs[i].ki = KEYBDINPUT(wVk=k, wScan=0, dwFlags=flags, time=0, dwExtraInfo=None)
    n = _user32.SendInput(len(inputs), ctypes.byref(inputs), ctypes.sizeof(INPUT))
    if n != len(inputs):
        err = ctypes.get_last_error()
        raise RuntimeError(f"SendInput(key) sent {n}/{len(inputs)}, GetLastError={err}")


_VK_NAMED = {
    "F1": 0x70, "F2": 0x71, "F3": 0x72, "F4": 0x73, "F5": 0x74, "F6": 0x75,
    "F7": 0x76, "F8": 0x77, "F9": 0x78, "F10": 0x79, "F11": 0x7A, "F12": 0x7B,
    "ENTER": 0x0D, "RETURN": 0x0D, "ESC": 0x1B, "ESCAPE": 0x1B,
    "SPACE": 0x20, "TAB": 0x09, "BACKSPACE": 0x08,
    "UP": 0x26, "DOWN": 0x28, "LEFT": 0x25, "RIGHT": 0x27,
}


def _resolve_vk(key: str) -> int:
    _require_windows()
    k = str(key).upper()
    if k in _VK_NAMED:
        return _VK_NAMED[k]
    if len(k) == 1:
        vk_and_shift = _user32.VkKeyScanW(ctypes.c_wchar(k))
        if vk_and_shift == -1:
            raise ValueError(f"VkKeyScan could not resolve key {key!r}")
        return vk_and_shift & 0xFF
    raise ValueError(f"unknown key name: {key!r}")


def invoke(target: dict, spec: dict) -> None:
    _require_windows()
    kind = spec.get("kind")

    if kind == "sendinput_click":
        x, y = spec["coords"]
        button = str(spec.get("button", "left")).lower()
        foreground = bool(spec.get("foreground", True))
        if foreground:
            hwnd = _resolve_hwnd(target)
            _user32.SetForegroundWindow(hwnd)
        down, up = {
            "left": (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP),
            "right": (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP),
            "middle": (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP),
        }[button]
        # SendInput with MOUSEEVENTF_ABSOLUTE expects 0..65535 on primary monitor
        screen_w = _user32.GetSystemMetrics(0)
        screen_h = _user32.GetSystemMetrics(1)
        _user32.GetSystemMetrics.argtypes = [ctypes.c_int]
        _user32.GetSystemMetrics.restype = ctypes.c_int
        ax = int((int(x) / max(screen_w, 1)) * 65535)
        ay = int((int(y) / max(screen_h, 1)) * 65535)
        _send_mouse(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, ax, ay)
        _send_mouse(down)
        _send_mouse(up)
        return

    if kind == "sendinput_key":
        vk = _resolve_vk(spec["key"])
        mods = []
        for name in spec.get("modifiers") or []:
            mods.append({"ctrl": VK_CONTROL, "shift": VK_SHIFT, "alt": VK_MENU}[str(name).lower()])
        _send_key(vk, up=False, modifiers=mods)
        _send_key(vk, up=True, modifiers=mods)
        return

    if kind == "postmessage_click":
        hwnd = _resolve_hwnd(target)
        x, y = spec["coords"]
        lparam = (int(y) << 16) | (int(x) & 0xFFFF)
        button = str(spec.get("button", "left")).lower()
        down, up = {
            "left": (WM_LBUTTONDOWN, WM_LBUTTONUP),
            "right": (WM_RBUTTONDOWN, WM_RBUTTONUP),
        }[button]
        if not _user32.PostMessageW(hwnd, down, 1, lparam):
            raise RuntimeError(f"PostMessage down failed, GetLastError={ctypes.get_last_error()}")
        if not _user32.PostMessageW(hwnd, up, 0, lparam):
            raise RuntimeError(f"PostMessage up failed, GetLastError={ctypes.get_last_error()}")
        return

    raise ValueError(f"sendinput does not handle kind={kind!r}")


def probe(target: dict) -> dict:
    if not _IS_WINDOWS:
        return {"kind": "sendinput", "ok": False, "detail": "not Windows"}
    try:
        hwnd = _resolve_hwnd(target)
    except BridgeDownError as exc:
        return {"kind": "sendinput", "ok": False, "detail": str(exc)}
    return {"kind": "sendinput", "ok": True, "detail": f"window hwnd=0x{hwnd:X} matched"}
