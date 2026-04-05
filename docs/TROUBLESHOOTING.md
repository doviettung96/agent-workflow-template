# Troubleshooting

## Current checkout cannot find the Beads database

Symptoms:

- `bd where` fails in the current checkout
- `bd ready` or `bd show` says the database is missing
- `bd context` shows stale server details

Fix:

1. Check the Beads context from the current checkout:

   ```bash
   bd where
   bd context
   ```

2. Repair the repo-local Beads state:

   ```bash
   bd bootstrap --yes
   ```

## Local Dolt server endpoint changed

Symptoms:

- `bd where` or `bd ready` warns that the Dolt server port changed
- the current checkout is pointing at stale local server info

Fix:

1. Check server state:

   ```bash
   bd dolt status
   bd context
   ```

2. If the checkout is unhealthy, run:

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
