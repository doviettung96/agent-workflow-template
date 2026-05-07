"""Epic runner — Phase 2 of harbor.

`run_epic` polls `br ready --parent <epic-id>` and runs each ready descendant
through `run_bead`. With `max_concurrency=1` the loop is sequential (P2.1
behavior). With `max_concurrency>1` the loop submits up to N concurrent
`run_bead` calls into a `ThreadPoolExecutor`, waits for any to complete, reaps
results, and re-polls.

The loop terminates when nothing is in flight AND no runnable ready descendants
remain. Beads that returned `closed=False` (timed out, hit a blocker, crashed)
are tracked in `attempted` so the same run won't re-spawn them — the user will
typically attach to the live pane and recover manually.

Future Phase 2 work layered on top of this skeleton:
  * P2.3 — Agent Mail epic-lock acquire/release around the loop.
  * P2.4 — reservation-conflict deferral when `mail.reserve` fails.
  * P2.5 — finalize step (build-and-test + review-epic) once the loop drains.

Each bead's lifecycle events are recorded against the epic's run via
`run_bead(..., parent_run=(store, run_id))` so the dashboard sees one epic run
with multiple bead workers, not a series of separate single-bead runs. The
shared `StateStore` is thread-safe — see its module docstring.
"""
from __future__ import annotations

import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
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
    # Maximum concurrent run_bead workers. 1 = sequential (P2.1 behavior).
    max_concurrency: int = 3
    # Wait at most this long inside one outer iteration for any pending future
    # to complete. Picked smaller than the typical bead duration so the loop
    # stays responsive to new ready beads appearing while others are running.
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


def _make_bead_opts(opts: RunEpicOptions, bead_id: str, repo_root: Path) -> RunBeadOptions:
    return RunBeadOptions(
        bead_id=bead_id,
        profile=opts.profile,
        model=opts.model,
        effort=opts.effort,
        repo_root=repo_root,
        timeout_s=opts.bead_timeout_s,
        keep_pane_after_finish=opts.keep_pane_after_finish,
    )


def run_epic(opts: RunEpicOptions, *, log: Callable[..., None] = print) -> RunEpicResult:
    if opts.max_concurrency < 1:
        raise ValueError(f"max_concurrency must be >= 1, got {opts.max_concurrency}")

    repo_root = Path(opts.repo_root).resolve()
    beads = Beads()

    store = StateStore(repo_root)
    run_id = store.start_run(mode="epic", epic_id=opts.epic_id)
    log(
        f"[harbor.epic] run {run_id} started for epic {opts.epic_id} "
        f"(max_concurrency={opts.max_concurrency})"
    )

    attempted: set[str] = set()
    closed: list[str] = []
    failed: list[tuple[str, str]] = []
    iterations = 0
    exit_reason = "drained"
    in_flight: dict[str, Future] = {}

    pool = ThreadPoolExecutor(max_workers=opts.max_concurrency, thread_name_prefix="harbor-bead")
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
            spawned_this_tick: list[str] = []

            # Spawn fresh beads up to the concurrency cap.
            for bead in ready:
                bid = bead.get("id")
                if not bid or bid in in_flight or bid in attempted:
                    continue
                if len(in_flight) >= opts.max_concurrency:
                    break
                attempted.add(bid)
                bead_opts = _make_bead_opts(opts, bid, repo_root)
                in_flight[bid] = pool.submit(
                    run_bead, bead_opts, log=log, parent_run=(store, run_id)
                )
                spawned_this_tick.append(bid)

            log(
                f"[harbor.epic] tick #{iterations}: ready={ready_ids} "
                f"running={list(in_flight)} attempted={sorted(attempted)} "
                f"spawned={spawned_this_tick}"
            )

            if not in_flight:
                # Nothing running — decide why and stop. Either ready is empty
                # (drained) or every ready bead has been attempted in this run.
                non_attempted = [b for b in ready_ids if b and b not in attempted]
                if non_attempted:
                    # Defensive: max_concurrency=0 would land here, but the
                    # constructor already rejects that. Treat as drained.
                    exit_reason = "drained"
                else:
                    exit_reason = "drained" if not ready else "all_attempted"
                break

            if opts.max_iterations is not None and iterations >= opts.max_iterations:
                exit_reason = "max_iterations"
                break

            # Wait for at least one in-flight bead to finish, or for the
            # poll interval to elapse — whichever comes first.
            done, _pending = wait(
                list(in_flight.values()),
                timeout=opts.interval_s,
                return_when=FIRST_COMPLETED,
            )

            for fut in done:
                bid = next((b for b, f in in_flight.items() if f is fut), None)
                if bid is None:
                    continue
                try:
                    result: RunBeadResult = fut.result()
                except Exception as e:  # noqa: BLE001
                    log(f"[harbor.epic] {bid} crashed: {e!r}")
                    failed.append((bid, "crash"))
                else:
                    if result.closed:
                        closed.append(bid)
                        log(f"[harbor.epic] {bid} closed")
                    else:
                        reason = result.sentinel_status or "timeout"
                        failed.append((bid, reason))
                        log(f"[harbor.epic] {bid} ended without close (reason={reason})")
                in_flight.pop(bid, None)
    finally:
        # Best-effort: wait for any still-in-flight workers so we don't leave
        # half-finished bead state behind. They should be a small set.
        if in_flight:
            log(f"[harbor.epic] draining {len(in_flight)} in-flight bead(s) before exit")
            for bid, fut in list(in_flight.items()):
                try:
                    fut.result(timeout=opts.interval_s)
                except Exception as e:  # noqa: BLE001
                    log(f"[harbor.epic] drain {bid}: {e!r}")
        pool.shutdown(wait=True, cancel_futures=False)
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
