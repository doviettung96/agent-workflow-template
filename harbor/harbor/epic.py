"""Sequential epic runner — Phase 2.1 of harbor.

`run_epic` polls `br ready --parent <epic-id>` and runs each ready descendant
through `run_bead` one at a time. The loop exits when no more ready
descendants exist (and, in this sequential mode, nothing is in flight because
`run_bead` blocks until the bead finishes).

Future Phase 2 work layers on top of this skeleton:
  * P2.2 — parallel pane orchestration (concurrent run_bead workers).
  * P2.3 — Agent Mail epic-lock acquire/release around the loop.
  * P2.4 — reservation-conflict deferral when `mail.reserve` fails.
  * P2.5 — finalize step (build-and-test + review-epic) once the loop drains.

Each bead's lifecycle events are recorded against the epic's run via
`run_bead(..., parent_run=(store, run_id))` so the dashboard sees one epic run
with multiple bead workers, not a series of separate single-bead runs.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .beads import Beads, BeadsError
from .orchestrator import RunBeadOptions, RunBeadResult, run_bead
from .state import StateStore


@dataclass
class RunEpicOptions:
    epic_id: str
    profile: str | None = None
    model: str | None = None
    effort: str | None = None
    repo_root: Path = field(default_factory=Path.cwd)
    # Polling cadence used when `br ready` errors transiently. The happy path
    # is back-to-back blocking `run_bead` calls — sequential mode does not need
    # to sleep between iterations under normal flow.
    interval_s: float = 30.0
    # Bound the loop. None = unbounded (production); tests pass a small int.
    max_iterations: int | None = None
    # Per-bead timeout, propagated into RunBeadOptions.
    bead_timeout_s: float = 60 * 60 * 6
    # Leave panes alive after each bead finishes (matches single-bead default).
    keep_pane_after_finish: bool = True


@dataclass
class RunEpicResult:
    epic_id: str
    run_id: str
    iterations: int
    closed: list[str]
    failed: list[tuple[str, str]]
    exit_reason: str

    def render_summary(self) -> str:
        lines = [
            f"Epic {self.epic_id}",
            f"  run_id     : {self.run_id}",
            f"  iterations : {self.iterations}",
            f"  exit_reason: {self.exit_reason}",
            f"  closed     : {self.closed}",
            f"  failed     : {self.failed}",
        ]
        return "\n".join(lines)


def _ready_under(beads: Beads, epic_id: str) -> list[dict]:
    """`br ready --parent <epic>` filtered down to beads that are not the epic
    itself. The br CLI sometimes echoes the parent in the ready list when the
    epic has no open children left."""
    raw = beads.ready(parent=epic_id)
    return [b for b in raw if b.get("id") != epic_id]


def run_epic(opts: RunEpicOptions, *, log: Callable[..., None] = print) -> RunEpicResult:
    repo_root = Path(opts.repo_root).resolve()
    beads = Beads()

    store = StateStore(repo_root)
    run_id = store.start_run(mode="epic", epic_id=opts.epic_id)
    log(f"[harbor.epic] run {run_id} started for epic {opts.epic_id}")

    attempted: set[str] = set()
    closed: list[str] = []
    failed: list[tuple[str, str]] = []
    iterations = 0
    exit_reason = "drained"

    try:
        while True:
            iterations += 1

            try:
                ready = _ready_under(beads, opts.epic_id)
            except BeadsError as e:
                log(
                    f"[harbor.epic] tick #{iterations}: br ready failed ({e}); "
                    f"sleeping {opts.interval_s}s"
                )
                if opts.max_iterations is not None and iterations >= opts.max_iterations:
                    exit_reason = "max_iterations"
                    break
                time.sleep(opts.interval_s)
                continue

            ready_ids = [b.get("id") for b in ready]
            running_ids: list[str] = []  # sequential mode never has concurrent in-flight beads
            log(
                f"[harbor.epic] tick #{iterations}: ready={ready_ids} "
                f"running={running_ids} attempted={sorted(attempted)}"
            )

            runnable = [b for b in ready if b.get("id") not in attempted]
            if not runnable:
                exit_reason = "drained" if not ready else "all_attempted"
                break

            bead = runnable[0]
            bead_id = bead["id"]
            attempted.add(bead_id)
            log(f"[harbor.epic] running {bead_id}")

            bead_opts = RunBeadOptions(
                bead_id=bead_id,
                profile=opts.profile,
                model=opts.model,
                effort=opts.effort,
                repo_root=repo_root,
                timeout_s=opts.bead_timeout_s,
                keep_pane_after_finish=opts.keep_pane_after_finish,
            )

            try:
                result: RunBeadResult = run_bead(bead_opts, log=log, parent_run=(store, run_id))
            except Exception as e:  # noqa: BLE001
                log(f"[harbor.epic] {bead_id} crashed: {e!r}")
                failed.append((bead_id, "crash"))
            else:
                if result.closed:
                    closed.append(bead_id)
                    log(f"[harbor.epic] {bead_id} closed")
                else:
                    reason = result.sentinel_status or "timeout"
                    failed.append((bead_id, reason))
                    log(f"[harbor.epic] {bead_id} ended without close (reason={reason})")

            if opts.max_iterations is not None and iterations >= opts.max_iterations:
                exit_reason = "max_iterations"
                break
    finally:
        store.end_run(run_id, status="finished")
        store.close()

    log(
        f"[harbor.epic] run {run_id} ended: reason={exit_reason} "
        f"closed={closed} failed={failed}"
    )
    return RunEpicResult(
        epic_id=opts.epic_id,
        run_id=run_id,
        iterations=iterations,
        closed=closed,
        failed=failed,
        exit_reason=exit_reason,
    )
