---
name: beads-planner
description: "Break a discussed or approved problem into Beads epics and tasks with clear dependencies and validation work. Use when the user wants to turn a problem statement, planning discussion, or approved execution plan into a Beads structure instead of ad-hoc TODOs."
---

# Beads Planner

**Workflow position:** Planner session, after `brainstorming`, any optional `planner-research`, and any optional `plan-debate`. When `plan-beads` invokes this skill, validation should happen immediately after bead creation in the same planner session. See `BEADS_WORKFLOW.md`.

Turn planning output into a Beads structure that another agent or engineer can execute directly.

## Use This Workflow

1. Confirm whether the conversation already produced an approved execution plan or whether `plan-beads` supplied a clear topic that still needs planning.
2. If no plan exists, create a lightweight execution plan first.
3. Translate the approved plan into Beads:
   - one `epic` for the main outcome; use `--type epic` so `bd` recognizes it as an epic and `bd ready --parent` works correctly
   - small executable `task` beads for implementation work
   - `bug` beads for concrete broken behavior
   - `chore` beads for tooling, cleanup, or maintenance work
   - parent all child beads under the epic: `bd dep add <child-id> <epic-id>`
4. Add dependencies explicitly instead of relying on ordering in prose.
5. Include validation work as its own bead when it is meaningful:
   - tests
   - review
   - migration
   - docs
   - target-runtime setup when verification must run on a non-local machine
6. If the epic includes runtime logic changes, make the last bead an end-to-end `build-and-test` bead that depends on all implementation beads.
7. If the epic's verification depends on SSH execution or platform-specific wrapper scripts, add or depend on a standalone runtime-target setup bead before the affected implementation beads.
8. For any bead that may run under `swarm-epic`, encode this execution contract directly in the description or notes:
   - `Read:` exact files, docs, or code areas a fresh worker must inspect before editing
   - `Inputs:` persisted prerequisites only, such as upstream bead ids, committed code, generated artifacts, or bead notes that the worker must rely on
   - `Files:` exact file paths or directory scope the worker may touch
   - `Verify:` exact commands or checks required before success can be reported
   - `Risk:` `low`, `medium`, or `high`
   - `Parallel:` whether the bead can run in parallel and what it must not overlap with
   - `Escalate:` what to do if blocked, underspecified, or forced out of scope

## Planning Rules

- Use the approved plan directly if the session already produced one. Do not re-plan from scratch.
- Keep beads executable by one focused session whenever possible.
- Prefer a few clear beads over a large brainstorm list.
- Keep Beads as the source of truth for task state. Do not create parallel markdown task lists.
- Separate project-level planning from single-task execution plans. Detailed execution plans belong to the execution phase, not the bead decomposition phase.
- Swarm-ready beads should be specific enough that a fresh worker can start from the bead alone plus local code inspection.
- Treat "fresh-session-safe" as the target property for swarm work. A bead may depend on earlier beads, but it must not depend on replaying the prior epic chat.
- Split any bead that spans multiple unrelated code areas, multiple independently testable outcomes, or a broad refactor that would likely force worker context compaction.
- If a later bead needs prior results, persist them in code, artifacts, or bead notes and reference them in `Inputs:` instead of assuming conversational memory.

## Output Shape

- State the proposed epic title when an epic is warranted.
- Group tasks by dependency order.
- Call out tasks that can proceed in parallel.
- Flag important assumptions or unresolved risks that should become beads or notes before execution starts.
- Say whether the resulting epic is ready for `validate-beads` or what still needs to be tightened first.

## Session Boundary - STOP HERE

<HARD-GATE>
This is a planner skill. After beads are created, the session is done.

Do not:

- claim or execute the beads you just created
- invoke `beads-claim`, `writing-plans`, `build-and-test`, `swarm-epic`, or `beads-close`
- start coding or dispatch implementation subagents
- run `bd ready` and pick up work

Do:

- report the created beads and their dependency structure
- if this skill was invoked directly, tell the user: "Beads created. Run `validate-beads` before `swarm-epic`, or claim one with `bd ready` in a manual executor session."
- if `plan-beads` invoked this skill, immediately hand back to `plan-beads` so it can run `validate-beads` before ending the planner session
</HARD-GATE>

