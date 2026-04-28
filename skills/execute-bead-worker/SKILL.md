---
name: execute-bead-worker
description: "Execute one assigned bead for a coordinator. Use only when swarm-epic, executor-once, or executor-loop-epic has assigned a fresh-session-safe bead contract, file scope, and verification contract; the worker implements, verifies, and reports without mutating bead state."
---

# Execute Bead Worker

Implement one assigned bead for a coordinator.

## Goal

Deliver one bead safely inside the boundaries set by `swarm-epic`, `executor-once`, or `executor-loop-epic`.

## Steps

1. Confirm the assignment from the coordinator:
   - coordination scope: either a real epic id or `manual/<bead-id>` for single-bead `executor-once`
   - bead id
   - `Read:` targets
   - `Inputs:` persisted prerequisites
   - `Files:` scope
   - `Verify:` commands or checks
   - reservation or conflict instructions
2. Read the bead details and inspect the required `Read:` targets plus the relevant code.
3. If the bead is underspecified or missing `Read:`, `Inputs:`, `Files:`, or `Verify:`, stop and return it to the coordinator instead of guessing.
4. Treat this worker as a fresh context. Do not assume access to prior epic or executor discussion beyond the persisted bead contract, local repo state, and Agent Mail messages.
5. Register the worker and inspect its inbox:
   - Windows:
     ```powershell
     .\scripts\windows\agent-mail.ps1 --repo . register --name worker/<bead-id> --role worker --epic-id <coordination-scope> --bead-id <bead-id>
     .\scripts\windows\agent-mail.ps1 --repo . inbox --recipient worker/<bead-id>
     ```
   - POSIX:
     ```bash
     ./scripts/posix/agent-mail.sh --repo . register --name worker/<bead-id> --role worker --epic-id <coordination-scope> --bead-id <bead-id>
     ./scripts/posix/agent-mail.sh --repo . inbox --recipient worker/<bead-id>
     ```
6. Reserve the declared file scope before editing through the shared control plane:
   - Windows:
     ```powershell
     .\scripts\windows\agent-mail.ps1 --repo . reserve --owner worker/<bead-id> --epic-id <coordination-scope> --bead-id <bead-id> --path <path1> --path <path2>
     ```
   - POSIX:
     ```bash
     ./scripts/posix/agent-mail.sh --repo . reserve --owner worker/<bead-id> --epic-id <coordination-scope> --bead-id <bead-id> --path <path1> --path <path2>
     ```
   If reservation fails, stop and report the conflict to the coordinator.
7. Update `.beads/workflow/HANDOFF.json` for this worker context:
   - `role`
   - `coordination_scope`
   - `bead_id`
   - `summary`
   - `next_action`
8. Post a `started` message to `bead/<bead-id>` so the coordinator and other sessions can see who owns the bead.
   - Windows:
     ```powershell
     .\scripts\windows\agent-mail.ps1 --repo . post --thread bead/<bead-id> --sender worker/<bead-id> --type started --body '{"status":"started"}' --epic-id <coordination-scope> --bead-id <bead-id>
     ```
   - POSIX:
     ```bash
     ./scripts/posix/agent-mail.sh --repo . post --thread bead/<bead-id> --sender worker/<bead-id> --type started --body '{"status":"started"}' --epic-id <coordination-scope> --bead-id <bead-id>
     ```
9. Implement only within the assigned scope and only after confirming the required `Inputs:` are present in persisted form.
10. Run the assigned verification commands and any required repo-local `build-and-test` checks for the touched surface area.
11. Report back to the coordinator with:
   - changed files
   - `Inputs:` consumed
   - verification commands run
   - key output or exit status
   - any new risks or follow-up work
   - suggested closeout note covering what changed, where it was persisted, and what downstream beads can now rely on
   - confirmation that reservations were released
12. Release reservations and post either a `completed` or `blocked` message to `bead/<bead-id>`.
   - release syntax:
     - Windows: `.\scripts\windows\agent-mail.ps1 --repo . release-reservations --owner worker/<bead-id> --bead-id <bead-id>`
     - POSIX: `./scripts/posix/agent-mail.sh --repo . release-reservations --owner worker/<bead-id> --bead-id <bead-id>`
13. If blocked or context-limited:
   - update `HANDOFF.json`
   - release reservations if possible
   - report the blocker clearly to the coordinator
   - classify the blocker as exactly one of:
     - `clarify` - small missing fact or instruction; the current worker context is still useful
     - `env` - environment, runtime, credential, or reservation problem; the current worker context is still useful once the environment is fixed
     - `contract` - the bead contract is incomplete, wrong, or missing required persisted inputs; the coordinator should tighten the bead before retry
     - `scope` - the bead needs splitting, replanning, or a changed file boundary; the coordinator should not keep this worker running as-is
   - include `Context reusable: yes` for `clarify` or `env`, and `Context reusable: no` for `contract` or `scope`

## Hard Rules

- Do not run `br update --no-db`, `br close --no-db`, or any other bead status mutation.
- Do not expand the file scope without coordinator approval.
- Do not silently skip verification.
- Do not keep reservations after you stop working.
- Do not assume another session can see local `.beads/workflow/`; shared coordination only happens through Agent Mail or the final worker report returned to the parent coordinator.
- Do not continue if the bead still depends on prior chat memory instead of persisted inputs.
- If blocked, prefer a crisp blocker report over speculative fixes. The coordinator decides whether this worker should continue or be replaced.
