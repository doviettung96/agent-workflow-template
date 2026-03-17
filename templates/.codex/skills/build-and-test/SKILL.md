---
name: build-and-test
description: "Use after implementing code changes to build, deploy, and test the affected components. Only build what changed."
---

# Build and Test

**Workflow position:** Executor session, between implementation (step 3) and verification (step 6). See BEADS_WORKFLOW.md.

Build, deploy, and test only the components affected by the current changes.

> **CUSTOMIZE THIS SKILL** for your project. Replace the placeholder sections below
> with your project's actual build commands, deploy steps, and test commands.
> This file is NOT synced by `update-skills` — it is your project's own.

## Steps

1. **Find the test plan** - read the `## Verification` section of the execution plan saved in `docs/plans/`. This tells you exactly what to build, deploy, and test.

2. **Detect what changed:**
   ```bash
   git diff --name-only HEAD
   ```
   If nothing staged, also check unstaged:
   ```bash
   git diff --name-only
   ```

3. **Build affected components** based on changed paths:

   <!-- Replace this table with your project's build mapping -->
   | Changed path | Action |
   |---|---|
   | `src/` | Rebuild (TODO: your build command) |
   | `tests/` | No build needed, run tests |

4. **Deploy if needed:**

   <!-- Replace with your project's deploy commands -->
   ```bash
   # TODO: your deploy command here
   ```

5. **Run tests:**

   <!-- Replace with your project's test commands -->
   ```bash
   # TODO: your test command here
   ```

6. **Report results** - state what was built, deployed, and tested with actual output. Do NOT claim success without evidence.

## Fix-and-Retry Loop

If tests fail or behavior is wrong, do NOT proceed to final verification. Instead:

1. Fix the code (go back to implementation)
2. Re-invoke `build-and-test`
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
