---
name: build-and-test
description: "Use after implementing code changes to build the PyInstaller bundle, launch the exe, and test via API endpoints. Only rebuild when runtime code changed."
---

# Build and Test

**Workflow position:** Executor session, between implementation (step 3) and verification (step 6). See BEADS_WORKFLOW.md.

Build, launch, and test only the components affected by the current changes.

> **CUSTOMIZE THIS SKILL** for your project. The defaults below assume a
> PyInstaller-bundled Python bot with a FastAPI server — the common pattern
> for game automation projects. Adjust the spec file, exe name, port, and
> endpoints to match your project.

## Project Config

<!-- Update these for your project -->
| Setting | Value |
|---|---|
| Spec file | `launcher.spec` |
| Output exe | `dist/BotName.exe` |
| API port | `8787` |
| Launch args | (none by default) |

## Steps

### 1. Find the test plan

Read the `## Verification` section of the execution plan saved in `docs/plans/`. This tells you exactly what to build, deploy, and test. If no plan file exists, fall back to the smoke tests below.

### 2. Detect what changed

```bash
git diff --name-only HEAD
```
If nothing staged, also check unstaged:
```bash
git diff --name-only
```

### 3. Decide if a rebuild is needed

A rebuild is needed when runtime Python code, the entry point, the spec file, or bundled assets changed. A rebuild is NOT needed when only documentation, tests, or non-runtime config changed.

<!-- Customize this table for your project's directory layout -->
| Changed path | Action |
|---|---|
| `app/` | Rebuild — bot logic changed |
| `launcher.py` | Rebuild — entry point changed |
| `launcher.spec` | Rebuild — bundle config changed |
| `deploy.py` | Rebuild — deploy logic changed |
| `tools/` | Rebuild — runtime tools changed |
| `docs/`, `*.md` | Skip — no rebuild needed |

### 4. Build the bundle

```bash
pyinstaller launcher.spec
```

Output: `dist/BotName.exe`

### 5. Clean state (REQUIRED before every launch)

You MUST stop everything before launching. Do not skip any of these:

```bash
# 1. Stop the bot exe explicitly by name
taskkill /F /IM BotName.exe 2>/dev/null || true

# 2. Stop the game/app on all connected devices
for serial in $(adb devices | grep -w device | awk '{print $1}'); do
  adb -s "$serial" shell am force-stop <package>
done
```

Wait a moment for ports to free up.

### 6. Launch the exe

> **IMPORTANT:** You MUST have killed all previous instances (step 5) before launching. If you skip this, the new instance will fail to bind ports or behave unpredictably.

```bash
./dist/BotName.exe &
```

Wait for the API server to become available:
```bash
for i in $(seq 1 30); do
  curl -s http://localhost:8787/ping && break
  sleep 2
done
```

**If the bot exits immediately (no devices found):** This is NOT a blocker. Do not stop and report "no devices." Instead:

1. Verify emulators/devices are running:
   ```bash
   adb devices
   ```
2. If devices are listed but bot still fails, run clean state again (step 5) — kill the bot exe, force-stop games on all devices — then relaunch.
3. If no devices show up in `adb devices`, THEN report the issue and ask the user to start emulators.

### 7. Smoke tests (always)

```bash
curl -s http://localhost:8787/ping
curl -s http://localhost:8787/status
```

Both must return valid JSON responses.

### 8. Live session test (when logic changed)

If the bead changed runtime logic (bot behavior, automation flows, API handlers, deploy/injection), you MUST run a live session test. Do not settle for "API returns 200" — you must observe the actual behavior.

Skip this step only when changes are purely structural (refactoring with no behavior change, documentation, config that doesn't affect runtime).

**Procedure:**

1. **Kill the running game/app on the device** (if applicable):
   ```bash
   adb -s <serial> shell am force-stop <package>
   ```

2. **Stop the bot if running:**
   ```bash
   taskkill /F /IM BotName.exe 2>/dev/null || true
   ```

3. **Launch a fresh bot session:**
   ```bash
   ./dist/BotName.exe &
   ```
   Wait for the API server and device connection (poll `/ping` and `/devices`).

4. **Trigger the automation flow being tested** via API — use whatever the verification plan specifies.

5. **Watch the logs and poll status** to verify the behavior is correct. Keep polling for a reasonable duration (30-60s depending on the flow) to confirm the automation actually progresses, not just starts.

6. **Check results against the verification plan.** The execution plan's `## Verification` section defines exactly what success looks like — match observed behavior against it.

### 9. Report results

State what was built, launched, and tested with **actual observed behavior** — log output, status responses, and whether the app performed the expected actions. Do NOT claim success without evidence.

### 10. Cleanup

After testing, stop the bot:
```bash
taskkill /F /IM BotName.exe 2>/dev/null || true
```

## Fix-and-Retry Loop

If tests fail or behavior is wrong, do NOT proceed to final verification. Instead:

1. Stop the running bot
2. Fix the code (go back to implementation)
3. Re-invoke `build-and-test`
4. Repeat until tests pass

```
implement → build-and-test → FAIL → fix code → build-and-test → PASS → verification
```

Only proceed to final verification when `build-and-test` passes.

## Skip Conditions

Do NOT trigger this skill when:
- Only documentation files changed (`*.md`, `docs/`)
- Only config files changed that do not affect runtime
- In a planner session
- The user explicitly says no testing is needed
