---
name: beads-close
description: "Use after implementation and verification are complete to close the bead, create follow-up beads, and commit the updated `.beads/` state. This is the final step of a manual executor session."
---

# Beads Close

**Workflow position:** Manual executor session, step 7 of 7. Final step after verification. See `BEADS_WORKFLOW.md`.

Close the current bead and commit the updated tracker state.

<HARD-GATE>
Before invoking this skill, the following must already be true:

- a bead was claimed at the start of this session
- implementation is complete
- verification has been run (`verification-before-completion` or `requesting-code-review`)

Do not invoke this skill:

- in a planner session
- before verification
- to close beads you did not work on in this session
- from `execute-bead-worker`; swarm workers report back to the coordinator instead
</HARD-GATE>

## Steps

1. Close the bead:
   ```bash
   bd close <id> --reason "Completed: <brief summary of what was done>"
   ```
2. Create follow-up beads if new work was discovered during implementation:
   ```bash
   bd create "Follow-up: ..." --description "Discovered during <id>: ..." --type task
   bd dep add <new-id> <other-id>
   ```
3. Commit code changes:
   ```bash
   git add <changed files>
   git commit -m "<type>: <description>"
   ```

## Rules

- If execution was blocked and the bead is not complete, do not close it. Instead update it:
  ```bash
  bd update <id> --notes "Blocked: <reason>"
  ```
- When `executor-loop`, `executor-loop-epic`, or any other manual loop is driving the workflow, hand control back to the loop after the current bead is closed and the local commit is complete.
- Work happens on feature branches. Merging to `main` is done via PR, not local merge.
- Live `.beads` state is local runtime. Do not treat it as something to publish through Git during normal closeout.
- `swarm-epic` owns bead status transitions during swarm runs. Workers never call `beads-close`.

