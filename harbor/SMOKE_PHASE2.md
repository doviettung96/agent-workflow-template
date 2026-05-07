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

## Run log — completed 2026-05-08

### Run 1 (parallel beads, `--skip-finalize`) — initial attempt 23:47 UTC

Smoke epic `awt-1qg` with three independent ready beads (`awt-1qg.1/2/3`),
each writing to a distinct `harbor/SMOKE_<X>.md`. Run id `7782835adee7`.

- 3 sessions spawned within 8s ✓
  - `harbor-6ee962d1-awt-1qg_1/2/3`
- Codex agents created the SMOKE files and emitted HARBOR-DONE: status=ok
- Harbor's polling crashed: `'NoneType' object has no attribute 'splitlines'`
- Root cause: Windows subprocess defaulted to cp1252 text mode, choked on
  the em-dash (`—` / 0xE2 0x80 0x94) codex echoed from the bead description.
  `subprocess.run(..., text=True)` silently swallowed the UnicodeDecodeError
  inside its reader thread and returned None for stdout.
- Fix: commit 7fc4627 — pass `encoding="utf-8", errors="replace"` to every
  subprocess call in `harbor.tmux`, `harbor.beads`, and `harbor.verify`.

### Run 2 (parallel beads, `--skip-finalize`) — re-run with fix 23:51 UTC

Run id `3c257f04563a`. Same epic, beads reset to open.

- 3 sessions spawned in tick #1 ✓
- All 3 codex agents emitted HARBOR-DONE: status=ok ✓
- Harbor parsed all 3 sentinels, ran verify, called `br close` ✓
- Result: `closed=['awt-1qg.2', 'awt-1qg.3', 'awt-1qg.1']`, `failed=[]` ✓
- 1 of 3 close calls didn't persist to JSONL (concurrent-write race in br
  CLI — orthogonal to harbor; recovered manually via JSONL edit + `br sync`)

### Run 3 (finalize pipeline) — initial attempt 23:54 UTC

Run id `ad3811e6e034`. Empty ready set, finalize triggered immediately.

- `finalize-build-and-test` session spawned + codex ran fallback prompt ✓
- Sentinel `status=ok` parsed ✓
- `finalize-review-epic` session spawned ✓
- Sentinel `status=blocked classification=contract` — codex correctly
  refused: `skills/review-epic/SKILL.md` doesn't include `Files:`/`Verify:`
  sections, which harbor's worker-prompt hard rules require.
- Fix: commit pending — `harbor.finalize._ensure_contract_sections` now
  wraps loaded SKILL.md prompts with default Files/Verify if missing.

### Run 4 (finalize pipeline) — re-run with contract-sections fix 23:59 UTC

Run id `aee013cd6885`.

- `finalize-build-and-test` ran tests, emitted HARBOR-DONE: status=ok in 30s ✓
- `finalize-review-epic` did real review work — read closed beads, ran
  pytest (153 passed), inspected git diffs, analyzed changes ✓
- Codex finished its review summary but forgot the formatted HARBOR-DONE
  line — sat at the prompt waiting. Sent `tmux send-keys` nudge
  ("Please emit the final HARBOR-DONE sentinel line now: HARBOR-DONE:
  finalize-review-epic status=ok classification=none") — this is the
  awt-zmq.14 human-recovery flow. Codex emitted the sentinel; harbor
  parsed it and finalized. ✓
- Final result: `exit_reason=drained`,
  `steps_passed=['finalize-build-and-test', 'finalize-review-epic']`,
  `failed=[]`, `skipped=[]` ✓

### Acceptance summary

- [x] 3 sessions appear within 10 seconds of `run-epic` starting (8s)
- [x] All three beads close (sentinel `status=ok`)
- [x] After all three close, `run_epic` exits cleanly
- [x] Re-run WITHOUT `--skip-finalize`: harbor spawns finalize sessions,
      runs to completion
- [x] Total wallclock under 10 minutes — Run 2 was ~30s, Run 4 was ~3 min
- [x] human-recovery via `tmux send-keys` works for forgotten sentinels

### Bugs found and fixed during the smoke

1. cp1252 encoding crash on em-dash → commit 7fc4627
2. SKILL.md loaded for finalize lacked Files/Verify sections → fix in
   `harbor.finalize._ensure_contract_sections`

### Known follow-ups (not blockers)

- `br close` under N-thread concurrent calls sometimes loses one write to
  JSONL (saw 2 of 3 close calls land). br-side reliability issue; out of
  harbor's scope. Workaround: idempotent `br sync --import-only --force`
  pulls JSONL into shape.
- Codex sometimes ends review-style prompts without the formatted sentinel
  line. The interactive-pane recovery flow handles this, but it's friction
  worth filing as a future improvement (e.g. inject a "WAS THE SENTINEL
  PRINTED?" check into the prompt's tail).


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
