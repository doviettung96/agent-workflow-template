# Phase 2 Live Smoke — `harbor run-epic` end-to-end

This is the runbook for the Phase 2 verification (awt-zmq.104). It exercises
the parallel runner, epic-lock, reservation deferral, and finalize pipeline
together against real `codex` on Windows + Git Bash + psmux.

Phase 1 had its parallel of this run (awt-zmq.99 / SMOKE.md). This file is
the same idea for Phase 2 — drive a real epic with three independent ready
beads through harbor, observe the panes, and verify the finalize step runs.

## Prerequisites

- [ ] `codex` 0.128 (or compatible) on PATH
- [ ] OpenAI API credits available
- [ ] `psmux` (or tmux) on PATH — Git Bash `tmux` works
- [ ] Repo on `main`, working tree clean
- [ ] `harbor.yml` at repo root has the codex profile (already committed)
- [ ] `cd harbor && python -m pytest -q` shows 149 passed before starting

## Setup — three independent scratch beads under a smoke epic

The beads must claim DISJOINT files so the parallel runner actually spawns
three concurrent panes (overlapping files would force the reservation
deferral path, which is the wrong code path for this smoke).

```bash
# Create the smoke epic
br create --type=epic --priority=2 --title="Harbor Phase 2 smoke epic" \
  --description="Throwaway epic for awt-zmq.104 verification. Three independent ready beads writing to distinct SMOKE_X.md files." \
  --silent
# Capture the new epic id, e.g. awt-XXX

# Three independent scratch beads. Each writes to its own SMOKE file.
SMOKE_EPIC=<paste-id-from-above>

br create --type=task --priority=2 --parent=$SMOKE_EPIC \
  --title="Smoke A: write SMOKE_A.md" \
  --description="Read:
- harbor/SMOKE_PHASE2.md (this file — context)

Files:
- harbor/SMOKE_A.md (this bead's output)

Verify:
- python -c \"import os,sys; sys.exit(0 if os.path.exists('harbor/SMOKE_A.md') else 1)\"

Body:
Create harbor/SMOKE_A.md with the line: 'Phase 2 smoke A — bead-A signed off at <timestamp>'. Then emit:
  HARBOR-DONE: BEAD-ID status=ok classification=none"

br create --type=task --priority=2 --parent=$SMOKE_EPIC \
  --title="Smoke B: write SMOKE_B.md" \
  --description="<same shape as A but harbor/SMOKE_B.md>"

br create --type=task --priority=2 --parent=$SMOKE_EPIC \
  --title="Smoke C: write SMOKE_C.md" \
  --description="<same shape as A but harbor/SMOKE_C.md>"
```

## Run

```bash
cd /d/Projects/game-reverse/agent-workflow-template
python -m harbor run-epic $SMOKE_EPIC --profile fast --interval 5 --max-concurrency 3 --skip-finalize
```

Why `--skip-finalize` for the first pass: the finalize step calls a synthetic
`build-and-test` skill which doesn't exist in this template, so it'd just hit
the fallback prompt and (likely) emit `blocked`. To verify the parallel-loop
half of Phase 2 cleanly, skip it. Run a SECOND time without `--skip-finalize`
to verify finalize wires up.

In a second terminal, watch what harbor sees:

```bash
tmux -L harbor list-sessions
# expected within ~10s of starting:
#   harbor-<digest>-<smoke-epic>_<bead-id-A>: ...
#   harbor-<digest>-<smoke-epic>_<bead-id-B>: ...
#   harbor-<digest>-<smoke-epic>_<bead-id-C>: ...
```

To peek inside one of the panes:

```bash
tmux -L harbor attach -t harbor-<digest>-<bead-id>
# (Ctrl-b d to detach without killing)
```

## Acceptance — fill in observations during the run

- [ ] 3 sessions appear within 10 seconds of `run-epic` starting
- [ ] All three beads close (sentinel `status=ok`)
- [ ] `state.json` shows `mode=swarm`, `workers=[A,B,C]` while running
- [ ] After all three close, `run_epic` exits with `exit_reason=drained`
- [ ] Re-run WITHOUT `--skip-finalize`: harbor spawns one more session named
      `harbor-<digest>-finalize-build-and-test`, runs to completion
- [ ] Total wallclock under 10 minutes for trivial beads (codex `fast` profile)

## Run log — fill these in

```
Run 1 (parallel beads, --skip-finalize):
  Started:  YYYY-MM-DDThh:mm:ssZ
  Sessions observed:
    -
    -
    -
  Sentinels detected (timestamp + status):
    -
  Exit reason / total wallclock:
  Notes:

Run 2 (with finalize):
  Started:  YYYY-MM-DDThh:mm:ssZ
  Build-and-test session:
  Build-and-test sentinel:
  Review-epic session (if reached):
  Review-epic sentinel:
  Notes:
```

## If something goes wrong

- Reservation conflicts when beads should be independent → the bead descriptions
  are claiming overlapping files. Re-check `Files:` blocks.
- Sessions don't appear → `python -m harbor run-epic --help` shows no errors;
  check `tmux -L harbor` works on this machine (Phase 1 SMOKE.md has the
  baseline test).
- `br ready --parent <smoke-epic>` returns the epic itself only → children
  aren't tagged with `--parent` correctly. Verify with `br show <bead>`.
- Codex 0.128 quirks (no `--reasoning-effort` flag, requires
  `--no-alt-screen`) are handled by `harbor.yml`'s codex profile — leave
  that file alone.

## After a successful run

```bash
# Tear down the smoke epic and its children
br close $SMOKE_BEAD_A $SMOKE_BEAD_B $SMOKE_BEAD_C $SMOKE_EPIC --reason="Phase 2 smoke complete"

# Clean up the SMOKE files (optional)
rm -f harbor/SMOKE_A.md harbor/SMOKE_B.md harbor/SMOKE_C.md

# Close awt-zmq.104 with the run log filled in above
br close awt-zmq.104 --reason="Phase 2 smoke run logged in harbor/SMOKE_PHASE2.md"
```
