---
name: review-epic
description: "Run an epic-level review after swarm or sequential epic execution. Use after all intended child beads are complete to classify remaining issues as P1, P2, or P3 and decide whether the epic can close or needs follow-up beads."
---

# Review Epic

Run a final quality gate for an epic after implementation is complete.

## Goal

Catch integration, regression, and quality issues that bead-level verification can miss.

## Steps

1. Confirm the target epic and inspect it:
   ```bash
   br show <epic-id> --json --no-db
   ```
2. Review the epic goal, closed child beads, open follow-up beads, and changed files or commits for the branch.
3. Run the final repo-local `build-and-test` workflow if it has not already been run for the whole epic in the current session.
4. Review the epic as a whole:
   - correctness against the epic goal
   - integration between child beads
   - regression risk
   - missing tests or missing verification evidence
   - architectural drift or scope creep
5. Classify findings:
   - `P1`: blocking defect, regression, safety issue, or missing must-have requirement
   - `P2`: important issue that should become follow-up work before broad rollout
   - `P3`: minor cleanup or nice-to-have improvement
6. Act on findings:
   - `P1`: do not close the epic; create or reopen beads and stop
   - `P2`: create follow-up beads and decide whether the epic can still proceed to PR
   - `P3`: note them or create backlog beads if they are worth tracking
7. If the epic is ready:
   - state that the epic passed review
   - summarize any non-blocking follow-up beads
   - proceed to `finishing-a-development-branch <epic-id>`

## Output Format

Present findings first, ordered by severity. Include file references when the finding is tied to a concrete location. Keep the change summary brief and secondary.

## Hard Rules

- Do not treat child bead completion as proof that the epic is complete.
- Do not suppress `P1` issues to preserve momentum.
- Create explicit follow-up beads for meaningful `P2` work instead of burying it in prose.

