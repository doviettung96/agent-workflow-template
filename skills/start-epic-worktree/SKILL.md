---
name: start-epic-worktree
description: "Create or reuse the dedicated worktree for one epic branch before swarm execution. This is the worktree helper that `swarm-epic` should call automatically when it is not already running inside the correct epic worktree."
---

# Start Epic Worktree

Prepare a dedicated worktree for one epic branch.

## Goal

Give each epic its own Git checkout so multiple coordinators can run in parallel without sharing `HEAD`, index, or working tree state.

## Steps

1. Confirm the target epic id.
2. Ensure the epic has passed `validate-beads` before preparing swarm execution.
3. Run the helper script from the repo root or current worktree:
   - Windows:
     ```powershell
     .\scripts\windows\start-epic-worktree.ps1 --repo . --epic-id <epic-id>
     ```
   - POSIX:
     ```bash
     ./scripts/posix/start-epic-worktree.sh --repo . --epic-id <epic-id>
     ```
4. Read the returned JSON and capture:
   - `worktree_path`
   - `branch`
   - whether the worktree was created or reused
   - the suggested next command
5. Switch into that worktree.
6. Run `swarm-epic` from inside the dedicated worktree, not from the main checkout.

In the normal operator flow, this helper is usually invoked by `swarm-epic` rather than called manually.

## Hard Rules

- Do not run `swarm-epic` for concurrent epic work from a shared checkout.
- Do not create a second worktree for the same epic if one already exists.
- Treat the worktree helper as the only supported entrypoint for epic swarm branches.
