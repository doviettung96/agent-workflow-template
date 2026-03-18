---
name: beads-claim
description: "Use at the start of an executor session to find and claim a ready bead. Do NOT invoke in planner sessions or after brainstorming/beads-planner."
---

# Beads Claim

**Workflow position:** Executor session, step 1 of 7. Next: `writing-plans`. See BEADS_WORKFLOW.md.

Find a ready bead and claim it for this session.

<HARD-GATE>
This is an **executor skill**. It must NOT be invoked in a planner session.

Only invoke this skill when:
- The user wants to start working on implementation
- The session is an executor session

Do NOT invoke this skill when:
- Beads were just created in this session
- You are in the middle of brainstorming or beads-planner
</HARD-GATE>

## Worktree Awareness

When running inside a git worktree, `bd` must be run from the main working tree (where the Dolt database lives). Detect and handle this automatically:

```bash
main_tree=$(git worktree list --porcelain | head -1 | sed 's/worktree //')
# Run bd commands with: cd "$main_tree" && bd ...
```

If you are NOT in a worktree (main tree is the current directory), run `bd` normally.

## Steps

1. **Find ready work:**
   ```bash
   bd ready --json
   ```

2. **Select a bead** - if the user specified one, use that. Otherwise, choose the best ready bead based on current context, priority, and dependencies.

3. **Show the bead details** before claiming:
   ```bash
   bd show <id> --json
   ```

4. **Confirm or auto-claim**:
   - present the bead title and description first
   - if this skill was invoked by `/executor-once` or `/executor-loop` and the bead choice is unambiguous, proceed without an extra confirmation turn
   - if the choice is ambiguous, ask the user before claiming

5. **Claim it:**
   ```bash
   bd update <id> --status=in_progress
   ```

6. **Report** - state the claimed bead ID and title, then proceed to `writing-plans` for the execution plan.

## Rules

- Only claim ONE bead per executor session.
- If no beads are ready, report that and suggest running a planner session first.
- If the user already specified a bead ID, skip the selection step but still show details before claiming.
- When `/executor-once` or `/executor-loop` is driving the flow, it is valid to claim without confirmation when bead choice is unambiguous.
- Do not start coding before claiming. The bead must be `in_progress` before any implementation.
