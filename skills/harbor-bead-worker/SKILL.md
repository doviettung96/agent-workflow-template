---
name: harbor-bead-worker
description: "Execute one assigned bead inside a tmux pane spawned by the harbor runner. Use when an agent CLI (codex, claude) is launched by `harbor run-bead` or `harbor run-epic` with the bead contract injected on stdin; the worker implements, verifies locally, and emits a HARBOR-DONE sentinel without mutating Beads state."
---

# Harbor Bead Worker

Implement one bead inside a tmux pane the harbor daemon launched. This is the
tmux-launcher counterpart to `execute-bead-worker`: the contract and hard rules
are nearly identical, but the invocation context is different — there is no
coordinator chat session to report back to, only a stdin prompt and a sentinel
line the daemon parses from your final output.

## Goal

Deliver one bead safely inside the boundaries the harbor runner injected via
the prompt, then emit the completion sentinel so the daemon can close the bead
or surface a blocker.

## Steps

1. The prompt you received is your full assignment. Treat your context as fresh
   — there is no prior chat memory you can rely on. Required sections in the
   bead description:
   - `Read:` — files to inspect first
   - `Inputs:` — persisted prerequisites (if any)
   - `Files:` — the only files you may edit
   - `Verify:` — commands you must run before reporting success
   If any of those sections is missing, stop and emit a `blocked` sentinel with
   `classification=contract`.
2. Read each `Read:` target plus any code those files reference. Do not browse
   beyond what the bead requires.
3. Implement only inside the `Files:` scope. Do not edit other files.
4. Run each `Verify:` command. Fix failures only if the fix is inside `Files:`
   scope and the contract still applies; otherwise stop and emit a `blocked`
   sentinel with `classification=scope` (work needs splitting) or
   `classification=contract` (the bead is wrong).
5. Print a short summary of what changed and the verify outcome.
6. Emit the completion sentinel as your final line:

   ```
   HARBOR-DONE: <bead-id> status=ok classification=none
   ```

   or, if you cannot finish:

   ```
   HARBOR-DONE: <bead-id> status=blocked classification=clarify
   HARBOR-DONE: <bead-id> status=blocked classification=env
   HARBOR-DONE: <bead-id> status=blocked classification=contract
   HARBOR-DONE: <bead-id> status=blocked classification=scope
   ```

   Print nothing after this line. The daemon reads it to decide whether to
   close the bead or leave it open with a blocker note.

## Hard rules

- Do not run `br update`, `br close`, or any other bead-state command — the
  harbor daemon is the sole writer.
- Do not call `agent-mail.ps1` / `agent-mail.sh`. The daemon registers your
  worker identity, reserves your file scope, and releases reservations on
  your behalf.
- Do not expand the file scope. If you discover you need files outside
  `Files:`, emit a `blocked` sentinel with `classification=scope`.
- Do not skip verification. If verify cannot run because of an environment
  issue you cannot fix locally, emit a `blocked` sentinel with
  `classification=env`.
- Do not print anything after the sentinel line. The daemon's parser uses the
  last `HARBOR-DONE: <id> ...` line in your output, but a multi-line trailing
  noise is more likely to confuse a human attaching to the pane.

## Classification reference

- `clarify` — small missing fact or wording. The next worker (or you, on
  retry) needs one piece of information.
- `env` — environment, runtime, credential, or harness problem. Fix the
  environment, then retry.
- `contract` — the bead description is incomplete or wrong. The bead must be
  edited before retry.
- `scope` — the work crosses boundaries the bead declared. Split the bead or
  rewrite its `Files:` scope, then retry.

## Differences from `execute-bead-worker`

The tmux-launched flow trims the cooperative bookkeeping that the chat
coordinator handles in the existing skill:

| Step                              | execute-bead-worker | harbor-bead-worker |
|-----------------------------------|---------------------|--------------------|
| Worker registers in Agent Mail    | Yes (worker call)   | No (daemon does it) |
| Worker reserves files             | Yes (worker call)   | No (daemon does it) |
| Worker writes `HANDOFF.json`      | Yes                 | No (daemon writes state.json) |
| Worker posts `started`/`completed` to thread | Yes      | No (daemon posts on its behalf) |
| Worker reports completion         | Structured message back to coordinator | `HARBOR-DONE` sentinel line |
| Coordinator runs verify           | No (worker runs it, coordinator reviews) | Both — worker runs verify locally; daemon runs it again before closing the bead |

Everything else (the fresh-worker mental model, the file-scope discipline, the
hard rule against bead-state mutation) is identical.
