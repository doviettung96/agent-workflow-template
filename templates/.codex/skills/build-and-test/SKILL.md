---
name: build-and-test
description: "Use after implementing code changes in TGun-like automation repos to build, deploy, and test the affected components. Only build what changed and dynamically pick a device with no existing port forwards plus a free bridge port."
---

# Build and Test

**Workflow position:** Executor session, between implementation (step 3) and verification (step 6). See BEADS_WORKFLOW.md.

Build, deploy, and test only the components affected by the current changes.

## Device Selection

Do NOT hardcode a device serial or port. Discover dynamically.

**On re-invocation within the same session:** If you already picked a device and port earlier in this session, reuse them - the forwards are ours. Skip straight to the Build step.

**First time in session:**

1. **List connected devices:**
   ```bash
   adb devices
   ```

2. **List ALL existing port forwards across all devices:**
   ```bash
   adb forward --list
   ```

3. **Pick a device** that has NO port forwards at all. Other automation systems may be running on devices with existing forwards - avoid those entirely to prevent conflicts.

4. **Pick a free PC-side port** for the bridge. Check what is already taken:
   ```bash
   adb forward --list | awk '{print $2}' | sort
   ```
   Choose a port NOT in that list. The default device-side port is 32123, but the PC-side port must be unique across all forwarded devices.

5. **Use `--device <serial>`** in all deploy commands.

**If no device is available without existing forwards**, ask the user which device to use - do not pick one that might conflict with other running automation.

## Steps

1. **Find the test plan** - read the `## Verification` section of the execution plan saved in `docs/plans/`. This tells you exactly what to build, deploy, and test. If no plan file exists, fall back to the component reference table below.

2. **Detect what changed:**
   ```bash
   git diff --name-only HEAD
   ```
   If nothing staged, also check unstaged:
   ```bash
   git diff --name-only
   ```

3. **Build affected components** based on changed paths:

   | Changed path | Action |
   |---|---|
   | `native-lib/` | Rebuild native lib |
   | `swf-patch/` or `tools/` (SWF-related) | Re-patch and re-encrypt SWF |
   | `app/` or `run_bot.py` | No build needed (Python), but restart bot if running |
   | `inject.py` | No build, but may need re-inject |

4. **Deploy if needed** - only when native-lib or SWF changed:

   **Native lib changed:**
   ```bash
   cd native-lib && bash build.sh x64      # or arm, based on device ABI
   python inject.py --device <serial> --launch
   ```

   **SWF changed:**
   ```bash
   bash tools/patch_swf.sh --deploy
   ```

5. **Smoke test** (always - use the forwarded port from `adb forward --list`):
   ```bash
   curl http://localhost:<bridge-port>/ping
   curl http://localhost:8787/status
   ```

6. **Run functional tests from the execution plan** - execute the API calls, commands, and checks defined in the plan's `## Verification` section. Compare actual output against the documented success criteria.

7. **Report results** - state what was built, deployed, and tested with actual output. Do NOT claim success without evidence.

## Fix-and-Retry Loop

If tests fail or behavior is wrong, do NOT proceed to final verification. Instead:

1. Fix the code (go back to implementation)
2. Re-invoke `build-and-test` - it will reuse the same device and port
3. Repeat until tests pass

```
implement -> build-and-test -> FAIL -> fix code -> build-and-test -> PASS -> verification
```

Only proceed to final verification when `build-and-test` passes.

## Skip Conditions

Do NOT trigger this skill when:
- Only documentation files changed (`*.md`, `docs/`)
- Only config files changed that do not affect runtime
- In a planner session
- The user explicitly says no testing is needed
