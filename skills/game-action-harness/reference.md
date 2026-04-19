# Game Action Harness — Reference

## Catalog schema: `.harness/actions.yaml`

```yaml
target:
  platform: android | pc         # required
  device: emulator-5554          # required when platform=android; adb serial
  window: "Game Window Title"    # required when platform=pc; substring match on window title
  pid: 12345                     # optional; pc only; overrides window if set
  observe_log: .harness/events.log   # optional; path to hook-log file (UTF-8, one event per line)
  adb_path: null                 # optional; full path to adb binary (falls back to ADB_PATH env then PATH)

actions:
  <name>:
    invoke: <invoke-spec> | [<invoke-spec>, ...]
    observe: <observe-spec>      # optional; if absent the trigger returns immediately as status=ok
```

### Invoke specs

| kind | fields | platforms | notes |
|------|--------|-----------|-------|
| `adb_tap` | `coords: [x, y]` | android | `adb -s <dev> shell input tap X Y` |
| `adb_swipe` | `from: [x1, y1]`, `to: [x2, y2]`, `duration_ms: int` | android | `adb shell input swipe` |
| `adb_keyevent` | `code: <KEYCODE_* or int>` | android | `adb shell input keyevent` |
| `adb_text` | `text: string` | android | `adb shell input text` — spaces encoded as `%s` |
| `sendinput_click` | `coords: [x, y]`, `button: left\|right\|middle` (default left), `foreground: bool` (default true) | pc | `SetForegroundWindow` + `SendInput` mouse event |
| `sendinput_key` | `key: "A"\|"1"\|"F5"\|...`, `modifiers: [ctrl, shift, alt]` | pc | `SendInput` keyboard event |
| `postmessage_click` | `coords: [x, y]`, `button: left\|right` (default left) | pc | `PostMessageW(hwnd, WM_LBUTTONDOWN/UP, ...)`; works against background/minimized windows |

When `invoke` is a list, invokes run sequentially with no observer between them; only the top-level `observe` applies.

### Observe specs

| kind | fields | platforms | notes |
|------|--------|-----------|-------|
| `hook_log` | `tag: string`, `pattern: regex` (optional), `timeout_ms: int` | both | tails `target.observe_log` from `trigger start timestamp`, matches lines containing `tag` (and `pattern` if set) |
| `logcat` | `tag: string`, `pattern: regex` (optional), `timeout_ms: int` | android | `adb logcat -v raw -s <tag>`; runs only while waiting |
| `packet` | `log_path: string`, `pattern: regex`, `timeout_ms: int` | both | tails a network capture log written by the project's existing hooks |
| `memory` | `sym: string`, `type: u8\|u16\|u32\|u64\|i8\|i16\|i32\|i64\|f32\|f64\|bool`, `expect: value` (optional), `poll_ms: int` (default 50), `timeout_ms: int` | both | android: reads via already-attached Frida session; pc: `ReadProcessMemory`. Symbol resolved via `.harness/symbols.yaml` |

If `observe` is omitted, `trigger` returns `status=ok` with `observe: null` after invoking successfully. Intended for "fire and forget" inputs where observation is not wired up yet.

## CLI output shape

Every command supports `--json`. When absent, output is human-readable but the JSON is authoritative.

### `trigger` output

```json
{
  "action": "open_inventory",
  "status": "ok | timeout | bridge_down | unknown_action",
  "started_at": "2026-04-19T10:11:22.003Z",
  "invoke": {
    "bridge": "adb_tap",
    "elapsed_ms": 34,
    "error": null
  },
  "observe": {
    "bridge": "hook_log",
    "matched": true,
    "elapsed_ms": 412,
    "evidence": "[INV_OPEN] id=3 slot=0",
    "error": null
  }
}
```

Contract:

- `status=bridge_down` is reserved for infrastructure failure (adb not found, device missing, window not found, observe log unreadable). Do not retry; diagnose.
- `status=timeout` is used only when the *invoke* call itself exceeded its own timeout. Timeouts on the *observe* side result in `status=ok` + `observe.matched=false`.
- `evidence` is the verbatim matching line from the observe source when applicable.

### `probe` output

```json
{
  "profile": "game-re",
  "target": { "platform": "android", "device": "emulator-5554" },
  "bridges": [
    { "kind": "adb", "ok": true, "detail": "emulator-5554 device" },
    { "kind": "hook_log", "ok": true, "detail": ".harness/events.log (writable, 12KB)" }
  ],
  "ok": true
}
```

### `list` output

```json
{
  "actions": [
    { "name": "open_inventory", "invoke": "adb_tap", "observe": "hook_log" },
    { "name": "skill_1",        "invoke": "adb_keyevent", "observe": "logcat" }
  ]
}
```

## Symbols file: `.harness/symbols.yaml`

Optional. Used by the `memory` observer to resolve `sym` to a concrete address.

```yaml
version: 1
resolver: static            # static | frida | module_base
module: "game.exe"          # for module_base: address = base(module) + offset
symbols:
  g_InventoryOpen: { offset: "0x00432100", type: bool }
  g_PlayerPos.x:   { offset: "0x00448240", type: f32 }
  g_CombatState:   { offset: "0x00450018", type: u32 }
```

`frida` resolver defers lookup to an already-attached Frida session (expects a helper RPC export `resolve(sym: str) -> number`).

## Failure modes to expect

- **Emulator ADB version mismatch**: LDPlayer/MuMu ship their own `adb`. Set `target.adb_path` to pin the binary used by the harness, or set `ADB_PATH` env var. The backend falls back to PATH.
- **Foreground stealing**: `sendinput_click` with `foreground=true` forces focus on the target window. If the user is actively typing, inputs interleave. Use `postmessage_click` for background targets.
- **Observe log rotation**: the `hook_log` observer tails from the position recorded at `trigger start timestamp`. If the project rotates the log mid-trigger, matches after the rotation point are lost — flag this in the catalog entry's notes.
- **Unicode in `adb_text`**: only ASCII survives `adb shell input text` on most devices. For non-ASCII, add a dedicated IME-based action later.
