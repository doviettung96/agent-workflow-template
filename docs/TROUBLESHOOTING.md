# Troubleshooting

## Worktree cannot find the Beads database

Symptoms:

- `bd where` fails inside a worktree
- `bd ready` or `bd show` says the database is missing
- the worktree was created with raw `git worktree add`

Fix:

1. Check the Beads context from the worktree:

   ```bash
   bd where
   bd context
   ```

2. If the worktree was not created through Beads, stop using it for Beads operations.
3. Recreate the worktree with:

   ```bash
   bd worktree create <name> --branch epic/<epic-id>
   ```

   or use `start-epic-worktree`.
4. If the main checkout itself cannot open the database, run:

   ```bash
   bd bootstrap --yes
   ```

## Local Dolt server endpoint changed

Symptoms:

- `bd where` or `bd ready` warns that the Dolt server port changed
- an old worktree is pointing at stale local server info

Fix:

1. Check server state:

   ```bash
   bd dolt status
   bd context
   ```

2. If the main checkout is healthy but a worktree is stale, recreate the worktree through Beads.
3. If the main checkout is unhealthy, run:

   ```bash
   bd bootstrap --yes
   bd doctor
   ```

## Old `br` artifacts remain after rollback

Symptoms:

- `.beads/redirect` points to an old `*.shared/_beads` path
- `scripts/windows/shared-beads.ps1` or `scripts/posix/shared-beads.sh` still exist
- `br`-era files like `.br_history/` remain under `.beads`

Fix:

1. Re-run the rollback scaffold or migration script for the repo.
2. Confirm the repo now uses `bd`:

   ```bash
   bd where
   bd ready --json
   ```

3. Ignore or remove archived `br` backups under `.beads/backup/` if they are no longer needed.
