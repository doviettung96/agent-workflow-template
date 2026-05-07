"""High-level run-bead orchestration. Used by `harbor run-bead` and the webview.

The pane is now the agent's REPL directly — no `harbor-bead-runner` wrapper
inside it. The orchestrator drives the pane like a person:

  1. `tmux new-window`                       (empty pane, default shell)
  2. `tmux send-keys "<agent-cli> <args>"`   (launch the REPL)
  3. wait a beat, then inject the prompt:
       - `file_ref`:  send-keys "@<absolute-prompt-path>" + Enter
       - `send_keys`: send-keys -l "<prompt body>"        + Enter
  4. poll `capture-pane` every `poll_interval_s` seconds; parse HARBOR-DONE
       - `status=ok`:      run Verify, on pass close bead and exit
       - `status=blocked`: mark `stuck`, leave pane alive so a human can
         attach and chat with the agent. The orchestrator keeps polling — when
         the agent emits a fresh HARBOR-DONE the new line supersedes the old.

The synthetic-fallback file at `.beads/workflow/runner-finished/<id>.json`
remains as a diagnostic kill-channel: webview's `/actions/kill` writes one,
and the poll loop treats its appearance as an external "stop now" request.
"""
from __future__ import annotations

import hashlib
import json
import re
import shlex
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .agent import AgentProfile, Config, load_config
from .beads import Beads, BeadsError
from .mail import Mail
from .prompt import parse_sentinel, render_worker_prompt
from .state import StateStore
from .tmux import Tmux, TmuxError
from .verify import VerifyResult, run_verify

FALLBACK_DIR = Path(".beads/workflow/runner-finished")
PROMPTS_DIR = Path(".beads/workflow/runner-prompts")
SESSION_PREFIX = "harbor-"


@dataclass
class RunBeadOptions:
    bead_id: str
    profile: str | None = None
    model: str | None = None
    effort: str | None = None
    repo_root: Path = field(default_factory=Path.cwd)
    daemon_url: str = "http://127.0.0.1:8765"
    poll_interval_s: float = 2.0
    timeout_s: float = 60 * 60 * 6  # 6 hours — interactive panes can sit a while
    keep_pane_after_finish: bool = True
    # Pause between launching the agent CLI and pasting the prompt. Real codex /
    # claude REPLs take a moment to print their banner and accept input.
    agent_startup_delay_s: float = 3.0
    # How many lines of pane scrollback to scan for the sentinel each poll.
    # 2000 is plenty for normal use and well within capture-pane's limits.
    capture_lines: int = 2000


def session_name_for(repo_root: Path, bead_id: str | None = None) -> str:
    """Tmux session name. With `bead_id`, the name is per-bead so each agent
    gets its own session — the only model that targets reliably under psmux,
    where `send-keys -t <session>:<window>` is unreliable for non-active
    windows. With `bead_id=None`, returns the per-repo prefix only (used in
    the webview's "harbor running" badges)."""
    digest = hashlib.sha256(str(repo_root.resolve()).encode("utf-8")).hexdigest()[:8]
    base = f"{SESSION_PREFIX}{digest}"
    if bead_id is None:
        return base
    return f"{base}-{window_name_for(bead_id)}"


def window_name_for(bead_id: str) -> str:
    """Tmux parses `.` in target strings as the pane separator
    (`session:window.pane`), so bead-ids like `awt-zmq.99` are unsafe in
    targets. Replace `.` with `_`. Used inside `session_name_for` so that the
    sanitized id appears in the per-bead session name; bead_id itself stays
    untouched in state/storage."""
    return bead_id.replace(".", "_")


def write_tmux_config(workflow_dir: Path, default_shell: str | None) -> Path | None:
    """Write a tiny tmux conf with `default-shell` so the very FIRST session's
    auto-created window already runs the right shell. Returns the conf path,
    or None if there's nothing to configure."""
    if not default_shell:
        return None
    workflow_dir.mkdir(parents=True, exist_ok=True)
    conf = workflow_dir / "harbor-tmux.conf"
    conf.write_text(
        f"# Auto-written by harbor — do not edit by hand.\n"
        f"set-option -g default-shell \"{default_shell}\"\n",
        encoding="utf-8",
    )
    return conf


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
        body = re.sub(r"\s*\(.*?\)\s*$", "", body).strip()
        if body and not body.lower().startswith("manual"):
            paths.append(body)
    return paths


@dataclass(frozen=True)
class ReservationOutcome:
    """Result of `try_reserve_for_bead`. `available=False` means the Agent
    Mail module isn't installed (downstream repos that haven't scaffolded
    `scripts/shared/agent_mail.py`). `ok=False` with `available=True` means
    a real reservation conflict — `conflict_with` lists the holding owners
    so the caller can defer or message the operator.
    """
    ok: bool
    available: bool
    conflict_with: tuple[str, ...] = ()


def try_reserve_for_bead(
    mail: "Mail | None",
    *,
    owner: str,
    files: list[str],
    bead_id: str,
    epic_id: str | None = None,
) -> ReservationOutcome:
    """Attempt `mail.reserve` and translate Agent Mail's raise-on-conflict
    contract into a pre-checkable outcome. Used by both `run_bead` (single
    mode) and `epic.run_epic` (parallel mode) so reservation conflicts are
    handled the same way regardless of how the bead was launched.

    A None mail or empty files list is treated as success — there is nothing
    to check. Errors that aren't conflicts (network, FK, etc.) propagate so
    the caller can decide; only AgentMailError code 12 / `details.conflicts`
    is mapped to `ok=False`.
    """
    if mail is None:
        return ReservationOutcome(ok=True, available=False)
    if not files:
        return ReservationOutcome(ok=True, available=True)
    try:
        mail.reserve(owner=owner, paths=files, bead_id=bead_id, epic_id=epic_id)
    except Exception as e:  # noqa: BLE001
        details = getattr(e, "details", None)
        if isinstance(details, dict) and details.get("conflicts"):
            holders = tuple(sorted({
                str(c.get("owner") or "?") for c in details["conflicts"]
            }))
            return ReservationOutcome(
                ok=False, available=True, conflict_with=holders,
            )
        # Not a conflict — re-raise so the caller can decide (in practice
        # `run_bead` falls back to "log + continue without reservations").
        raise
    return ReservationOutcome(ok=True, available=True)


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


def _read_kill_signal(repo_root: Path, bead_id: str) -> dict[str, Any] | None:
    """Look for an external stop signal — the webview's /actions/kill writes one
    of these to the legacy runner-finished dir. We honor it as a hard stop."""
    target = repo_root / FALLBACK_DIR / f"{bead_id}.json"
    if not target.exists():
        return None
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _write_prompt_file(repo_root: Path, bead_id: str, prompt: str) -> Path:
    target_dir = repo_root / PROMPTS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{bead_id}.md"
    path.write_text(prompt, encoding="utf-8")
    return path


def inject_prompt(
    tmux: Tmux,
    session: str,
    window: str,
    profile: AgentProfile,
    prompt: str,
    prompt_path: Path,
) -> None:
    """Push the worker prompt into the agent's interactive REPL.

    The mode is per-profile — see AgentProfile.prompt_injection. `stdin` is the
    legacy non-interactive mode and is not valid for live panes; `prompt_arg`
    means the prompt was injected as part of the launch command line and there's
    nothing left to do here.
    """
    mode = profile.prompt_injection
    if mode == "file_ref":
        # claude REPL accepts `@<path>` to load a file as the prompt body.
        # Codex does NOT — use prompt_arg for codex.
        ref = prompt_path.resolve().as_posix()
        tmux.send_keys(session, window, f"@{ref}")
    elif mode == "send_keys":
        tmux.send_keys_literal(session, window, prompt, enter=True)
    elif mode == "prompt_arg":
        # The prompt rode in on the launch command line via launch_template's
        # {prompt_path} placeholder — no further injection needed.
        return
    elif mode == "stdin":
        raise ValueError(
            f"profile {profile.name!r}: prompt_injection=stdin is for the legacy "
            "harbor-bead-runner only; interactive panes need 'file_ref', 'send_keys', "
            "or 'prompt_arg'"
        )
    else:
        raise ValueError(f"unknown prompt_injection {mode!r} on profile {profile.name!r}")


def launch_agent(
    tmux: Tmux,
    session: str,
    window: str,
    profile: AgentProfile,
    model: str | None,
    effort: str | None,
    prompt_path: Path,
) -> str:
    """Type the agent CLI command into the freshly-opened pane and Enter.

    When `profile.launch_template` is set, that string is formatted with
    {model}/{effort}/{prompt_path} and sent verbatim — letting the pane's shell
    do its own file substitution (e.g. PowerShell `(Get-Content -Raw '{path}')`
    or bash `"$(cat '{path}')"`). Otherwise the legacy command + args_template
    argv is shlex-joined and sent.

    Returns the rendered command string so callers can log it.
    """
    if profile.launch_template:
        cmd = profile.launch_template.format(
            model=(model if model is not None else profile.model),
            effort=(effort if effort is not None else profile.effort),
            prompt_path=prompt_path.resolve().as_posix(),
        )
    else:
        argv = profile.render_argv(model=model, effort=effort)
        cmd = shlex.join(argv)
    tmux.send_keys(session, window, cmd)
    return cmd


def _count_sentinels(pane: str, bead_id: str) -> int:
    needle = f"HARBOR-DONE: {bead_id} "
    return sum(1 for line in pane.splitlines() if line.strip().startswith(needle))


def run_bead(
    opts: RunBeadOptions,
    *,
    log: Callable[..., None] = print,
    parent_run: tuple[StateStore, str] | None = None,
    pre_reserved_owner: str | None = None,
    synthetic_bead: dict | None = None,
) -> RunBeadResult:
    """Spawn one bead in a tmux session and wait for it to finish.

    `parent_run`, when supplied, is `(store, run_id)` from a higher-level
    orchestrator (e.g. `harbor.epic.run_epic`). In that mode this function
    records bead events against the parent run and does NOT call
    `start_run`/`end_run` itself — the caller owns the run lifecycle.

    `pre_reserved_owner`, when set, signals that the caller already
    registered + reserved Files: paths under that owner. `run_bead` skips
    its own register/reserve/release and trusts the caller to do the
    cleanup once the future completes. Used by the parallel epic runner
    so reservation conflicts are detected once at submission time, not
    redundantly inside each worker thread.

    `synthetic_bead`, when set, is a pre-resolved bead-shaped dict (id,
    description, status keys at minimum). `run_bead` uses it instead of
    calling `beads.show`, and skips all `br update`/`br close` calls
    since there is no real bead in the database. Used by `harbor.finalize`
    to drive the build-and-test + review-epic finalize steps through the
    same tmux pane infrastructure as a normal bead.
    """
    repo_root = Path(opts.repo_root).resolve()
    is_synthetic = synthetic_bead is not None
    beads = Beads()
    if is_synthetic:
        bead = dict(synthetic_bead)
        bead.setdefault("id", opts.bead_id)
        bead.setdefault("status", "open")
    else:
        bead = beads.show(opts.bead_id)

    if bead.get("status") not in {"open", "in_progress"}:
        raise RuntimeError(
            f"bead {opts.bead_id} status={bead.get('status')} — "
            "harbor only runs open or in_progress beads"
        )

    cfg: Config = load_config(
        repo_root / "harbor.yml" if (repo_root / "harbor.yml").exists() else None
    )
    profile = cfg.get(opts.profile)

    if parent_run is not None:
        store, run_id = parent_run
        owns_run = False
    else:
        store = StateStore(repo_root)
        run_id = store.start_run(mode="single", epic_id=None)
        owns_run = True

    owner = pre_reserved_owner or f"harbor/{run_id}/{opts.bead_id}"
    files = parse_files_section(bead.get("description") or "")
    reservation_ok = False
    mail: Mail | None = None

    if pre_reserved_owner is not None:
        # Caller (epic.run_epic) already registered + reserved under this owner.
        # We still want a Mail handle for thread/post operations later, but we
        # must NOT touch register/reserve/release — that's the caller's job.
        try:
            mail = Mail(repo_root)
        except Exception as e:  # noqa: BLE001
            log(f"[harbor] mail handle unavailable ({e!r}); pre-reserved owner is best-effort only")
            mail = None
    else:
        try:
            mail = Mail(repo_root)
            mail.register(name=owner, role="coordinator", bead_id=opts.bead_id)
            if files:
                outcome = try_reserve_for_bead(
                    mail, owner=owner, files=files, bead_id=opts.bead_id,
                )
                if not outcome.ok:
                    holders = ", ".join(outcome.conflict_with) or "<unknown>"
                    log(
                        f"[harbor] reservation conflict for {opts.bead_id}: "
                        f"held by {holders}; aborting before tmux spawn"
                    )
                    store.record_bead_finish(
                        run_id=run_id, bead_id=opts.bead_id, exit_code=124,
                        sentinel_status="reservation_conflict",
                        blocker_class="reservation",
                    )
                    if owns_run:
                        store.end_run(run_id, status="aborted")
                    return RunBeadResult(
                        bead_id=opts.bead_id,
                        sentinel_status="reservation_conflict",
                        blocker_class="reservation",
                        exit_code=124, verify=None, closed=False,
                    )
                reservation_ok = True
                log(f"[harbor] reserved {len(files)} path(s) for {opts.bead_id}")
        except FileNotFoundError as e:
            log(f"[harbor] mail unavailable ({e}); continuing without reservations")
            mail = None
        except Exception as e:  # noqa: BLE001
            log(f"[harbor] mail error ({e!r}); continuing without reservations")
            mail = None

    if is_synthetic:
        log(f"[harbor] synthetic bead {opts.bead_id} — skipping br update/close")
    else:
        upd_ok, upd_err = _safe_br_update(beads, opts.bead_id, "in_progress")
        if not upd_ok:
            log(f"[harbor] WARNING br update failed: {upd_err}; continuing (JSONL is source of truth)")

    # 1. Render and persist the prompt — file_ref mode reads it back via @<path>;
    #    send_keys mode pastes it directly. Either way, having it on disk is a
    #    debugging lifesaver.
    prompt_text = render_worker_prompt(bead)
    prompt_path = _write_prompt_file(repo_root, opts.bead_id, prompt_text)

    # Clear any stale kill-signal from a previous run so the poll loop does not
    # short-circuit on the first iteration.
    stale_kill = repo_root / FALLBACK_DIR / f"{opts.bead_id}.json"
    if stale_kill.exists():
        try:
            stale_kill.unlink()
        except OSError:
            pass

    # 2. Spawn a dedicated tmux session for this bead. One bead = one session
    #    sidesteps psmux's broken `-t session:window` targeting (only the
    #    active window in any session is reliably reachable). The session's
    #    auto-created default window IS the agent pane — no `new-window` dance.
    #    A tmux conf (-f) sets default-shell BEFORE the session starts so the
    #    first window already runs Git Bash on Windows, not PowerShell.
    workflow_dir = repo_root / ".beads" / "workflow"
    conf_path = write_tmux_config(workflow_dir, cfg.default_shell)
    tmux = Tmux(config_path=str(conf_path) if conf_path else None)
    session = session_name_for(repo_root, opts.bead_id)
    tmux.ensure_session(session, str(repo_root), default_shell=cfg.default_shell)
    log(f"[harbor] spawned tmux session: {tmux.attach_command(session)}")

    store.record_bead_start(
        run_id=run_id,
        bead_id=opts.bead_id,
        profile=profile.name,
        model=opts.model or profile.model,
        effort=opts.effort or profile.effort,
        window_name=session,  # per-bead session IS the addressable target now
    )

    # 3. Launch the agent CLI inside the pane and wait for its banner.
    #    With per-bead sessions, `window=""` targets the active (=only) window.
    agent_cmd = launch_agent(
        tmux, session, "", profile, opts.model, opts.effort, prompt_path
    )
    log(f"[harbor] launched agent: {agent_cmd}")
    if opts.agent_startup_delay_s > 0:
        time.sleep(opts.agent_startup_delay_s)

    # 4. Inject the prompt (no-op when profile uses prompt_arg / launch_template).
    try:
        inject_prompt(tmux, session, "", profile, prompt_text, prompt_path)
        if profile.prompt_injection != "prompt_arg":
            log(f"[harbor] injected prompt via {profile.prompt_injection} from {prompt_path}")
    except Exception as e:  # noqa: BLE001
        log(f"[harbor] prompt injection failed: {e!r}; aborting")
        store.record_bead_finish(
            run_id=run_id, bead_id=opts.bead_id, exit_code=1,
            sentinel_status=None, blocker_class="env",
        )
        if owns_run:
            store.end_run(run_id, status="aborted")
        return RunBeadResult(
            bead_id=opts.bead_id, sentinel_status=None, blocker_class="env",
            exit_code=1, verify=None, closed=False,
        )

    # 5. Poll loop — capture the pane until we see a HARBOR-DONE we haven't
    #    acted on yet, or someone kills the pane / drops the kill-signal file.
    deadline = time.monotonic() + opts.timeout_s
    seen_emissions = 0
    final_status: str | None = None
    final_classification: str | None = None
    verify_result: VerifyResult | None = None
    closed = False

    while time.monotonic() < deadline:
        # External kill signal? (webview /actions/kill writes the legacy fallback file)
        kill = _read_kill_signal(repo_root, opts.bead_id)
        if kill is not None:
            log(f"[harbor] kill signal received for {opts.bead_id}: {kill.get('last_output')!r}")
            final_status = kill.get("sentinel_status") or "blocked"
            final_classification = kill.get("blocker_class") or "env"
            break

        # Session gone? agent crashed or user killed it (kill-session).
        if not tmux.has_session(session):
            log("[harbor] tmux session disappeared; treating as env-blocker")
            final_status = "blocked"
            final_classification = "env"
            break

        try:
            pane = tmux.capture_pane(session, "", lines=opts.capture_lines)
        except TmuxError:
            time.sleep(opts.poll_interval_s)
            continue

        emissions = _count_sentinels(pane, opts.bead_id)
        if emissions > seen_emissions:
            seen_emissions = emissions
            sent = parse_sentinel(pane, opts.bead_id)
            if sent is None:
                # Sentinel detected but unparsable — wait for the next emission.
                time.sleep(opts.poll_interval_s)
                continue
            status, classification = sent
            log(
                f"[harbor] sentinel #{emissions} for {opts.bead_id}: "
                f"status={status} classification={classification}"
            )

            if status == "ok":
                verify_result = run_verify(bead, repo_root)
                if verify_result.skipped or verify_result.success:
                    final_status = "ok"
                    final_classification = "none"
                    break
                # Verify failed — downgrade to a stuck state so the agent
                # can react to a follow-up message from the human.
                log(f"[harbor] verify failed:\n{verify_result.render_summary()}")
                store.record_bead_stuck(
                    run_id=run_id,
                    bead_id=opts.bead_id,
                    sentinel_status="blocked",
                    blocker_class="env",
                )
                # Continue polling — agent may re-emit after fixing.
            else:  # status == "blocked"
                store.record_bead_stuck(
                    run_id=run_id,
                    bead_id=opts.bead_id,
                    sentinel_status=status,
                    blocker_class=classification,
                )
                log(
                    f"[harbor] {opts.bead_id} stuck ({classification}); "
                    f"pane left alive at: {tmux.attach_command(session)}"
                )

        time.sleep(opts.poll_interval_s)
    else:
        log(f"[harbor] timed out after {opts.timeout_s}s waiting for {opts.bead_id}")
        final_status = None
        final_classification = "env"

    # 6. Finalize.
    if final_status == "ok":
        if is_synthetic:
            # Synthetic beads have no row in the bead db — there is nothing
            # to close. We still treat success as "closed" for the result
            # so callers can short-circuit on .closed.
            closed = True
            log(f"[harbor] synthetic bead {opts.bead_id} verified (no br close)")
        else:
            ok, err = _safe_br_close(beads, opts.bead_id)
            if ok:
                closed = True
                log(f"[harbor] closed {opts.bead_id}")
            else:
                log(f"[harbor] WARNING br close failed: {err}; mark closed manually in JSONL")
        store.record_bead_finish(
            run_id=run_id,
            bead_id=opts.bead_id,
            exit_code=0,
            sentinel_status="ok",
            blocker_class="none",
        )
        if not opts.keep_pane_after_finish:
            tmux.kill_session(session)
    else:
        store.record_bead_finish(
            run_id=run_id,
            bead_id=opts.bead_id,
            exit_code=124,
            sentinel_status=final_status,
            blocker_class=final_classification or "env",
        )

    if reservation_ok and mail is not None:
        try:
            mail.release_reservations(owner=owner, bead_id=opts.bead_id)
        except Exception as e:  # noqa: BLE001
            log(f"[harbor] release_reservations failed: {e!r}")

    if owns_run:
        store.end_run(run_id, status="finished" if closed else "aborted")
    return RunBeadResult(
        bead_id=opts.bead_id,
        sentinel_status=final_status,
        blocker_class=final_classification,
        exit_code=0 if closed else 124,
        verify=verify_result,
        closed=closed,
    )
