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
    observe: <observe-spec>      # OPTIONAL; omit to treat a successful invoke as status=ok
```

Observers are optional by design: each project has its own way to read state (memory, packet capture, custom hook logs). Only attach an observer when the project already emits something worth matching.

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
| `locate` | `method: template_match`, `template: path`, `region: [x1,y1,x2,y2]?`, `threshold: float` (default 0.85), `output: varname` (default `pos`), `retry_timeout_ms: int?`, `retry_interval_ms: int` (default 150) | both | Captures the game window (PC: `PrintWindow` in client coords; android: `adb exec-out screencap -p`), runs `cv2.matchTemplate` against the reference image, writes `[cx, cy]` into `scope[<output>]`. Raises `locate_failed` if best match < threshold (after retries if set). Also writes `<output>_confidence`. Requires `pip install opencv-python numpy` |
| `wait` | `duration_ms: int` | both | Fixed sleep between chain steps. Tests are simple; a short sleep after a click is usually enough to let an animation settle before the next step |

When `invoke` is a list, steps run sequentially. A chain stops on the first error; subsequent steps are skipped.

### Invoke chaining and scope

Chain steps share a variable scope. A `locate` step writes its result into `scope[<output>]`; any later step can reference it with `$<output>`. Scope is also seeded by CLI `--arg KEY=VALUE` pairs.

```yaml
# Example: locate an icon, wait for it to settle, click it, then click an adjacent button.
talk_to_vendor:
  invoke:
    - { kind: locate, method: template_match, template: .harness/assets/vendor_npc.png, output: npc, retry_timeout_ms: 3000 }
    - { kind: postmessage_click, coords: $npc }
    - { kind: wait, duration_ms: 500 }
    - { kind: locate, method: template_match, template: .harness/assets/dialog_accept.png, output: btn, threshold: 0.9 }
    - { kind: sendinput_click, coords: $btn }
```

`locate` acts as a guard: if the expected icon is not visible (e.g., the dialog did not appear), the chain aborts with `locate_failed` and no stale click fires.

When `retry_timeout_ms` is set on a `locate` step, the step polls (re-captures + re-matches) at `retry_interval_ms` until the threshold is met or the timeout elapses. This is the "wait for X to appear, then click it" pattern.

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

Single-step action (no chain):

```json
{
  "action": "open_inventory",
  "status": "ok | timeout | bridge_down | locate_failed | unknown_action",
  "started_at": "2026-04-19T10:11:22.003Z",
  "invoke": {
    "bridge": "adb_tap",
    "elapsed_ms": 34,
    "error": null
  },
  "observe": null
}
```

Multi-step chain — `invoke` summarizes the last-or-failing step and adds a `steps` array:

```json
{
  "action": "talk_to_vendor",
  "status": "ok",
  "invoke": {
    "bridge": "sendinput_click",
    "elapsed_ms": 12,
    "error": null,
    "steps": [
      { "bridge": "locate",            "elapsed_ms": 88,  "error": null },
      { "bridge": "postmessage_click", "elapsed_ms": 2,   "error": null },
      { "bridge": "wait",              "elapsed_ms": 500, "error": null },
      { "bridge": "locate",            "elapsed_ms": 74,  "error": null },
      { "bridge": "sendinput_click",   "elapsed_ms": 12,  "error": null }
    ]
  },
  "observe": null
}
```

Contract:

- `status=bridge_down` — infrastructure failure (adb not found, device missing, window not found, cv2 not installed, observe log unreadable). Do not retry; diagnose.
- `status=locate_failed` — a chain step's `locate` could not find its template above threshold (after retries if configured). Not an infrastructure failure; it's a real signal that the expected UI state is not present.
- `status=timeout` — the invoke call itself exceeded its own timeout.
- Timeouts on the *observe* side do not fail the action: they yield `status=ok` + `observe.matched=false`.
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

## Coordinate spaces and input routing

Getting this wrong is the #1 source of silent "click landed somewhere unexpected" bugs. The harness standardizes as follows:

- **PC capture** uses `PrintWindow(hwnd, PW_CLIENTONLY | PW_RENDERFULLCONTENT)`. This captures the game window's *client area* — no title bar, no borders — at its actual pixel size, **even when the window is occluded or partly off-screen**. (0, 0) is the top-left of the client area.
- **PC `postmessage_click` coords are client coords.** They match the capture coord space 1:1, so coords produced by a `locate` step feed directly into `postmessage_click`. No focus stealing, works on background/minimized windows.
- **PC `sendinput_click` coords are client coords that the harness converts to absolute screen coords internally** (by querying the window rect). It also forces the target window to foreground first. Use this only when the game rejects `PostMessage` mouse events (some DirectX-exclusive games do).
- **Android capture** uses `adb exec-out screencap -p` which yields native device pixels. `adb shell input tap X Y` uses the same pixel space. Template matches and tap coords share coord space natively.
- **DPI**: PC capture returns pixels at the window's actual rendered size. If Windows is scaling the game window (high-DPI display, scaling setting != 100%), the capture reflects that scale. Keep your template images captured from the same DPI you will run against, or add `-Dpi` handling later if you need cross-DPI portability.

If you see template matches succeed but clicks land in the wrong place, the first thing to check is whether you mixed `sendinput_click` (screen-space expectation) with a coord pulled from a `locate` step (client-space). Use `postmessage_click` unless the game forces `SendInput`.

## Failure modes to expect

- **Emulator ADB version mismatch**: LDPlayer/MuMu ship their own `adb`. Set `target.adb_path` to pin the binary used by the harness, or set `ADB_PATH` env var. The backend falls back to PATH.
- **Foreground stealing**: `sendinput_click` with `foreground=true` forces focus on the target window. If the user is actively typing, inputs interleave. Use `postmessage_click` for background targets.
- **Observe log rotation**: the `hook_log` observer tails from the position recorded at `trigger start timestamp`. If the project rotates the log mid-trigger, matches after the rotation point are lost — flag this in the catalog entry's notes.
- **Unicode in `adb_text`**: only ASCII survives `adb shell input text` on most devices. For non-ASCII, add a dedicated IME-based action later.
