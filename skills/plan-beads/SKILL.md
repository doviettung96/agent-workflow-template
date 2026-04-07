---
name: plan-beads
description: "Run a planner-only Beads session: brainstorm, produce or confirm an execution plan, get user approval, then create beads and stop. Use when the user wants to turn a current problem or topic into Beads without implementing."
---

# Plan Beads

Run a planner-only Beads session.

## Steps

1. If the current repo is not initialized for Beads, stop and tell the user to run the template bootstrap script or at minimum `bd init --prefix <prefix>` plus the repo scaffolding steps.
2. If the user provided a planning topic in the current request, treat it as the planning topic.
3. Otherwise, use the current conversation topic.
4. If the topic is still unclear, ask clarifying questions before planning.
5. Use `brainstorming` when the problem is still fuzzy or underexplored.
6. If `brainstorming` leaves material factual uncertainty that affects architecture, feasibility, integration points, or swarm bead quality, use `planner-research` before finalizing the plan.
7. Produce or confirm an execution plan using the discussion and any planner research findings.
8. If there are unresolved questions or blockers, ask the user before proceeding. Otherwise, auto-approve and continue.
9. Use `beads-planner` to create or update the beads from the approved plan.
10. If the plan is intended for epic-scoped autonomous execution, immediately run `validate-beads` in the same planner session.
11. If validation fails, tighten the beads, dependencies, or execution contract, then re-run `validate-beads` before ending the session.
12. Stop after the beads are created and either validated for swarm execution or explicitly marked as manual-only.

## Hard Rules

- Planner session only.
- Do not claim beads.
- Do not start implementation.
- Do not create a parallel planning tracker or second source of truth outside the approved plan/spec plus Beads.
- Do not invoke `beads-claim`, `writing-plans`, repo-local `build-and-test`, `swarm-epic`, or `beads-close`.
- Keep Beads as the source of truth for task state.

## Final Output

- Summarize the approved plan briefly.
- List the created or updated beads and important dependencies.
- Say whether the epic passed `validate-beads` or why it is manual-only.
- End by telling the user that executor work should start in a separate session.

