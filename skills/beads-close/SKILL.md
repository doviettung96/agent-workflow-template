---
name: beads-close
description: "Use after implementation and verification are complete to close the bead, create follow-up beads, and commit the updated `.beads/` state. This is the final step of a manual executor or worker-backed coordinator session."
---

# Beads Close

**Workflow position:** executor closeout, final step after verification. See `BEADS_WORKFLOW.md`.

Close the current bead and commit the updated tracker state.

<HARD-GATE>
Before invoking this skill, the following must already be true:

- a bead was claimed at the start of this session
- implementation is complete
- verification has been run (`verification-before-completion` or `requesting-code-review`)
- if implementation was done by `execute-bead-worker`, the coordinator has reviewed the worker report and verification evidence

Do not invoke this skill:

- in a planner session
- before verification
- to close beads outside the current executor or coordinator session
- from `execute-bead-worker`; workers report back to the coordinator instead
</HARD-GATE>

## Steps

1. Record a closeout note before closing the bead so later work can rely on persisted state instead of session memory:
   ```bash
   br comments add <id> --message "Outcome: <what changed>\nPersisted: <committed files, generated artifacts, or bead notes>\nDownstream: <what later beads can now rely on>" --no-db
   ```
2. Close the bead:
   ```bash
   br close <id> --reason "Completed: <brief summary of what was done>" --no-db
   ```
3. Create follow-up beads if new work was discovered during implementation:
   ```bash
   br create "Follow-up: ..." --description "Discovered during <id>: ..." --type task --no-db
   br dep add <new-id> <other-id> --no-db
   ```
4. Commit code changes:
   ```bash
   git add <changed files>
   git commit -m "<type>: <description>"
   ```

## Rules

- If execution was blocked and the bead is not complete, do not close it. Instead update it:
  ```bash
  br update <id> --notes "Blocked: <reason>" --no-db
  ```
- When `executor-loop`, `executor-loop-epic`, or any other loop is driving the workflow, hand control back to the loop after the current bead is closed and the local commit is complete.
- Work happens on feature branches. Merging to `main` is done via PR, not local merge.
- Live `.beads` state is local runtime. Do not treat it as something to publish through Git during normal closeout.
- `swarm-epic`, `executor-once`, and `executor-loop-epic` own bead status transitions while coordinating worker-backed runs. Workers never call `beads-close`.
- Keep the closeout note concise but concrete. It should tell a fresh downstream worker what changed, where the result lives, and what is now safe to assume.
