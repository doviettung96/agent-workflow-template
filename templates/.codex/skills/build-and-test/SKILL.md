---
name: build-and-test
description: "Use after implementing changes to run the exact verification commands from the current execution plan. This stage-1 version is intentionally generic and should be specialized per repo once the runtime workflow is clear."
---

# Build and Test

**Workflow position:** Executor session, between implementation (step 3) and verification (step 6). See BEADS_WORKFLOW.md.

Validate only the components affected by the current changes.

This scaffold is the **stage 1** validator for a brand-new repo. It does not assume a stack, runtime, package manager, build tool, or deployment shape.

Once the repo has a stable runtime workflow, replace this generic version with a repo-specific one that knows the normal build, serve, launch, and smoke-test path.

Project-execution commands may run locally or through an SSH-backed target runtime depending on `.beads/workflow/runtime-target.json`. Keep repo exploration local, but route runtime-dependent verification commands through `scripts/shared/target_runtime.py`.

## Core Rule

Run the **exact commands** from the current plan's `## Verification` section. Do not invent substitute commands because they "seem right."

When the repo uses wrapper scripts for platform differences, use those wrapper commands exactly as written in the plan.

## Steps

### 1. Find the test plan

Read the `## Verification` section of the execution plan saved in `docs/plans/`.

That section must tell you:

- what to build
- what to launch or deploy
- what commands to run
- what output or observed behavior counts as success

If there is no plan file, or the plan has no usable `## Verification` section, stop and say the plan must be updated before `build-and-test` can run.

### 2. Detect what changed

```bash
git diff --name-only HEAD
```

If nothing staged, also check unstaged:

```bash
git diff --name-only
```

### 3. Decide whether validation is required

Use the change list plus the verification plan to decide what to run.

| Changed path | Action |
|---|---|
| Only docs, bead metadata, or notes changed | Skip runtime validation unless the plan explicitly requires it |
| Tests changed without runtime behavior changes | Run the test commands from the plan |
| App/runtime/build/deploy files changed | Run the full verification commands from the plan |

### 4. Validate the verification contract before running anything

Before executing commands, confirm the plan is specific enough.

The `## Verification` section should include exact commands and expected evidence, such as:

- working directory when it matters
- env vars or prerequisites when required
- build command
- launch or serve command
- smoke-test commands such as `curl`, `npm test`, `pytest`, or browser checks
- URLs, ports, endpoints, files, or logs to inspect
- success criteria written as observed output or behavior

If the plan says vague things like "run the app" or "make sure it works," stop and send the work back to `writing-plans` to tighten the verification section.

### 5. Run the plan's verification commands in order

Use the commands exactly as written in the current plan.

Run runtime-dependent commands through:

```bash
python scripts/shared/target_runtime.py run -- <exact command>
```

If `.beads/workflow/runtime-target.json` is missing or still set to `local`, the helper keeps execution local. If the repo configured `ssh`, the helper syncs the repo and runs the command on the selected SSH host instead.

Examples of acceptable stage-1 verification flows:

- `python scripts/shared/target_runtime.py run -- npm run build`, `python scripts/shared/target_runtime.py run -- npm run preview`, then `python scripts/shared/target_runtime.py run -- curl http://127.0.0.1:4173/health`
- `python scripts/shared/target_runtime.py run -- pytest tests/viewer/test_session.py -q`
- `python scripts/shared/target_runtime.py run -- docker compose up -d`, then `python scripts/shared/target_runtime.py run -- curl http://localhost:3000/api/status`
- start a local server and inspect the UI in a browser if the plan explicitly says to do that

When the plan requires manual observation, record what you actually saw. Do not replace it with a lighter automated check unless the plan explicitly allows that.

**Harness-aware runs:** If the plan's verification calls for in-game actions and the repo has `.harness/actions.yaml` (profile=game-re), run those actions via `python scripts/shared/harness.py trigger <action> --json` yourself. Do NOT substitute "ask the user to click X" for a catalogued trigger. If the plan writes "user does X" but an action exists for X, that is a plan defect — return to `writing-plans` before executing. If the plan calls for an action that is not yet catalogued, either catalogue it (small scope) or flag to the user that the plan should either be tightened or a follow-up bead created.

### 6. Capture evidence while running

For each verification command, note:

- the command you ran
- exit code
- relevant output
- any observed UI behavior or logs the plan required
- whether the result matched the stated success criteria

Do not summarize failed checks as "mostly passed." Report the failing step precisely.

### 7. Report results

State exactly what was validated and what evidence you saw.

Minimum report contents:

- changed areas that triggered validation
- verification commands executed
- observed outputs and behavior
- pass/fail status for each major check
- blockers or plan gaps, if any

Do NOT claim success without evidence.

### 8. Stage 2 specialization trigger

If you notice the same build, launch, and smoke-test sequence repeating across beads, that is a signal to specialize this repo-local skill.

Typical stage-2 specialization examples:

- web app: `npm run build`, `npm run preview`, HTTP smoke checks, browser inspection
- CLI tool: package build plus command-line smoke tests
- service: compose or process launch plus API health checks
- device app: app launch plus live-device smoke tests
- mixed local/remote runtime: repo-owned wrapper scripts plus target-runtime-aware verification commands

## Fix-and-Retry Loop

If validation fails or behavior is wrong, do NOT proceed to final verification. Instead:

1. Fix the code or the verification plan
2. Re-run `build-and-test`
3. Repeat until the checks pass

```
implement → build-and-test → FAIL → fix code → build-and-test → PASS → verification
```

Only proceed to final verification when `build-and-test` passes.

## Skip Conditions

Do NOT trigger this skill when:

- the user explicitly says no testing is needed
- in a planner session
- only planner artifacts changed and the current plan does not require validation
