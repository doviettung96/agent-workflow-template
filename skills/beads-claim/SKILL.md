---
name: beads-claim
description: "Use at the start of an executor or coordinator session to find and claim a ready bead. Do not invoke in planner sessions or inside workers."
---

# Beads Claim

**Workflow position:** executor start. Next step is either worker assignment (`executor-once` / `executor-loop-epic`) or `writing-plans` (`executor-loop`). See `BEADS_WORKFLOW.md`.

Find a ready bead and claim it for this session.

<HARD-GATE>
This is an executor/coordinator skill. It must not be invoked in a planner session or inside `execute-bead-worker`.

Only invoke this skill when:

- the user wants to start implementation
- the session is an executor or coordinator session

Do not invoke this skill when:

- beads were just created in this session
- you are in the middle of `brainstorming` or `beads-planner`
- `swarm-epic` already assigned the bead to a worker
</HARD-GATE>

## Steps

1. If the current repo is not initialized for Beads, stop and tell the user to run the template bootstrap script or at minimum `br init --prefix <prefix> --no-db` plus the repo scaffolding steps.
2. Find ready work:
   ```bash
   br ready --json --no-db
   ```
3. Select a bead. If the user specified one, use that. Otherwise, choose the best ready bead based on current context, priority, and dependencies.
4. Show the bead details before claiming:
   ```bash
   br show <id> --json --no-db
   ```
5. Confirm or auto-claim:
   - present the bead title and description first
   - if this skill was invoked by `executor-once`, `executor-loop`, or `executor-loop-epic` and the bead choice is unambiguous, proceed without an extra confirmation turn
   - if the choice is ambiguous, ask the user before claiming
6. Claim it:
   ```bash
   br update <id> --status in_progress --no-db
   ```
7. Report the claimed bead id and title:
   - for `executor-once` or `executor-loop-epic`, return to the coordinator flow so it can dispatch `execute-bead-worker`
   - for `executor-loop`, proceed to `writing-plans`

## Rules

- Only claim one bead per executor cycle.
- If no beads are ready, report that and suggest running a planner session first.
- If the user already specified a bead id, skip the selection step but still show details before claiming.
- When `executor-once`, `executor-loop`, or `executor-loop-epic` is driving the flow, it is valid to claim without confirmation when bead choice is unambiguous.
- Do not start coding before claiming. The bead must be `in_progress` before any implementation.
- `swarm-epic` owns claiming and closing for swarm runs. Workers do not call this skill.
