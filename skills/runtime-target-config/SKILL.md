---
name: runtime-target-config
description: "Interactive setup for .harbor/runtime-target.json — chooses local/ssh mode and the game-RE target subobject (emulator, device, game window) plus a probe_command. Use when initializing a new repo, switching emulators, swapping target devices, or when target-runtime-exec reports a misconfiguration."
---

# Runtime Target Config

Walk the user through configuring `.harbor/runtime-target.json` for this repo. The file declares two orthogonal axes:

- **Where to run** — `mode=local` (this machine) vs `mode=ssh` (remote host with workdir + sync strategy).
- **What to target** — `target.kind` ∈ `{local, emulator, device, game_window}` plus the kind-specific subobject and a `probe_command`.

The probe command is the user-defined readiness check. It runs before every project command when `target.kind != local` and is the gate the worker uses to refuse running probes against an unreachable target.

## When to Use

- Fresh repo: `.harbor/runtime-target.json` exists only as the default `{mode:local, target:{kind:local}}`.
- Switching from one emulator/device to another.
- Adding `probe_command` when a task's `## Worker Instructions` requires an emulator/device/window.
- `target-runtime-exec` aborted with "probe_target.py failed" or "no probe_command set".

## Steps

1. **Read the current state.**
   ```bash
   python scripts/shared/target_runtime.py status
   ```
   Show the user what is already configured.

2. **Pick the execution mode.** Ask:
   > Run commands locally, or via SSH to a remote host?
   - `local` — most game-RE work where the emulator runs on this machine.
   - `ssh` — when the build/test happens on a different host (rare in game-RE).

   If `ssh`, gather `ssh_host`, `remote_platform` (`posix`|`windows`), `remote_workdir`, optional `remote_python`. Persist via:
   ```bash
   python scripts/shared/target_runtime.py configure --mode=ssh --ssh-host=... --remote-platform=... --remote-workdir=...
   ```

3. **Pick the target kind.** Ask:
   > What is the runtime target for this repo's commands?
   - `local` — no emulator, no device, no specific window.
   - `emulator` — an emulator process this machine launches (LDPlayer, MuMu, BlueStacks, etc.).
   - `device` — an ADB-attached device (phone, emulator at a specific port, Frida session, raw bridge).
   - `game_window` — a specific desktop window identified by title or class.

4. **Collect the kind-specific subobject.**

   For `emulator`:
   ```bash
   python scripts/shared/target_runtime.py target set-emulator \
     --name=ldplayer-9 \
     --exec-path="C:/LDPlayer/LDPlayer9/dnplayer.exe" \
     --arg=--instance --arg=0 \
     --adb-port=5555 \
     --probe-command="adb -s 127.0.0.1:5555 shell pidof com.YostarJP.BlueArchive"
   ```

   For `device`:
   ```bash
   python scripts/shared/target_runtime.py target set-device \
     --id=127.0.0.1:5555 \
     --kind=adb \
     --transport=tcp \
     --probe-command="adb -s 127.0.0.1:5555 get-state"
   ```

   For `game_window`:
   ```bash
   python scripts/shared/target_runtime.py target set-game-window \
     --title-pattern=BlueArchive \
     --pid-lookup-strategy=adb-focused-app \
     --probe-command="adb shell dumpsys window windows | rg mCurrentFocus | rg BlueArchive"
   ```

   For `local`:
   ```bash
   python scripts/shared/target_runtime.py target set-local
   ```

5. **Validate the probe.** Run it once to make sure it works:
   ```bash
   python scripts/shared/probe_target.py
   ```
   Expect `target=<kind> probe='<cmd>' exit=0`. If non-zero, fix the probe before continuing.

6. **Confirm.**
   ```bash
   python scripts/shared/target_runtime.py status
   ```
   Show the user the resolved config and ask them to confirm before proceeding to other work.

## Hard Rules

- Always set `probe_command` when `target.kind != local`. The worker refuses to run task probes if it cannot first verify the target is reachable.
- Do not write to `.harbor/runtime-target.json` directly — use the `target_runtime.py` subcommands. Direct edits skip schema validation.
- `runtime-target.local.json` (worktree-local override, gitignored) is for per-task overrides written by the worker. Do NOT teach users to edit it manually.
- If the user is on a fresh repo and skips this skill, the default `local`/`local` is fine — but any task whose `## Worker Instructions` require an emulator/device/game-window target will fail until the user runs this skill.
