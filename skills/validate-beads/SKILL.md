---
name: validate-beads
description: "Validate a planned epic before autonomous execution. Use after beads-planner and before swarm-epic to check dependency quality, bead size, file scope, verification instructions, and parallel-safety notes."
---

# Validate Beads

Run a pre-execution quality gate for an epic before autonomous execution starts.

## Goal

Catch planning defects before workers start coding. This is a planner-side validation pass, not an implementation step.

## Steps

1. If the current repo is not initialized for Beads, stop and tell the user to run the template bootstrap script or at minimum `bd init --prefix <prefix>` plus the repo scaffolding steps.
2. Determine the target epic:
   - if the user supplied an epic id, use it
   - otherwise use the most recent planning context and ask only if the target epic is ambiguous
3. Inspect the epic and its child beads. Use `bd show <epic-id> --json` plus the current planning context and `.beads/` state as needed.
4. Validate the epic against this checklist:
   - the target is actually an epic
   - child beads are small enough for one focused worker session
   - dependencies are explicit and coherent
   - no two child beads describe the same work
   - there is a meaningful final integration or `build-and-test` bead when runtime behavior changed
   - every swarm-ready bead includes:
     - `Files:`
     - `Verify:`
     - `Risk:`
     - `Parallel:`
     - `Escalate:`
   - beads marked as parallel do not obviously overlap the same file scope
5. Classify findings:
   - blocking: missing execution contract, duplicate work, broken dependency shape, oversized bead
   - non-blocking: wording cleanup, minor note improvements
6. If blocking findings exist:
   - do not start `swarm-epic`
   - update beads, notes, or dependencies until the blockers are removed
   - report exactly what still needs to change
7. If the epic passes:
   - report that the epic is validated for swarm execution
   - identify the first ready descendants or likely first wave
   - recommend `start-epic-worktree` followed by `swarm-epic`

## Hard Rules

- Do not claim beads.
- Do not implement code.
- Do not approve a swarm run while any bead is missing `Files` or `Verify`.
- When in doubt about parallel safety, fail closed and mark the work as sequential.

