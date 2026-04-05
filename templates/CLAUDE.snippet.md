<!-- BEGIN TEMPLATE BR WORKFLOW -->
## Issue Tracking

This repo uses `br` (`beads_rust`) for issue tracking. Use `br`, not markdown TODO files or alternate trackers.

The repo standard is `.beads/config.yaml` with `no-db: false`, so normal `br` mutations use the shared live Beads store for this clone. Run `br sync --flush-only` before commit or handoff so the shared live JSONL stays current. Use `shared-beads export-snapshot` from the main checkout when you want the tracked `.beads/issues.jsonl` snapshot updated for Git sharing. Perform one-bead status mutations only, and if a `br update` or `br close` command errors, verify the bead with `br show <id> --json` plus the live shared `issues.jsonl` path reported by `shared-beads status` before retrying.

See `AGENTS.md` for repo rules and `BEADS_WORKFLOW.md` for planner, executor, worktree, and swarm flow.
<!-- END TEMPLATE BR WORKFLOW -->
