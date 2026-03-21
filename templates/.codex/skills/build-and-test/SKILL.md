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
| Launch args | `--no-ui` |

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

### 5. Kill any existing process

```bash
taskkill /F /IM BotName.exe 2>/dev/null || true
```
Wait a moment for ports to free up.

### 6. Launch the exe

```bash
./dist/BotName.exe --no-ui &
```

Wait for the API server to become available:
```bash
for i in $(seq 1 30); do
  curl -s http://localhost:8787/ping && break
  sleep 2
done
```

### 7. Smoke tests (always)

```bash
curl -s http://localhost:8787/ping
curl -s http://localhost:8787/status
```

Both must return valid JSON responses.

### 8. Functional tests

Run the verification plan. This means testing the **actual behavior** the bead changed — not just that endpoints return 200. If the bead changed campaign logic, start a campaign and verify it progresses. If it changed login flow, trigger login and verify success. The execution plan's `## Verification` section defines exactly what to test and what success looks like.

Compare actual output and observed behavior against the documented success criteria.

### 9. Report results

State what was built, launched, and tested with actual output. Do NOT claim success without evidence.

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
