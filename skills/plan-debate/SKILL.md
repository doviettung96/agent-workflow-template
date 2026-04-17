---
name: plan-debate
description: "Run an adversarial review pass on an approved plan before Beads creation. Use in a planner session when the user asks for extra scrutiny or when the plan is risky because it is cross-cutting, migration-heavy, integration-heavy, or intended for swarm execution."
---

# Plan Debate

**Workflow position:** Planner session, after a plan is approved and before `beads-planner`. See `BEADS_WORKFLOW.md`.

Use this skill to pressure-test the approved plan before turning it into Beads.

## Goal

Catch missing decisions, hidden assumptions, weak verification, vague success criteria, and unsafe swarm decomposition before `beads-planner` creates execution work.

## When To Run

Run this skill when:

- the user asks for critique, debate, red-team review, or defense of the plan
- the plan is broad, cross-cutting, or integration-heavy
- migrations or rollout constraints matter
- the plan is likely to go to `swarm-epic`

Do not run this skill for every trivial plan by default. The normal flow is still `brainstorming` -> optional `planner-research` -> approved plan -> `beads-planner`.

## Steps

1. Confirm the plan is already approved by the user or explicitly auto-approved by `plan-beads`.
2. Build a structured handoff from the approved plan:
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
   - answer the critic's required questions if the answers are already known
   - surface unresolved product decisions to the user if they are still open
6. Re-run the critic after every material revision. Each re-run should be fresh and should review the current plan, not stale debate history.
7. When the critic returns `approved`, summarize only the compact result:
   - selected backend
   - blocking findings resolved
   - remaining advisory risks
8. Hand back to `plan-beads` or `beads-planner`.

## Rules

- Planner session only.
- Do not create Beads until the debate pass is approved or explicitly skipped.
- Do not pass the full planner transcript by default.
- Do not excuse missing plan content with "we discussed it earlier."
- Do not persist the full debate transcript in the repo or `.beads/`.

## Output

- Say whether the plan passed debate.
- List any blocking issues that were fixed before approval.
- Call out remaining advisory risks that should inform `beads-planner` descriptions or notes.
