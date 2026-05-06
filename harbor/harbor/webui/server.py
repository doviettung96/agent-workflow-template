"""FastAPI server that drives single-bead harbor orchestration from a browser.

Mounted at 127.0.0.1:8765. Endpoints:

- GET  /                          → dashboard (active workers, ready beads, blockers)
- GET  /bead/{bead_id}            → bead detail (contract preview, pane capture, attach hint)
- POST /actions/run-bead/{bead_id} → start a bead in a background thread
- POST /actions/kill/{bead_id}    → kill the tmux window and let run_bead exit
- POST /_internal/finished        → invoked by harbor-bead-runner when its agent exits

The webview deliberately does not embed a terminal. For live agent interaction
the user pastes the attach command into Git Bash. The dashboard surfaces the
exact `tmux -L harbor attach -t ...` command.
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..agent import Config, load_config
from ..beads import Beads
from ..orchestrator import (
    FALLBACK_DIR,
    RunBeadOptions,
    run_bead,
    session_name_for,
)
from ..state import StateStore
from ..tmux import Tmux

TEMPLATES_DIR = Path(__file__).parent / "templates"


@dataclass
class _ActiveRun:
    bead_id: str
    thread: threading.Thread
    profile: str
    model: str
    effort: str


@dataclass
class HarborApp:
    """Holds shared state for the FastAPI app — repo root, config, active threads."""

    repo_root: Path
    cfg: Config
    active_runs: dict[str, _ActiveRun] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)


def create_app(repo_root: str | Path) -> FastAPI:
    repo_root_p = Path(repo_root).resolve()
    cfg_path = repo_root_p / "harbor.yml"
    cfg = load_config(cfg_path if cfg_path.exists() else None)

    state = HarborApp(repo_root=repo_root_p, cfg=cfg)
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    app = FastAPI(title="harbor", docs_url=None, redoc_url=None)

    # ----- helpers --------------------------------------------------------

    def _beads() -> Beads:
        return Beads()

    def _store() -> StateStore:
        return StateStore(state.repo_root)

    def _tmux() -> Tmux:
        return Tmux()

    def _is_active(bead_id: str) -> bool:
        with state.lock:
            run = state.active_runs.get(bead_id)
            return bool(run and run.thread.is_alive())

    def _spawn_run(bead_id: str, profile: str, model: str | None, effort: str | None) -> None:
        opts = RunBeadOptions(
            bead_id=bead_id,
            profile=profile,
            model=model,
            effort=effort,
            repo_root=state.repo_root,
            timeout_s=60 * 60 * 6,  # generous default for browser-launched runs
        )

        def _runner() -> None:
            try:
                run_bead(opts, log=lambda *_a, **_k: None)
            except Exception as e:  # noqa: BLE001
                # Surface failures via state.json — the orchestrator already records
                # what it can, but unexpected exceptions still need a breadcrumb.
                store = _store()
                run = store.active_run()
                if run is not None:
                    store.record_event(
                        run_id=run["run_id"],
                        bead_id=bead_id,
                        type="webui_run_error",
                        payload={"error": repr(e)},
                    )
            finally:
                with state.lock:
                    state.active_runs.pop(bead_id, None)

        t = threading.Thread(target=_runner, daemon=True, name=f"harbor-run-{bead_id}")
        with state.lock:
            state.active_runs[bead_id] = _ActiveRun(
                bead_id=bead_id,
                thread=t,
                profile=profile,
                model=model or "",
                effort=effort or "",
            )
        t.start()

    # ----- runner-side webhook (fast path; the file fallback still exists) ----

    @app.post("/_internal/finished")
    async def runner_finished(payload: dict[str, Any]) -> dict[str, Any]:
        bead_id = str(payload.get("bead_id") or "").strip()
        if not bead_id:
            raise HTTPException(400, "missing bead_id")
        target_dir = state.repo_root / FALLBACK_DIR
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / f"{bead_id}.json"
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return {"ok": True, "wrote": str(path)}

    # ----- read pages -----------------------------------------------------

    @app.get("/", response_class=HTMLResponse)
    async def dashboard(request: Request) -> HTMLResponse:
        store = _store()
        snap = store.snapshot()

        # Decorate workers with the attach command for convenience. With per-bead
        # sessions, `window_name` IS the session name — attach without a window.
        tmux = _tmux()
        for w in snap["workers"]:
            w["attach_command"] = tmux.attach_command(w["window_name"])

        # Ready beads (top-level, no parent filter — Phase 2 will add epic scoping)
        try:
            ready = _beads().ready()
        except Exception as e:  # noqa: BLE001
            ready = []
            snap.setdefault("errors", []).append(f"br ready failed: {e!r}")

        # Strip beads that are already in our active set
        active_ids = {w["bead_id"] for w in snap["workers"]}
        ready = [b for b in ready if b.get("id") not in active_ids and b.get("issue_type") != "epic"]

        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "snap": snap,
                "ready": ready[:50],
                "profiles": sorted(state.cfg.profiles.keys()),
                "default_profile": state.cfg.default_profile,
            },
        )

    @app.get("/bead/{bead_id}", response_class=HTMLResponse)
    async def bead_detail(request: Request, bead_id: str) -> HTMLResponse:
        try:
            bead = _beads().show(bead_id)
        except Exception as e:  # noqa: BLE001
            raise HTTPException(404, f"bead {bead_id!r} not found ({e})")

        tmux = _tmux()
        session = session_name_for(state.repo_root, bead_id)
        attach_cmd = tmux.attach_command(session)
        try:
            pane = tmux.capture_pane(session, "", lines=300) if tmux.has_session(session) else ""
        except Exception:  # noqa: BLE001
            pane = ""

        return templates.TemplateResponse(
            "bead.html",
            {
                "request": request,
                "bead": bead,
                "attach_command": attach_cmd,
                "pane_capture": pane,
                "is_active": _is_active(bead_id),
                "profiles": sorted(state.cfg.profiles.keys()),
                "default_profile": state.cfg.default_profile,
            },
        )

    # ----- HTMX partials --------------------------------------------------

    @app.get("/_partials/dashboard-status", response_class=HTMLResponse)
    async def dashboard_status(request: Request) -> HTMLResponse:
        store = _store()
        snap = store.snapshot()
        tmux = _tmux()
        for w in snap["workers"]:
            w["attach_command"] = tmux.attach_command(w["window_name"])
        return templates.TemplateResponse(
            "_status_partial.html",
            {"request": request, "snap": snap},
        )

    @app.get("/_partials/pane/{bead_id}", response_class=HTMLResponse)
    async def pane_partial(request: Request, bead_id: str) -> HTMLResponse:
        tmux = _tmux()
        session = session_name_for(state.repo_root, bead_id)
        try:
            pane = tmux.capture_pane(session, "", lines=300) if tmux.has_session(session) else ""
        except Exception:  # noqa: BLE001
            pane = ""
        return HTMLResponse(f"<pre class='pane-capture'>{_escape(pane)}</pre>")

    # ----- actions --------------------------------------------------------

    @app.post("/actions/run-bead/{bead_id}")
    async def action_run_bead(
        bead_id: str,
        profile: str = Form(""),
        model: str = Form(""),
        effort: str = Form(""),
    ) -> RedirectResponse:
        if _is_active(bead_id):
            raise HTTPException(409, f"bead {bead_id} already running")
        prof = profile or state.cfg.default_profile
        if prof not in state.cfg.profiles:
            raise HTTPException(400, f"unknown profile {prof!r}")
        _spawn_run(bead_id, prof, model or None, effort or None)
        return RedirectResponse(f"/bead/{bead_id}", status_code=303)

    @app.post("/actions/kill/{bead_id}")
    async def action_kill(bead_id: str) -> RedirectResponse:
        # 1. Kill the tmux session (its agent dies with it).
        tmux = _tmux()
        session = session_name_for(state.repo_root, bead_id)
        if tmux.has_session(session):
            tmux.kill_session(session)
        # 2. Drop a synthetic fallback so run_bead's poll loop exits cleanly.
        target_dir = state.repo_root / FALLBACK_DIR
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{bead_id}.json"
        if not target.exists():
            target.write_text(
                json.dumps(
                    {
                        "bead_id": bead_id,
                        "exit_code": 137,
                        "sentinel_status": "blocked",
                        "blocker_class": "env",
                        "last_output": "(killed by webui)",
                    }
                ),
                encoding="utf-8",
            )
        return RedirectResponse(f"/bead/{bead_id}", status_code=303)

    return app


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
