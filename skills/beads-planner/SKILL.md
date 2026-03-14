---
name: beads-planner
description: Break a discussed or approved problem into Beads epics and tasks with clear dependencies and validation work. Use when the user wants to turn a problem statement, planning discussion, or approved execution plan into a Beads structure instead of ad-hoc TODOs.
---

# Beads Planner

Turn planning output into a Beads structure that another agent or engineer can execute directly.

## Use This Workflow

1. Confirm whether the conversation already produced an approved execution plan.
2. If no plan exists, create a lightweight execution plan first.
3. Translate the approved plan into Beads:
   - one `epic` for the main outcome when it improves coordination
   - small executable `task` beads for implementation work
   - `bug` beads for concrete broken behavior
   - `chore` beads for tooling, cleanup, or maintenance work
4. Add dependencies explicitly instead of relying on ordering in prose.
5. Include validation work as its own bead when it is meaningful:
   - tests
   - review
   - migration
   - docs

## Planning Rules

- Use the approved plan directly if the session already produced one. Do not re-plan from scratch.
- Keep beads executable by one focused session whenever possible.
- Prefer a few clear beads over a large brainstorm list.
- Keep Beads as the source of truth for task state. Do not create parallel markdown task lists.
- Separate project-level planning from single-task execution plans. Detailed execution plans belong to the execution phase, not the bead decomposition phase.

## Output Shape

- State the proposed epic title when an epic is warranted.
- Group tasks by dependency order.
- Call out any tasks that can proceed in parallel.
- Flag important assumptions or unresolved risks that should become beads or notes before execution starts.
