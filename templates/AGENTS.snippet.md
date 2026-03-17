## Workflow Guide

Use `BEADS_WORKFLOW.md` for the current planner/executor flow and the role of the Beads-related skills.
All workflow skills are repo-local: Codex skills live under `.codex/skills/`, Claude skills under `.claude/skills/`.
The preferred workflow entry points are `plan-beads`, `executor-once`, `executor-loop`, and `executor-loop-epic`.
The executor test skill lives at `.codex/skills/build-and-test/SKILL.md`; use it between implementation and final verification.

Important:

- keep this section outside the Beads-managed `AGENTS.md` block
- do not edit inside `<!-- BEGIN BEADS INTEGRATION --> ... <!-- END BEADS INTEGRATION -->`
