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
9. If the user asked for critique or the plan is risky because it is cross-cutting, migration-heavy, integration-heavy, or intended for autonomous swarm execution, run `plan-debate` before Beads creation.
10. Use `beads-planner` to create or update the beads from the approved plan.
11. If the plan is intended for epic-scoped autonomous execution, immediately run `validate-beads` in the same planner session.
12. If validation fails, tighten the beads, dependencies, or execution contract, then re-run `validate-beads` before ending the session.
13. Stop after the beads are created and either validated for swarm execution or explicitly marked as manual-only.

## Hard Rules

- Planner session only.
- Do not claim beads.
- Do not start implementation.
- Do not create a parallel planning tracker or second source of truth outside the approved plan/spec plus Beads.
- Do not invoke `beads-claim`, `writing-plans`, repo-local `build-and-test`, `swarm-epic`, or `beads-close`.
- Keep Beads as the source of truth for task state.
- If `plan-debate` is triggered, do not let `beads-planner` run until the critic pass is approved or explicitly skipped by the user.

## Final Output

- Summarize the approved plan briefly.
- Say whether `plan-debate` ran or was skipped.
- List the created or updated beads and important dependencies.
- Say whether the epic passed `validate-beads` or why it is manual-only.
- End by telling the user that executor work should start in a separate session.

