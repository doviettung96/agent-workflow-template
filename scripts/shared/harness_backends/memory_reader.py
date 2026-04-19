"""Memory observer — reads a symbol/address from the target process.

PC: ctypes ReadProcessMemory (requires matching pid in target or resolvable via window title).
Android: defers to an already-attached Frida session exposing rpc.exports.read(symbol).

If neither is available, observe returns matched=false with an error explaining why,
rather than failing hard — the harness is "raw input first, memory nice-to-have".
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import struct
import sys
import time
from typing import Any


class BridgeDownError(RuntimeError):
    """frida session / process handle / symbols not usable."""


_IS_WINDOWS = sys.platform == "win32"


_TYPE_FORMATS = {
    "u8": ("<B", 1), "i8": ("<b", 1),
    "u16": ("<H", 2), "i16": ("<h", 2),
    "u32": ("<I", 4), "i32": ("<i", 4),
    "u64": ("<Q", 8), "i64": ("<q", 8),
    "f32": ("<f", 4), "f64": ("<d", 8),
    "bool": ("<?", 1),
}


def _parse_address(raw: Any) -> int:
    if isinstance(raw, int):
        return raw
    s = str(raw).strip()
    return int(s, 16) if s.lower().startswith("0x") else int(s, 0)


def _resolve_symbol(sym: str, symbols: dict | None) -> tuple[int, str]:
    if symbols is None:
        raise BridgeDownError("symbols.yaml not found; memory observers need .harness/symbols.yaml")
    resolver = symbols.get("resolver", "static")
    entry = (symbols.get("symbols") or {}).get(sym)
    if not entry:
        raise ValueError(f"symbol {sym!r} not in .harness/symbols.yaml")
    offset = _parse_address(entry.get("offset"))
    sym_type = entry.get("type")
    if resolver == "static":
        return offset, sym_type
    if resolver == "module_base":
        if not _IS_WINDOWS:
            raise BridgeDownError("module_base resolver currently supports Windows only")
        base = _module_base_windows(symbols.get("module"))
        return base + offset, sym_type
    raise BridgeDownError(f"resolver {resolver!r} not implemented (try 'static' or 'module_base')")


if _IS_WINDOWS:
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _psapi = ctypes.WinDLL("psapi", use_last_error=True)

    _kernel32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
    _kernel32.OpenProcess.restype = wt.HANDLE
    _kernel32.CloseHandle.argtypes = [wt.HANDLE]
    _kernel32.CloseHandle.restype = wt.BOOL
    _kernel32.ReadProcessMemory.argtypes = [wt.HANDLE, wt.LPCVOID, wt.LPVOID, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
    _kernel32.ReadProcessMemory.restype = wt.BOOL

    _psapi.EnumProcessModules.argtypes = [wt.HANDLE, ctypes.POINTER(wt.HMODULE), wt.DWORD, wt.LPDWORD]
    _psapi.EnumProcessModules.restype = wt.BOOL
    _psapi.GetModuleBaseNameW.argtypes = [wt.HANDLE, wt.HMODULE, wt.LPWSTR, wt.DWORD]
    _psapi.GetModuleBaseNameW.restype = wt.DWORD

    PROCESS_VM_READ = 0x0010
    PROCESS_QUERY_INFORMATION = 0x0400


def _pid_from_target(target: dict) -> int:
    pid = target.get("pid")
    if pid:
        return int(pid)
    # Resolve from window title via user32
    if not _IS_WINDOWS:
        raise BridgeDownError("pid resolution by window title requires Windows")
    title = target.get("window")
    if not title:
        raise BridgeDownError("target.pid or target.window required for memory observer on pc")
    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _user32.EnumWindows.argtypes = [ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM), wt.LPARAM]
    _user32.EnumWindows.restype = wt.BOOL
    _user32.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
    _user32.GetWindowTextW.restype = ctypes.c_int
    _user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
    _user32.GetWindowThreadProcessId.restype = wt.DWORD

    found = {"pid": 0}

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def _cb(hwnd, lparam):  # noqa: ARG001
        length = _user32.GetWindowTextW(hwnd, None, 0)
        if length <= 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        _user32.GetWindowTextW(hwnd, buf, length + 1)
        if title in buf.value:
            pid = wt.DWORD(0)
            _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            found["pid"] = pid.value
            return False
        return True

    _user32.EnumWindows(_cb, 0)
    if not found["pid"]:
        raise BridgeDownError(f"no window matched {title!r} for memory observer")
    return found["pid"]


def _module_base_windows(module: str | None) -> int:
    if not module:
        raise ValueError("symbols.module required for module_base resolver")
    handle = _kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, _current_pid_cache["pid"])
    if not handle:
        raise BridgeDownError(f"OpenProcess failed, GetLastError={ctypes.get_last_error()}")
    try:
        n_modules = 1024
        arr = (wt.HMODULE * n_modules)()
        needed = wt.DWORD(0)
        if not _psapi.EnumProcessModules(handle, arr, ctypes.sizeof(arr), ctypes.byref(needed)):
            raise BridgeDownError("EnumProcessModules failed")
        count = needed.value // ctypes.sizeof(wt.HMODULE)
        for i in range(min(count, n_modules)):
            name_buf = ctypes.create_unicode_buffer(260)
            _psapi.GetModuleBaseNameW(handle, arr[i], name_buf, 260)
            if name_buf.value.lower() == str(module).lower():
                return int(arr[i])
    finally:
        _kernel32.CloseHandle(handle)
    raise BridgeDownError(f"module {module!r} not loaded in target process")


_current_pid_cache: dict[str, int] = {"pid": 0}


def _read_bytes_windows(pid: int, address: int, size: int) -> bytes:
    handle = _kernel32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)
    if not handle:
        raise BridgeDownError(f"OpenProcess({pid}) failed, GetLastError={ctypes.get_last_error()}")
    try:
        buf = (ctypes.c_ubyte * size)()
        read = ctypes.c_size_t(0)
        ok = _kernel32.ReadProcessMemory(handle, ctypes.c_void_p(address), buf, size, ctypes.byref(read))
        if not ok or read.value != size:
            raise RuntimeError(f"ReadProcessMemory failed at 0x{address:X}, GetLastError={ctypes.get_last_error()}")
        return bytes(buf)
    finally:
        _kernel32.CloseHandle(handle)


def observe(target: dict, spec: dict, symbols: dict | None) -> dict:
    sym = spec.get("sym")
    if not sym:
        raise ValueError("memory observer requires 'sym'")
    type_name = spec.get("type")
    expect = spec.get("expect", None)
    timeout_s = float(spec.get("timeout_ms", 1500)) / 1000.0
    poll_s = float(spec.get("poll_ms", 50)) / 1000.0

    platform = target.get("platform")
    if platform == "android":
        return {"bridge": "memory", "matched": False, "elapsed_ms": 0, "evidence": None,
                "error": "android memory observer requires Frida session (not implemented in v1)"}

    if platform != "pc":
        raise BridgeDownError(f"memory observer does not support platform={platform!r}")

    if not _IS_WINDOWS:
        raise BridgeDownError("pc memory observer requires Windows")

    _current_pid_cache["pid"] = _pid_from_target(target)
    address, resolved_type = _resolve_symbol(sym, symbols)
    type_name = type_name or resolved_type
    if type_name not in _TYPE_FORMATS:
        raise ValueError(f"unsupported type for memory observer: {type_name!r}")
    fmt, size = _TYPE_FORMATS[type_name]

    deadline = time.monotonic() + timeout_s
    start = time.monotonic()
    last_value: Any = None
    while True:
        raw = _read_bytes_windows(_current_pid_cache["pid"], address, size)
        (value,) = struct.unpack(fmt, raw)
        last_value = value
        matched = True if expect is None else bool(value == expect)
        if matched:
            return {"bridge": "memory", "matched": True, "elapsed_ms": int((time.monotonic() - start) * 1000),
                    "evidence": f"{sym} @ 0x{address:X} = {value!r}", "error": None}
        if time.monotonic() >= deadline:
            return {"bridge": "memory", "matched": False, "elapsed_ms": int((time.monotonic() - start) * 1000),
                    "evidence": f"{sym} @ 0x{address:X} = {last_value!r}", "error": None}
        time.sleep(poll_s)
