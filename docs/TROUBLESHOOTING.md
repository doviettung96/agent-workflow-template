# Troubleshooting

## `br` mutation errors in one worktree

Use this only as a fallback. It is not part of the normal skill flow.

Typical symptoms:

- `br update <id> --status=...` errors with a database or foreign-key failure
- `br close <id>` errors even though the bead graph looks valid
- `br show <id>` and the live shared `issues.jsonl` appear to disagree

Normal recovery order:

1. Stop issuing further bead mutations.
2. Inspect the bead with:
   ```bash
   br show <id> --json
   ```
3. Run `shared-beads status` and inspect the same id in the live shared `issues.jsonl` path it reports.
4. If DB and JSONL already agree on the intended state, continue from that state without replaying the mutation.
5. If DB and JSONL disagree, reconcile JSONL before more status changes or handoff.

## Rebuild the local DB cache

If single-bead mutations keep failing in the same worktree and the live shared `issues.jsonl` looks sane, rebuild the shared DB cache from that JSONL.

This is safe because:

- the live shared `issues.jsonl` in the clone-local shared Beads root is the intra-clone source of truth
- `_beads/beads.db*` is the shared clone-local cache

Windows PowerShell:

```powershell
Remove-Item (Join-Path ((.\scripts\windows\shared-beads.ps1 status | ConvertFrom-Json).shared_root) "beads.db"), (Join-Path ((.\scripts\windows\shared-beads.ps1 status | ConvertFrom-Json).shared_root) "beads.db-wal"), (Join-Path ((.\scripts\windows\shared-beads.ps1 status | ConvertFrom-Json).shared_root) "beads.db-shm") -ErrorAction SilentlyContinue
br doctor --repair
.\scripts\windows\shared-beads.ps1 --repo . attach
```

POSIX shell:

```bash
root="$(./scripts/posix/shared-beads.sh --repo . status | python3 -c 'import json,sys; print(json.load(sys.stdin)["shared_root"])')"
rm -f "${root}/beads.db" "${root}/beads.db-wal" "${root}/beads.db-shm"
br doctor --repair
./scripts/posix/shared-beads.sh --repo . attach
```

After rebuild:

1. Smoke-test one single-bead mutation.
2. Verify with `br show <id> --json`.
3. Confirm the live shared `issues.jsonl` matches before continuing.

## Notes

- This is a clone-local recovery step, not a repo-wide migration step.
- It became especially relevant after migrating old worktrees from the earlier `bd` / `no-db` setup, but it is not limited to migration scenarios.
- Do not rebuild the DB as a first response. Verify DB vs JSONL first.
