"""High-level run-bead orchestration. Used by `harbor run-bead`.

For Phase 1 we keep this dead simple: one process, one bead, no HTTP server.
The runner-side wrapper writes a fallback file at
`.beads/workflow/runner-finished/<bead-id>.json`; we poll for it and act on
the payload.

When Phase 3 lands, the FastAPI server fields the runner's POST and pushes
into the same `_FinishedSignal` queue, so this orchestrator stays the same.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .agent import Config, load_config
from .beads import Beads, BeadsError
from .mail import Mail
from .prompt import parse_sentinel
from .state import StateStore
from .tmux import Tmux
from .verify import VerifyResult, run_verify

FALLBACK_DIR = Path(".beads/workflow/runner-finished")
SESSION_PREFIX = "harbor-"


@dataclass
class RunBeadOptions:
    bead_id: str
    profile: str | None = None
    model: str | None = None
    effort: str | None = None
    repo_root: Path = field(default_factory=Path.cwd)
    daemon_url: str = "http://127.0.0.1:8765"
    poll_interval_s: float = 1.0
    timeout_s: float = 60 * 60  # 1 hour default
    keep_pane_after_finish: bool = True


def session_name_for(repo_root: Path) -> str:
    digest = hashlib.sha256(str(repo_root.resolve()).encode("utf-8")).hexdigest()[:8]
    return f"{SESSION_PREFIX}{digest}"


def parse_files_section(description: str) -> list[str]:
    """Pull out paths under `Files:` (one per `- ...` line)."""
    if not description:
        return []
    section_re = re.compile(r"^([A-Z][A-Za-z]+):\s*$", re.MULTILINE)
    sections = list(section_re.finditer(description))
    files_idx = next((i for i, m in enumerate(sections) if m.group(1).lower() == "files"), None)
    if files_idx is None:
        return []
    start = sections[files_idx].end()
    end = sections[files_idx + 1].start() if files_idx + 1 < len(sections) else len(description)
    block = description[start:end]
    paths: list[str] = []
    for raw in block.splitlines():
        m = re.match(r"^\s*-\s+(.+)$", raw)
        if not m:
            continue
        body = m.group(1).strip()
        # Drop any inline parentheticals like " (one-paragraph)"
        body = re.sub(r"\s*\(.*?\)\s*$", "", body).strip()
        if body and not body.lower().startswith("manual"):
            paths.append(body)
    return paths


@dataclass
class RunBeadResult:
    bead_id: str
    sentinel_status: str | None
    blocker_class: str | None
    exit_code: int
    verify: VerifyResult | None
    closed: bool

    def render_summary(self) -> str:
        lines = [
            f"Bead {self.bead_id}",
            f"  exit_code     : {self.exit_code}",
            f"  sentinel      : {self.sentinel_status or 'none'}",
            f"  classification: {self.blocker_class or 'none'}",
        ]
        if self.verify is not None:
            lines.append("  verify        :")
            for v_line in self.verify.render_summary().splitlines():
                lines.append(f"    {v_line}")
        lines.append(f"  closed        : {self.closed}")
        return "\n".join(lines)


def _safe_br_update(beads: Beads, bead_id: str, status: str) -> tuple[bool, str | None]:
    """Try `br update --status` and swallow the known Windows FK bug.

    Returns (success, error_message_if_any). The orchestrator continues either
    way; the JSONL is the source of truth and a follow-up `br sync` can repair.
    """
    try:
        beads.update_status(bead_id, status)
        return True, None
    except BeadsError as e:
        return False, str(e)


def _safe_br_close(beads: Beads, bead_id: str) -> tuple[bool, str | None]:
    try:
        beads.close(bead_id)
        return True, None
    except BeadsError as e:
        return False, str(e)


def _wait_for_fallback(repo_root: Path, bead_id: str, timeout_s: float, poll_s: float) -> dict[str, Any] | None:
    target = repo_root / FALLBACK_DIR / f"{bead_id}.json"
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if target.exists():
            try:
                return json.loads(target.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                # File may still be mid-write; retry next tick
                pass
        time.sleep(poll_s)
    return None


def run_bead(opts: RunBeadOptions, *, log=print) -> RunBeadResult:
    repo_root = Path(opts.repo_root).resolve()
    beads = Beads()
    bead = beads.show(opts.bead_id)

    if bead.get("status") not in {"open", "in_progress"}:
        raise RuntimeError(
            f"bead {opts.bead_id} status={bead.get('status')} — "
            "harbor only runs open or in_progress beads"
        )

    cfg: Config = load_config(repo_root / "harbor.yml" if (repo_root / "harbor.yml").exists() else None)
    profile = cfg.get(opts.profile)

    # State + run id
    store = StateStore(repo_root)
    run_id = store.start_run(mode="single", epic_id=None)

    # Files reservation (best-effort — agent-mail backing requires `git`)
    owner = f"harbor/{run_id}"
    files = parse_files_section(bead.get("description") or "")
    reservation_ok = False
    try:
        mail = Mail(repo_root)
        mail.register(name=owner, role="coordinator", bead_id=opts.bead_id)
        if files:
            mail.reserve(owner=owner, paths=files, bead_id=opts.bead_id)
            reservation_ok = True
            log(f"[harbor] reserved {len(files)} path(s) for {opts.bead_id}")
    except Exception as e:
        log(f"[harbor] mail unavailable ({e!r}); continuing without reservations")

    # Mark in-progress (best-effort)
    upd_ok, upd_err = _safe_br_update(beads, opts.bead_id, "in_progress")
    if not upd_ok:
        log(f"[harbor] WARNING br update failed: {upd_err}; continuing (JSONL is source of truth)")

    # Spawn the tmux pane
    tmux = Tmux()
    session = session_name_for(repo_root)
    tmux.ensure_session(session, str(repo_root))
    runner_cmd_parts = ["harbor-bead-runner", opts.bead_id, "--repo-root", str(repo_root)]
    if opts.profile:
        runner_cmd_parts += ["--profile", opts.profile]
    if opts.model:
        runner_cmd_parts += ["--model", opts.model]
    if opts.effort:
        runner_cmd_parts += ["--effort", opts.effort]
    runner_cmd = " ".join(runner_cmd_parts)

    window_name = opts.bead_id
    tmux.new_window(session, window_name, str(repo_root), runner_cmd)
    log(f"[harbor] spawned tmux window: {tmux.attach_command(session, window_name)}")

    store.record_bead_start(
        run_id=run_id,
        bead_id=opts.bead_id,
        profile=profile.name,
        model=opts.model or profile.model,
        effort=opts.effort or profile.effort,
        window_name=window_name,
    )

    # Wait for the runner to write the fallback file (Phase 3 will replace this with HTTP).
    log(f"[harbor] waiting for runner to finish (timeout {opts.timeout_s}s)…")
    payload = _wait_for_fallback(repo_root, opts.bead_id, opts.timeout_s, opts.poll_interval_s)
    if payload is None:
        log(f"[harbor] timed out waiting for {opts.bead_id}; leaving pane open")
        store.record_bead_finish(
            run_id=run_id,
            bead_id=opts.bead_id,
            exit_code=124,  # standard timeout
            sentinel_status=None,
            blocker_class="env",
        )
        store.end_run(run_id, status="aborted")
        return RunBeadResult(
            bead_id=opts.bead_id,
            sentinel_status=None,
            blocker_class="env",
            exit_code=124,
            verify=None,
            closed=False,
        )

    sentinel_status = payload.get("sentinel_status")
    blocker_class = payload.get("blocker_class")
    exit_code = int(payload.get("exit_code", 0))

    # Verify (only when agent claims ok)
    verify_result: VerifyResult | None = None
    if sentinel_status == "ok":
        verify_result = run_verify(bead, repo_root)
        if verify_result.skipped:
            log("[harbor] no executable verify commands — running anyway is unsafe; "
                "treating as success but flagging classification=clarify on blocker if user disagrees")
        elif not verify_result.success:
            log(f"[harbor] verify failed:\n{verify_result.render_summary()}")
            sentinel_status = "blocked"
            blocker_class = "env"

    # Close the bead if everything is green; otherwise leave it open with a note.
    closed = False
    if sentinel_status == "ok":
        ok, err = _safe_br_close(beads, opts.bead_id)
        if ok:
            closed = True
            log(f"[harbor] closed {opts.bead_id}")
        else:
            log(f"[harbor] WARNING br close failed: {err}; mark closed manually in JSONL")
    else:
        log(f"[harbor] {opts.bead_id} blocked: classification={blocker_class}; pane left open")

    store.record_bead_finish(
        run_id=run_id,
        bead_id=opts.bead_id,
        exit_code=exit_code,
        sentinel_status=sentinel_status,
        blocker_class=blocker_class,
    )

    # Release reservations
    if reservation_ok:
        try:
            mail.release_reservations(owner=owner, bead_id=opts.bead_id)
        except Exception as e:
            log(f"[harbor] release_reservations failed: {e!r}")

    # Optionally clean up the pane on success.
    if closed and not opts.keep_pane_after_finish:
        tmux.kill_window(session, window_name)

    store.end_run(run_id, status="finished")
    return RunBeadResult(
        bead_id=opts.bead_id,
        sentinel_status=sentinel_status,
        blocker_class=blocker_class,
        exit_code=exit_code,
        verify=verify_result,
        closed=closed,
    )
