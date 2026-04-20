---
name: plan-debate
description: "Run an adversarial review pass on a settled plan before Beads creation. Use in a planner session when the user asks for extra scrutiny or when the plan is risky because it is cross-cutting, migration-heavy, integration-heavy, or intended for swarm execution."
---

# Plan Debate

**Workflow position:** Planner session, after a plan is substantially settled and before `beads-planner`. See `BEADS_WORKFLOW.md`.

Use this skill to pressure-test the settled plan before turning it into Beads.

## Goal

Catch missing decisions, hidden assumptions, weak verification, vague success criteria, and unsafe swarm decomposition before `beads-planner` creates execution work.

## When To Run

Run this skill when:

- the user asks for critique, debate, red-team review, or defense of the plan
- the plan is broad, cross-cutting, or integration-heavy
- migrations or rollout constraints matter
- the plan is likely to go to `swarm-epic`

Do not run this skill for every trivial plan by default. The normal flow is still `brainstorming` -> optional `planner-research` -> settled plan -> `beads-planner`.

## Steps

1. Confirm the plan is already settled enough to critique, even if the user has not yet given the final bead-creation confirmation.
2. Build a structured handoff from the current best plan:
   - `goal`
   - `success_criteria`
   - `constraints`
   - `locked_decisions`
   - `assumptions`
   - `open_risks`
   - `swarm_intent`
   - `plan_text`
3. Invoke the shared runner:
   - `python scripts/shared/run_plan_critic.py --planner-backend <codex|claude|unknown> --critic-backend auto --handoff <json-file>`
   - with `auto`, prefer a different available backend than the planner; if none exists, a fresh isolated session on the same backend is still valid
4. Treat the critic as valid only if it runs in a fresh isolated session. Reusing the planner session, or resuming an older critic thread, does not count.
5. If the critic returns blocking findings:
   - revise the plan text
   - answer the critic's required questions by choosing the planner's recommended resolution whenever a defensible default exists
   - surface a question to the user only when it is a true product or preference decision that cannot be safely settled by the planner
6. Re-run the critic after every material revision. Each re-run should be fresh and should review the current plan, not stale debate history.
7. When the critic returns `approved`, summarize only the compact result:
   - selected backend
   - blocking findings resolved
   - remaining advisory risks
8. Hand back to `plan-beads` for the final bead-creation confirmation, or to `beads-planner` only when that confirmation already happened.

## Rules

- Planner session only.
- Do not create Beads until the debate pass is approved or explicitly skipped.
- Do not pass the full planner transcript by default.
- Do not excuse missing plan content with "we discussed it earlier."
- Do not persist the full debate transcript in the repo or `.beads/`.
- Treat `required_questions` as planner work by default, not automatic user-facing questions.

## Output

- Say whether the plan passed debate.
- List any blocking issues that were fixed before approval.
- Call out remaining advisory risks that should inform `beads-planner` descriptions or notes.
