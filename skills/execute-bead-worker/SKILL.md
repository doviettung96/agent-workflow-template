---
name: execute-bead-worker
description: "Execute one assigned bead inside a swarm coordinated by swarm-epic. Use only when a coordinator has assigned the bead, file scope, and verification contract; the worker implements, verifies, and reports without mutating bead state."
---

# Execute Bead Worker

Implement one assigned bead inside a swarm run.

## Goal

Deliver one bead safely inside the boundaries set by `swarm-epic`.

## Steps

1. Confirm the assignment from the coordinator:
   - epic id
   - bead id
   - `Files:` scope
   - `Verify:` commands or checks
   - reservation or conflict instructions
2. Read the bead details and inspect the relevant code.
3. If the bead is underspecified or missing `Files` or `Verify`, stop and return it to the coordinator instead of guessing.
4. Register the worker and inspect its inbox:
   - Windows:
     ```powershell
     .\scripts\windows\agent-mail.ps1 --repo . register --name worker/<bead-id> --role worker --epic-id <epic-id> --bead-id <bead-id>
     .\scripts\windows\agent-mail.ps1 --repo . inbox --recipient worker/<bead-id>
     ```
   - POSIX:
     ```bash
     ./scripts/posix/agent-mail.sh --repo . register --name worker/<bead-id> --role worker --epic-id <epic-id> --bead-id <bead-id>
     ./scripts/posix/agent-mail.sh --repo . inbox --recipient worker/<bead-id>
     ```
5. Reserve the declared file scope before editing through the shared control plane:
   - Windows:
     ```powershell
     .\scripts\windows\agent-mail.ps1 --repo . reserve --owner worker/<bead-id> --epic-id <epic-id> --bead-id <bead-id> --path <path1> --path <path2>
     ```
   - POSIX:
     ```bash
     ./scripts/posix/agent-mail.sh --repo . reserve --owner worker/<bead-id> --epic-id <epic-id> --bead-id <bead-id> --path <path1> --path <path2>
     ```
   If reservation fails, stop and report the conflict to the coordinator.
6. Update `.beads/workflow/HANDOFF.json` for this worker context:
   - `role`
   - `epic_id`
   - `bead_id`
   - `summary`
   - `next_action`
7. Post a `started` message to `bead/<bead-id>` so the coordinator and other sessions can see who owns the bead.
   - Windows:
     ```powershell
     .\scripts\windows\agent-mail.ps1 --repo . post --thread bead/<bead-id> --sender worker/<bead-id> --type started --body '{"status":"started"}' --epic-id <epic-id> --bead-id <bead-id>
     ```
   - POSIX:
     ```bash
     ./scripts/posix/agent-mail.sh --repo . post --thread bead/<bead-id> --sender worker/<bead-id> --type started --body '{"status":"started"}' --epic-id <epic-id> --bead-id <bead-id>
     ```
8. Implement only within the assigned scope.
9. Run the assigned verification commands and any required repo-local `build-and-test` checks for the touched surface area.
10. Report back to the coordinator with:
   - changed files
   - verification commands run
   - key output or exit status
   - any new risks or follow-up work
   - confirmation that reservations were released
11. Release reservations and post either a `completed` or `blocked` message to `bead/<bead-id>`.
   - release syntax:
     - Windows: `.\scripts\windows\agent-mail.ps1 --repo . release-reservations --owner worker/<bead-id> --bead-id <bead-id>`
     - POSIX: `./scripts/posix/agent-mail.sh --repo . release-reservations --owner worker/<bead-id> --bead-id <bead-id>`
12. If blocked or context-limited:
   - update `HANDOFF.json`
   - release reservations if possible
   - report the blocker clearly to the coordinator

## Hard Rules

- Do not run `bd update`, `bd close`, or any other bead status mutation.
- Do not expand the file scope without coordinator approval.
- Do not silently skip verification.
- Do not keep reservations after you stop working.
- Do not assume another session can see local `.beads/workflow/`; shared coordination only happens through Agent Mail.
