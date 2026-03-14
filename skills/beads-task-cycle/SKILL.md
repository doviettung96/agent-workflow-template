---
name: beads-task-cycle
description: "Deprecated compatibility shim for older prompts that still mention beads-task-cycle. Use only to route to the split executor workflow: beads-claim, writing-plans, build-and-test, verification, and beads-close."
---

# Beads Task Cycle (Deprecated)

This skill is kept only for backward compatibility with older prompts. Do not use it as the primary executor workflow.

## Current Executor Workflow

1. Start with `beads-claim`
2. Use `writing-plans`
3. Implement
4. Use `systematic-debugging` if blocked
5. Use repo-local `build-and-test`
6. Run `verification-before-completion` or `requesting-code-review`
7. Finish with `beads-close`

## Routing Rules

- If the user is starting executor work, invoke `beads-claim`.
- If the user is mid-implementation and needs a local plan, invoke `writing-plans`.
- If the user is ready to build or verify runtime changes, use repo-local `build-and-test`.
- If the user has finished implementation and verification, invoke `beads-close`.

Do not introduce a separate monolithic lifecycle on top of the split workflow.
