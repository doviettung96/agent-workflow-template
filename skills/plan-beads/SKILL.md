---
name: plan-beads
description: "Run a planner-only Beads session: brainstorm, produce or confirm an execution plan, get user approval, then create beads and stop. Use when the user wants to turn a current problem or topic into Beads without implementing."
---

# Plan Beads

Run a planner-only Beads session.

## Steps

1. If the current repo is not initialized for Beads, stop and tell the user to run `bd init -p <prefix>` and `bd setup codex`.
2. If the user provided a planning topic in the current request, treat it as the planning topic.
3. Otherwise, use the current conversation topic.
4. If the topic is still unclear, ask clarifying questions before planning.
5. Use `brainstorming` when the problem is still fuzzy or underexplored.
6. Produce or confirm an execution plan.
7. If there are unresolved questions or blockers, ask the user before proceeding. Otherwise, auto-approve and continue.
8. Use `beads-planner` to create or update the beads from the approved plan.
9. Stop after beads are created.

## Hard Rules

- Planner session only.
- Do not claim beads.
- Do not start implementation.
- Do not invoke `beads-claim`, `writing-plans`, repo-local `build-and-test`, or `beads-close`.
- Keep Beads as the source of truth for task state.

## Final Output

- Summarize the approved plan briefly.
- List the created or updated beads and important dependencies.
- End by telling the user that executor work should start in a separate session.
