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
    legacy non-interactive mode and is not valid for live panes; it raises so
    misconfiguration fails loud rather than silently doing nothing.
    """
    mode = profile.prompt_injection
    if mode == "file_ref":
        # codex/claude REPL accept `@<path>` to load a file as the prompt body.
        # Use POSIX-style path so it works under MSYS/Git-Bash + native Windows shells.
        ref = prompt_path.resolve().as_posix()
        tmux.send_keys(session, window, f"@{ref}")
    elif mode == "send_keys":
        tmux.send_keys_literal(session, window, prompt, enter=True)
    elif mode == "stdin":
        raise ValueError(
            f"profile {profile.name!r}: prompt_injection=stdin is for the legacy "
            "harbor-bead-runner only; interactive panes need 'file_ref' or 'send_keys'"
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
) -> str:
    """Type the agent CLI command into the freshly-opened pane and Enter.

    Returns the rendered argv so callers can log it.
    """
    argv = profile.render_argv(model=model, effort=effort)
    cmd = shlex.join(argv)
    tmux.send_keys(session, window, cmd)
    return cmd


def _count_sentinels(pane: str, bead_id: str) -> int:
    needle = f"HARBOR-DONE: {bead_id} "
    return sum(1 for line in pane.splitlines() if line.strip().startswith(needle))


def run_bead(opts: RunBeadOptions, *, log: Callable[..., None] = print) -> RunBeadResult:
    repo_root = Path(opts.repo_root).resolve()
    beads = Beads()
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

    store = StateStore(repo_root)
    run_id = store.start_run(mode="single", epic_id=None)

    owner = f"harbor/{run_id}"
    files = parse_files_section(bead.get("description") or "")
    reservation_ok = False
    mail: Mail | None = None
    try:
        mail = Mail(repo_root)
        mail.register(name=owner, role="coordinator", bead_id=opts.bead_id)
        if files:
            mail.reserve(owner=owner, paths=files, bead_id=opts.bead_id)
            reservation_ok = True
            log(f"[harbor] reserved {len(files)} path(s) for {opts.bead_id}")
    except Exception as e:  # noqa: BLE001
        log(f"[harbor] mail unavailable ({e!r}); continuing without reservations")

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

    # 2. Spawn the pane (no command — psmux drops trailing-command args).
    tmux = Tmux()
    session = session_name_for(repo_root)
    tmux.ensure_session(session, str(repo_root))
    window_name = opts.bead_id
    tmux.new_window(session, window_name, str(repo_root), command="")
    log(f"[harbor] spawned tmux window: {tmux.attach_command(session, window_name)}")

    store.record_bead_start(
        run_id=run_id,
        bead_id=opts.bead_id,
        profile=profile.name,
        model=opts.model or profile.model,
        effort=opts.effort or profile.effort,
        window_name=window_name,
    )

    # 3. Launch the agent CLI inside the pane and wait for its banner.
    agent_cmd = launch_agent(tmux, session, window_name, profile, opts.model, opts.effort)
    log(f"[harbor] launched agent: {agent_cmd}")
    if opts.agent_startup_delay_s > 0:
        time.sleep(opts.agent_startup_delay_s)

    # 4. Inject the prompt.
    try:
        inject_prompt(tmux, session, window_name, profile, prompt_text, prompt_path)
        log(f"[harbor] injected prompt via {profile.prompt_injection} from {prompt_path}")
    except Exception as e:  # noqa: BLE001
        log(f"[harbor] prompt injection failed: {e!r}; aborting")
        store.record_bead_finish(
            run_id=run_id, bead_id=opts.bead_id, exit_code=1,
            sentinel_status=None, blocker_class="env",
        )
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

        # Window gone? agent crashed or user killed it
        if not tmux.window_exists(session, window_name):
            log("[harbor] pane disappeared; treating as env-blocker")
            final_status = "blocked"
            final_classification = "env"
            break

        try:
            pane = tmux.capture_pane(session, window_name, lines=opts.capture_lines)
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
                    f"pane left alive at: {tmux.attach_command(session, window_name)}"
                )

        time.sleep(opts.poll_interval_s)
    else:
        log(f"[harbor] timed out after {opts.timeout_s}s waiting for {opts.bead_id}")
        final_status = None
        final_classification = "env"

    # 6. Finalize.
    if final_status == "ok":
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
            tmux.kill_window(session, window_name)
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

    store.end_run(run_id, status="finished" if closed else "aborted")
    return RunBeadResult(
        bead_id=opts.bead_id,
        sentinel_status=final_status,
        blocker_class=final_classification,
        exit_code=0 if closed else 124,
        verify=verify_result,
        closed=closed,
    )
