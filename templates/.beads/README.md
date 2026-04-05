# `.beads/` Layout

This template standardizes `br` with `.beads/config.yaml` set to `no-db: false`.

- `issues.jsonl` is the repo-tracked snapshot used for Git sharing across machines
- `config.yaml` stores the issue prefix and DB-backed mode
- `redirect` points plain `br` at the shared live Beads workspace for this clone
- `workflow/` is local worktree runtime for swarm coordination and handoff

Normal `br` mutations update the shared live Beads store for the whole clone. Export the tracked snapshot explicitly from the main checkout when you want `.beads/issues.jsonl` updated for Git.

`workflow/` is local runtime state and is ignored by Git. Shared live Beads lives in the clone-local path reported by `shared-beads status`, while Agent Mail, epic locks, and reservations live under `git rev-parse --git-common-dir`, not under repo-local `.beads/`.
