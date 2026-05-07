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
from .mail import Mail
from .orchestrator import (
    ReservationOutcome,
    RunBeadOptions,
    RunBeadResult,
    parse_files_section,
    run_bead,
    try_reserve_for_bead,
)
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
    # When True, skip the build-and-test + review-epic finalize pipeline that
    # normally runs after a successful drain. Tests use this to keep the run
    # focused on the loop's behavior; the CLI defaults to running finalize.
    skip_finalize: bool = False


@dataclass
class RunEpicResult:
    epic_id: str
    run_id: str
    iterations: int
    closed: list[str]
    failed: list[tuple[str, str]]
    exit_reason: str
    finalize: "object | None" = None  # FinalizeResult — typed loosely to avoid circular imports

    def render_summary(self) -> str:
        lines = [
            f"Epic {self.epic_id}",
            f"  run_id     : {self.run_id}",
            f"  iterations : {self.iterations}",
            f"  exit_reason: {self.exit_reason}",
            f"  closed     : {self.closed}",
            f"  failed     : {self.failed}",
        ]
        if self.finalize is not None:
            lines.append("  finalize   :")
            for fline in self.finalize.render_summary().splitlines():
                lines.append(f"    {fline}")
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
    owner = f"harbor/{run_id}"
    log(
        f"[harbor.epic] run {run_id} started for epic {opts.epic_id} "
        f"(max_concurrency={opts.max_concurrency})"
    )

    # Acquire the Agent Mail epic-lock so a parallel `swarm-epic` chat session
    # (the legacy coordinator) can't try to drive the same epic concurrently.
    # Mail unavailable (`scripts/shared/agent_mail.py` missing) is non-fatal —
    # downstream repos that haven't scaffolded Agent Mail still get harbor.
    mail: Mail | None = None
    lock_held = False
    try:
        mail = Mail(repo_root)
        mail.acquire_epic(epic_id=opts.epic_id, owner=owner)
        lock_held = True
        log(f"[harbor.epic] acquired epic-lock for {opts.epic_id} as {owner}")
    except FileNotFoundError as e:
        log(f"[harbor.epic] epic-lock unavailable ({e}); continuing without it")
        mail = None
    except Exception as e:  # noqa: BLE001
        # Most commonly AgentMailError code=10 — lock held by another owner.
        details = getattr(e, "details", None) or {}
        existing_owner = details.get("owner") if isinstance(details, dict) else None
        msg = (
            f"epic {opts.epic_id} is already locked"
            + (f" by {existing_owner}" if existing_owner else "")
            + f": {e}"
        )
        log(f"[harbor.epic] {msg}")
        store.end_run(run_id, status="aborted")
        store.close()
        return RunEpicResult(
            epic_id=opts.epic_id,
            run_id=run_id,
            iterations=0,
            closed=[],
            failed=[],
            exit_reason="lock_held",
        )

    attempted: set[str] = set()
    closed: list[str] = []
    failed: list[tuple[str, str]] = []
    # Beads whose reservation conflicts with another holder. They stay out
    # of `attempted` so each tick re-tries them; the count is for log
    # de-duplication only.
    deferred: dict[str, int] = {}
    # Per-bead reservation owner — populated when epic.py successfully
    # reserves Files: paths before submitting run_bead. The same key
    # signals "epic owns the reservation, run_bead skipped reserve" and is
    # the owner string we hand to mail.release_reservations on reap.
    reservations: dict[str, str] = {}
    iterations = 0
    exit_reason = "drained"
    in_flight: dict[str, Future] = {}

    pool = ThreadPoolExecutor(max_workers=opts.max_concurrency, thread_name_prefix="harbor-bead")
    finalize_result = None
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
            deferred_this_tick: list[str] = []

            # Spawn fresh beads up to the concurrency cap.
            for bead in ready:
                bid = bead.get("id")
                if not bid or bid in in_flight or bid in attempted:
                    continue
                if len(in_flight) >= opts.max_concurrency:
                    break

                # Pre-check / pre-reserve Files: paths so two ready beads
                # claiming overlapping files don't both spawn. The owner is
                # per-bead so reservations across this run's beads conflict
                # the same way they would across distinct harbor sessions.
                files = parse_files_section(bead.get("description") or "")
                bead_owner = f"harbor/{run_id}/{bid}"
                outcome: ReservationOutcome
                try:
                    if mail is not None and files:
                        # Register the per-bead worker first so it shows up
                        # in agents.json with role=worker.
                        try:
                            mail.register(
                                name=bead_owner, role="worker", bead_id=bid,
                                epic_id=opts.epic_id,
                            )
                        except Exception as e:  # noqa: BLE001
                            log(f"[harbor.epic] register({bead_owner}) failed: {e!r}; continuing")
                        outcome = try_reserve_for_bead(
                            mail, owner=bead_owner, files=files,
                            bead_id=bid, epic_id=opts.epic_id,
                        )
                    else:
                        # No mail or no files → no reservation needed.
                        outcome = ReservationOutcome(
                            ok=True, available=mail is not None,
                        )
                except Exception as e:  # noqa: BLE001
                    log(f"[harbor.epic] reservation pre-check raised for {bid}: {e!r}; spawning anyway")
                    outcome = ReservationOutcome(ok=True, available=False)

                if not outcome.ok:
                    prev = deferred.get(bid, 0)
                    deferred[bid] = prev + 1
                    holders = ", ".join(outcome.conflict_with) or "<unknown>"
                    # Log on first defer and every 10th tick after, so a
                    # long-held reservation doesn't spam the log.
                    if prev == 0 or (prev + 1) % 10 == 0:
                        log(
                            f"[harbor.epic] deferred {bid} — reservation held by "
                            f"{holders} (deferred {prev + 1} time"
                            f"{'s' if prev + 1 != 1 else ''})"
                        )
                    deferred_this_tick.append(bid)
                    continue

                # Reservation acquired (or unavailable mail — proceed without).
                attempted.add(bid)
                deferred.pop(bid, None)
                if outcome.available and files:
                    reservations[bid] = bead_owner
                bead_opts = _make_bead_opts(opts, bid, repo_root)
                in_flight[bid] = pool.submit(
                    run_bead, bead_opts, log=log,
                    parent_run=(store, run_id),
                    pre_reserved_owner=(
                        bead_owner if outcome.available and files else None
                    ),
                )
                spawned_this_tick.append(bid)

            log(
                f"[harbor.epic] tick #{iterations}: ready={ready_ids} "
                f"running={list(in_flight)} attempted={sorted(attempted)} "
                f"spawned={spawned_this_tick} deferred={deferred_this_tick}"
            )

            if not in_flight and not deferred:
                # Nothing running and nothing waiting. Either ready is empty
                # (drained) or every ready bead has been attempted in this run.
                non_attempted = [b for b in ready_ids if b and b not in attempted]
                if non_attempted:
                    # Defensive: shouldn't happen since the spawn loop above
                    # consumes any non-attempted-non-deferred id with room.
                    exit_reason = "drained"
                else:
                    exit_reason = "drained" if not ready else "all_attempted"
                break

            if opts.max_iterations is not None and iterations >= opts.max_iterations:
                # Distinguish "out of iterations because we couldn't make
                # progress on deferred beads" from a generic max-out: the
                # operator-visible reason is more informative.
                if deferred and not in_flight:
                    exit_reason = "deferred_out"
                else:
                    exit_reason = "max_iterations"
                break

            # Nothing to wait on but deferred beads still pending — sleep
            # before re-polling so we don't busy-loop the conflict-retry case.
            if not in_flight:
                time.sleep(opts.interval_s)
                continue

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

                # Release the per-bead reservation so the next ready bead
                # claiming overlapping files can spawn.
                bead_owner = reservations.pop(bid, None)
                if bead_owner is not None and mail is not None:
                    try:
                        mail.release_reservations(owner=bead_owner, bead_id=bid)
                    except Exception as e:  # noqa: BLE001
                        log(f"[harbor.epic] release_reservations({bead_owner}) failed: {e!r}")

        # Finalize step — runs only when the loop drained cleanly with no
        # bead-level failures. A broken build/test shouldn't get a sign-off
        # review, so build-and-test gates review-epic inside run_finalize.
        if exit_reason == "drained" and not failed and not opts.skip_finalize:
            from .finalize import run_finalize
            log(f"[harbor.epic] all beads drained; running finalize for {opts.epic_id}")
            finalize_result = run_finalize(
                epic_id=opts.epic_id,
                store=store,
                run_id=run_id,
                repo_root=repo_root,
                profile=opts.profile,
                model=opts.model,
                effort=opts.effort,
                bead_timeout_s=opts.bead_timeout_s,
                keep_pane_after_finish=opts.keep_pane_after_finish,
                log=log,
            )
            if not finalize_result.all_passed:
                exit_reason = "finalize_failed"
                log(
                    f"[harbor.epic] finalize failed: "
                    f"failed={finalize_result.steps_failed} "
                    f"skipped={finalize_result.skipped}"
                )
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
        # Release any reservations still held by abandoned in-flight beads.
        if reservations and mail is not None:
            for bid, bead_owner in list(reservations.items()):
                try:
                    mail.release_reservations(owner=bead_owner, bead_id=bid)
                except Exception as e:  # noqa: BLE001
                    log(f"[harbor.epic] cleanup release_reservations({bead_owner}) failed: {e!r}")
            reservations.clear()
        if lock_held and mail is not None:
            try:
                mail.release_epic(epic_id=opts.epic_id, owner=owner)
                log(f"[harbor.epic] released epic-lock for {opts.epic_id}")
            except Exception as e:  # noqa: BLE001
                log(f"[harbor.epic] release_epic failed: {e!r}")
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
        finalize=finalize_result,
    )
