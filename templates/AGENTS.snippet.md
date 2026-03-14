## Workflow Guide

Use `BEADS_WORKFLOW.md` for the current planner/executor flow and the role of the Beads-related skills.
For Codex, the preferred workflow entry points are the global skills `plan-beads`, `executor-once`, and `executor-loop` installed under `~/.codex/skills`.
For Codex, the repo-local executor test skill lives at `.codex/skills/build-and-test/SKILL.md`; use it between implementation and final verification.

Important:

- keep this section outside the Beads-managed `AGENTS.md` block
- do not edit inside `<!-- BEGIN BEADS INTEGRATION --> ... <!-- END BEADS INTEGRATION -->`
