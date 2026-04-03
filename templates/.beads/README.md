# `.beads/` Layout

This template standardizes `br` with `.beads/config.yaml` set to `no-db: true`.

- `issues.jsonl` is the repo-shared Beads state
- `config.yaml` stores the issue prefix and no-db mode
- `workflow/` is local worktree runtime for swarm coordination and handoff

Normal `br` mutations update the repo-shared JSONL directly. Commit `.beads/` issue state with code changes.

`workflow/` is local runtime state and is ignored by Git. Shared Agent Mail, epic locks, and reservations live under `git rev-parse --git-common-dir`, not under repo-local `.beads/`.
