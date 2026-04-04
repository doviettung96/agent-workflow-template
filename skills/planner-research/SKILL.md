---
name: planner-research
description: "Planner-only research step for resolving factual unknowns after brainstorming and before Beads creation. Use only when unresolved technical or domain uncertainty would materially weaken the plan."
---

# Planner Research

Resolve factual unknowns that still matter after `brainstorming` and before `beads-planner`.

This skill is intentionally narrow. It exists to improve the quality of the approved design and the resulting Beads. It does not create a second planning system.

## When To Use This

Use `planner-research` only when one or more unresolved factual unknowns would materially affect:

- architecture or feasibility
- integration points or file ownership
- library, framework, or platform behavior
- external API constraints
- the clarity of swarm-ready bead contracts

Do not use this skill for user preferences, product decisions, or speculative "nice to know" investigation.

## Workflow Position

Planner session only, between `brainstorming` and `beads-planner`.

Typical flow:

1. `brainstorming`
2. `planner-research` if needed
3. approve the refined design
4. `beads-planner`
5. `validate-beads` when the epic is intended for swarm execution

## Required Behavior

1. Start by listing the concrete unknowns that need answers.
2. Prioritize only the unknowns that would change the plan or bead decomposition.
3. Investigate using local repo inspection first, then user-provided references, then external authoritative sources when needed.
4. Summarize findings in terms of planning impact:
   - what was confirmed
   - what assumption changed
   - what remains unresolved
   - how the plan or bead contract should change
5. Fold those findings back into the approved design/spec and any bead notes or descriptions.

## Output Shape

Keep the output compact and decision-oriented:

- `Unknowns:` the specific questions being answered
- `Findings:` the factual answers with source context
- `Planning impact:` what changes in the design or Beads because of those findings
- `Remaining risks:` only if something still cannot be resolved

## Hard Rules

- Planner session only.
- Do not create a separate planning tracker, roadmap tree, or research state system.
- Do not claim Beads, write implementation code, or start execution.
- Do not use research as a substitute for asking the user preference questions.
- Keep Beads as the only task-state system.

## Done Condition

Stop once the research has reduced uncertainty enough that `beads-planner` can create high-quality executable Beads without replaying the entire investigation.
