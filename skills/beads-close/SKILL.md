---
name: beads-close
description: "Use after implementation and verification are complete to close the bead, create follow-up beads, and sync local state. This is the final step of an executor session."
---

# Beads Close

**Workflow position:** Executor session, step 7 of 7 (final step, after verification). See BEADS_WORKFLOW.md.

Close the current bead and sync local state. This is the last step of an executor session, after `build-and-test` and verification are done.

<HARD-GATE>
Before invoking this skill, the following MUST already be true:
- A bead was claimed at the start of this session
- Implementation is complete
- Verification has been run (`verification-before-completion` or `requesting-code-review`)

Do NOT invoke this skill:
- In a planner session
- Before verification
- To close beads you did not work on in this session
</HARD-GATE>

## Steps

1. **Close the bead:**
   ```bash
   bd close <id> --reason "Completed: <brief summary of what was done>"
   ```

2. **Create follow-up beads** if new work was discovered during implementation:
   ```bash
   bd create --title="Follow-up: ..." --description="Discovered during <id>: ..." --type=task
   bd dep add <new-id> <other-id>
   ```

3. **Sync beads state:**
   ```bash
   bd dolt pull
   ```

4. **Commit code changes:**
   ```bash
   git add <changed files>
   git commit -m "<type>: <description>"
   ```

## Rules

- If execution was blocked and the bead is NOT complete, do NOT close it. Instead update it:
  ```bash
  bd update <id> --notes="Blocked: <reason>"
  ```
- When `/executor-loop` is driving the workflow, hand control back to the loop only after the current bead is closed and the local commit is complete.
- If multiple beads were completed, close them together:
  ```bash
  bd close <id1> <id2> ... --reason "Completed"
  ```
- This repo uses ephemeral branches merged to main locally - there is no upstream push.
- Always run `bd dolt pull` before committing to avoid sync conflicts.
