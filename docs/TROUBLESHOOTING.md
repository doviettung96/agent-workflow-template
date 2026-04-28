# Troubleshooting

## Current checkout cannot find the Beads workspace

Symptoms:

- `br where --no-db` fails in the current checkout
- `br ready --no-db` or `br show --no-db` says the workspace is missing
- `br info --json --no-db` cannot resolve `.beads`

Fix:

1. Check the Beads context from the current checkout:

   ```bash
   br where --no-db
   br info --json --no-db
   ```

2. Repair the repo-local Beads state:

   ```bash
   br init --prefix <prefix> --no-db
   ```

## Local Beads state looks stale

Symptoms:

- `br where --no-db` resolves the wrong checkout
- `br ready --no-db` does not match the current `issues.jsonl`
- `.beads/` contains leftover files from an older tracker layout

Fix:

1. Inspect current state:

   ```bash
   br where --no-db
   br info --json --no-db
   ```

2. If the checkout is unhealthy, run:

   ```bash
   br init --prefix <prefix> --no-db
   br doctor --no-db
   ```

## Old `br` artifacts remain after rollback

Symptoms:

- `.beads/redirect` points to an old `*.shared/_beads` path
- `scripts/windows/shared-beads.ps1` or `scripts/posix/shared-beads.sh` still exist
- `br`-era files like `.br_history/` remain under `.beads`

Fix:

1. Re-run the rollback scaffold or migration script for the repo.
2. Confirm the repo now uses `br --no-db`:

   ```bash
   br where --no-db
   br ready --json --no-db
   ```

3. Ignore or remove archived `br` backups under `.beads/backup/` if they are no longer needed.

## Target runtime config is invalid

Symptoms:

- `python scripts/shared/target_runtime.py status` fails
- `build-and-test` reports a runtime-target config error before running verification
- `workflow-status` shows stale or incomplete target-runtime details

Fix:

1. Inspect the current runtime target:

   ```bash
   python scripts/shared/target_runtime.py status
   ```

2. Reconfigure the checkout-local target:

   ```bash
   python scripts/shared/target_runtime.py configure --mode local
   ```

   Or, for SSH:

   ```bash
   python scripts/shared/target_runtime.py configure --mode ssh --ssh-host <alias> --remote-platform posix|windows --remote-workdir <path> [--remote-python /path/to/python]
   ```

## SSH target cannot sync or execute

Symptoms:

- `target_runtime.py run -- ...` fails before the command starts
- `rsync`, `scp`, or `ssh` errors appear during build or test execution
- the remote workdir exists but the repo contents are stale or incomplete

Fix:

1. Confirm the checkout-local target runtime config:

   ```bash
   python scripts/shared/target_runtime.py status
   ```

2. Confirm the local machine has the required transport tools:

   ```bash
   ssh -V
   rsync --version
   ```

   The default SSH `rsync` flow is additive and keeps remote-only files. If the remote workdir also stores large artifacts or model weights, prefer `sync_strategy=rsync` over `archive` and keep those artifacts outside paths the repo itself writes to.

3. Confirm the named SSH host works outside the workflow first:

   ```bash
   ssh <alias>
   ```

4. If the repo depends on Docker, Conda, or platform-specific wrapper scripts, finish the `Configure target runtime for this repo` bead before retrying feature execution.
