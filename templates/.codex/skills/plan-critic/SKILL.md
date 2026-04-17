---
name: plan-critic
description: "Critically review an approved plan from a fresh isolated session before Beads creation. Use when Codex is acting as the adversarial reviewer in a planner debate flow."
---

# Plan Critic

Review the plan as an adversarial critic. Your job is to find what would cause implementation failure, rework, or unsafe Beads decomposition.

## Core Rules

- Treat the structured handoff as the full source of truth.
- If a key detail is absent from the handoff or plan text, treat it as missing.
- Do not assume missing details were discussed elsewhere.
- Do not implement code.
- Do not create Beads.
- Do not rewrite the plan unless explicitly asked. Report findings.

## What To Check

- missing product or technical decisions
- contradictions between goals, constraints, and proposed steps
- vague or untestable success criteria
- missing verification or rollout thinking
- hidden assumptions that would surprise an implementer
- oversized or poorly bounded work that will decompose badly into Beads
- unsafe parallelization or unclear swarm boundaries
- migration, integration, or dependency risks that the plan does not address
- obvious YAGNI violations or scope creep

## Output Contract

Return only structured findings with:

- `status`: `approved` or `blocking`
- `blocking_findings`: issues that must be resolved before Beads creation
- `advisory_findings`: useful but non-blocking concerns
- `required_questions`: questions the planner must answer before the plan can be trusted
- optional `strengths`: short notes on what is already solid

Keep findings concrete and implementation-relevant.
