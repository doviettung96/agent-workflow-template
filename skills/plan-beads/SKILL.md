---
name: plan-beads
description: "Run a planner-only Beads session: brainstorm, produce or confirm an execution plan, resolve critique, brief the user once for bead creation, then create beads and stop. Use when the user wants to turn a current problem or topic into Beads without implementing."
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
8. Keep moving autonomously through normal design uncertainty. Ask the user only when a missing decision is genuinely product-defining, preference-sensitive, or too risky to choose on the user's behalf.
9. If the user asked for critique or the plan is risky because it is cross-cutting, migration-heavy, integration-heavy, or intended for autonomous swarm execution, run `plan-debate` before Beads creation.
10. Incorporate debate feedback into the plan. By default, resolve critic questions by choosing the planner's recommended answer and revising the plan accordingly. Escalate to the user only when the critic exposed a real product decision that the planner cannot safely settle.
11. Once the plan is settled and ready to translate, stop once to brief the user on the final recommended plan and ask for confirmation to create Beads.
12. After confirmation, use `beads-planner` to create or update the beads from the settled plan.
13. If the plan is intended for epic-scoped autonomous execution, immediately run `validate-beads` in the same planner session.
14. If validation fails, tighten the beads, dependencies, or execution contract, then re-run `validate-beads` before ending the session.
15. Stop after the beads are created and either validated for swarm execution or explicitly marked as manual-only.

## Hard Rules

- Planner session only.
- Do not claim beads.
- Do not start implementation.
- Do not create a parallel planning tracker or second source of truth outside the settled plan/spec plus Beads.
- Do not invoke `beads-claim`, `writing-plans`, repo-local `build-and-test`, `swarm-epic`, or `beads-close`.
- Keep Beads as the source of truth for task state.
- If `plan-debate` is triggered, do not let `beads-planner` run until the critic pass is approved or explicitly skipped by the user.
- The default planner posture is to resolve critic questions with the planner's recommended answer, not to bounce every question to the user.
- In the normal flow, the explicit user confirmation gate is the bead-creation handoff right before `beads-planner`.

## Final Output

- Summarize the settled plan briefly.
- Say whether `plan-debate` ran or was skipped.
- List the created or updated beads and important dependencies.
- Say whether the epic passed `validate-beads` or why it is manual-only.
- End by telling the user that executor work should start in a separate session.

