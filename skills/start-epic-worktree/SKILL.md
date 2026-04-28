---
name: start-epic-worktree
description: "Create a parallel git worktree for one epic and hydrate the local-only workflow files into it. Use before swarm-epic when the user wants checkout isolation for a truly parallel epic."
---

# Start Epic Worktree

Prepare a new git worktree that can run the normal local-only workflow.

## Goal

Create a sibling checkout for one epic, copy the ignored workflow surface into it, and leave it ready for normal `swarm-epic` or manual execution.

## When To Use

- the user wants one epic isolated in its own checkout
- the current checkout already has the repo-local workflow files and live `.beads` state you want to clone
- you want the new worktree to inherit local skills, helper scripts, AGENTS/CLAUDE workflow snippets, and the current `.beads` snapshot

Do not use this skill for normal single-checkout work. `swarm-epic` can run directly in the current checkout.

## Steps

1. Confirm the source checkout is already workflow-ready:
   ```bash
   br where --no-db
   ```
2. Determine:
   - epic id
   - optional destination path
   - optional branch name, default `epic/<epic-id>`
   - optional base ref, default `HEAD`
3. Run the helper script from the current checkout:

Windows:

```powershell
.\scripts\windows\start-epic-worktree.ps1 -EpicId <epic-id>
```

POSIX:

```bash
./scripts/posix/start-epic-worktree.sh <epic-id>
```

4. After the helper completes, switch your session into the new worktree and continue there.
5. Run the normal executor flow in that worktree, usually:
   ```bash
   swarm-epic <epic-id>
   ```

## Notes

- this helper clones the current checkout's local-only workflow surface into the new worktree; it does not make that state shared or merge-safe
- code still merges back through normal Git branches and PRs
- when the epic finishes, close beads in the planner checkout as usual and delete the execution worktree when no longer needed
