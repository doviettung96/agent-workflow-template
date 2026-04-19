---
name: game-action-harness
description: "Trigger in-game actions as pseudo-human input and observe the effect via memory/log hooks. Use when verifying a hooked function (autopath, autoattack, skill use, UI state) during reverse-engineering work, so the agent can run its own plan → implement → trigger → observe → assert loop without human clicks. Works on Android (adb) and PC (SendInput/PostMessage). Installed only in repos bootstrapped with profile=game-re."
---

# Game Action Harness

## Purpose

Close the "I need a human to click this button" gap during RE work. The harness translates a high-level action name (e.g., `open_inventory`, `skill_1`) into a concrete platform call and reports whether the effect was observed through existing hooks. It is wiring, not instrumentation — the project's own Frida/TCP/capture tooling emits the events; the harness only triggers and tails.

Explicitly NOT vision-based: no OpenCV, no OCR.

## When to use

- You added or suspect a hooked function and need to fire it to confirm the hook fires.
- You are in `writing-plans` and the `## Verification` step is currently "user clicks X" — rewrite it as `harness trigger X` and keep the executor autonomous.
- You are in `systematic-debugging` phase 3 (hypothesis validation) and want to reproduce the condition without leaving the session.
- A swarm worker needs to exercise a feature from a fresh session: point the bead's `Read:` at `.harness/actions.yaml` plus this file.

## When NOT to use

- The project was bootstrapped without `profile=game-re`. The harness files will not be present and the skill is not applicable.
- You need pixel-based detection (OCR, template matching). Out of scope; build that separately.
- The action to trigger is not in the catalog. Add it to `.harness/actions.yaml` first, then run the harness.

## Inputs

Required in the repo:

- `.harness/actions.yaml` — the action catalog (schema in `reference.md`).
- `scripts/shared/harness.py` + `scripts/shared/harness_backends/` — the CLI dispatcher.
- A running game target (emulator/device/process) with the project's existing hooks already attached and emitting events.

Optional:

- `.harness/symbols.yaml` — symbol→address map for `memory` observations.
- `target.observe_log` pointing at the existing hook-log file the Frida/TCP scripts append to.

## Commands

```
python scripts/shared/harness.py probe
python scripts/shared/harness.py list
python scripts/shared/harness.py trigger <action> [--arg k=v ...] [--json]
python scripts/shared/harness.py observe <action> --duration 5s [--json]
```

Every command exits non-zero on failure and emits structured JSON when `--json` is passed. See `reference.md` for the full schema.

## Decision flow

1. If `.harness/actions.yaml` does not exist, stop and flag the "Populate action catalog" stage-2 bead as the prerequisite. Do not invent actions ad hoc inside a verification step.
2. Run `harness probe`. If any declared bridge is down (adb device missing, observe log not writable, target window not found), stop and report — never silently fall through to a partial trigger.
3. Run `harness list` to confirm the action name exists. If it does not, add it to the catalog first, then retry.
4. Run `harness trigger <action> --json`. Parse the result:
   - `status=ok` + `observe.matched=true` → proceed.
   - `status=ok` + `observe.matched=false` → the input fired but no hook event matched within the timeout. Treat as a real negative signal, not a harness bug.
   - `status=bridge_down` → infrastructure issue; diagnose, do not retry the action.
   - `status=timeout` on invoke → the input call itself stalled; diagnose adb/SendInput, do not retry blindly.
5. Record the returned `evidence` line in the bead notes or plan's verification section so the trigger is reproducible.

## Hard rules

- The harness must not reimplement hooking. Observation reads what existing hooks already emit; if an action has no observer defined, the catalog entry is incomplete.
- Never add a vision/OCR backend here. That belongs in a separate skill if it ever becomes wanted.
- Never overwrite a downstream `.harness/actions.yaml` during `update-skills`. Treat it the same as `runtime-target.json` and `build-and-test`.
- Never commit machine-specific device serials, window handles, or process IDs to the template. `.harness/actions.yaml` ships as an example; concrete values live in the downstream checkout only.
- Do not auto-trigger actions in a loop without an upper bound. The harness is a test tool, not an automation engine.

## Reporting

When invoked as part of a plan's verification, report:

- exact command executed
- returned JSON (abbreviated to status + observe.matched + evidence)
- whether this matches the plan's expectation
- any bridge that came up dirty during `probe`

## Related skills and files

- `writing-plans` — plans that exercise hooked code should emit `harness trigger` in `## Verification`.
- `systematic-debugging` — phase 3 hypothesis validation can drive the harness directly.
- `reference.md` — catalog schema, backend list, JSON output shape.
- `templates/actions.yaml.example` — minimal starter catalog.
- `templates/symbols.yaml.example` — optional symbol map.
