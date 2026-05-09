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

from ..agent import AgentProfile, Config, load_config, load_issue_prefix, write_config
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
    issue_prefix: str | None = None
    allow_config_edit: bool = False
    active_runs: dict[str, _ActiveRun] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)


def create_app(repo_root: str | Path, *, allow_config_edit: bool = False) -> FastAPI:
    repo_root_p = Path(repo_root).resolve()
    cfg_path = repo_root_p / "harbor.yml"
    cfg = load_config(cfg_path if cfg_path.exists() else None)

    state = HarborApp(
        repo_root=repo_root_p,
        cfg=cfg,
        issue_prefix=load_issue_prefix(repo_root_p),
        allow_config_edit=allow_config_edit,
    )
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    app = FastAPI(title="harbor", docs_url=None, redoc_url=None)

    # ----- helpers --------------------------------------------------------

    def _beads() -> Beads:
        return Beads()

    def _store() -> StateStore:
        return StateStore(state.repo_root)

    def _tmux() -> Tmux:
        return Tmux()

    def _cfg_path() -> Path:
        return state.repo_root / "harbor.yml"

    def _reload_cfg() -> None:
        path = _cfg_path()
        state.cfg = load_config(path if path.exists() else None)

    def _is_active(bead_id: str) -> bool:
        with state.lock:
            run = state.active_runs.get(bead_id)
            return bool(run and run.thread.is_alive())

    def _blockers_for(bead: dict[str, Any], beads: Beads) -> list[dict[str, Any]]:
        """List of unresolved blockers for `bead` — dependencies whose target
        is not closed. parent-child deps are hierarchy, not runtime ordering,
        and are skipped (a child can run while its epic is still open)."""
        deps = bead.get("dependencies") or []
        out: list[dict[str, Any]] = []
        for dep in deps:
            if dep.get("type") == "parent-child":
                continue
            dep_id = dep.get("depends_on_id")
            if not dep_id:
                continue
            try:
                dep_bead = beads.show(dep_id)
            except Exception:  # noqa: BLE001
                out.append({"id": dep_id, "status": "unknown", "title": ""})
                continue
            if dep_bead.get("status") != "closed":
                out.append({
                    "id": dep_id,
                    "status": dep_bead.get("status") or "?",
                    "title": dep_bead.get("title") or "",
                })
        return out

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
    async def dashboard(request: Request, prefix: str | None = None) -> HTMLResponse:
        store = _store()
        snap = store.snapshot()

        # Decorate workers with the attach command for convenience. With per-bead
        # sessions, `window_name` IS the session name — attach without a window.
        tmux = _tmux()
        for w in snap["workers"]:
            w["attach_command"] = tmux.attach_command(w["window_name"])

        # Ready beads (top-level, no parent filter — Phase 2 will add epic scoping)
        beads = _beads()
        try:
            ready = beads.ready()
        except Exception as e:  # noqa: BLE001
            ready = []
            snap.setdefault("errors", []).append(f"br ready failed: {e!r}")

        # In-progress beads with no live worker — surface them so a user can see
        # beads stranded by a failed run (e.g. tmux not on PATH). The workers
        # panel covers the actively-running ones; this panel only shows the
        # leftovers.
        try:
            in_progress = beads.list_in_progress()
        except Exception as e:  # noqa: BLE001
            in_progress = []
            snap.setdefault("errors", []).append(f"br list (in_progress) failed: {e!r}")

        # Strip beads that are already in our active set
        active_ids = {w["bead_id"] for w in snap["workers"]}
        ready = [b for b in ready if b.get("id") not in active_ids and b.get("issue_type") != "epic"]
        in_progress = [b for b in in_progress if b.get("id") not in active_ids]

        prefix_filter = None if prefix == "all" else state.issue_prefix
        if prefix_filter:
            ready = [b for b in ready if str(b.get("id", "")).startswith(f"{prefix_filter}-")]
            in_progress = [
                b for b in in_progress
                if str(b.get("id", "")).startswith(f"{prefix_filter}-")
            ]
        ready_scope = {
            "mode": "all" if prefix == "all" or not state.issue_prefix else "prefix",
            "prefix": state.issue_prefix,
            "filtered_prefix": prefix_filter,
            "count": len(ready),
        }

        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "snap": snap,
                "ready": ready[:50],
                "in_progress": in_progress[:50],
                "ready_scope": ready_scope,
                "profiles": sorted(state.cfg.profiles.keys()),
                "default_profile": state.cfg.default_profile,
                "allow_config_edit": state.allow_config_edit,
            },
        )

    @app.get("/setup", response_class=HTMLResponse)
    async def setup(request: Request) -> HTMLResponse:
        if not state.allow_config_edit:
            raise HTTPException(404, "config editor is disabled")
        cfg_file_exists = _cfg_path().exists()
        return templates.TemplateResponse(
            "setup.html",
            {
                "request": request,
                "cfg": state.cfg,
                "cfg_file_exists": cfg_file_exists,
                "profiles": [state.cfg.profiles[name] for name in sorted(state.cfg.profiles)],
                "prompt_injections": ["file_ref", "send_keys", "prompt_arg", "stdin"],
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

        blockers = _blockers_for(bead, _beads()) if bead.get("status") in ("open", "in_progress") else []

        # Recent events for this bead — surfaces the why behind a previously-
        # failed run (otherwise the webui_run_error breadcrumb is invisible).
        try:
            recent_events = _store().recent_events_for(bead_id, limit=10)
        except Exception:  # noqa: BLE001
            recent_events = []
        last_error = next(
            (e for e in recent_events if e["type"] == "webui_run_error"),
            None,
        )

        return templates.TemplateResponse(
            "bead.html",
            {
                "request": request,
                "bead": bead,
                "attach_command": attach_cmd,
                "pane_capture": pane,
                "is_active": _is_active(bead_id),
                "blockers": blockers,
                "recent_events": recent_events,
                "last_error": last_error,
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
        force: str = Form(""),
    ) -> RedirectResponse:
        if _is_active(bead_id):
            raise HTTPException(409, f"bead {bead_id} already running")
        beads = _beads()
        try:
            bead = beads.show(bead_id)
        except Exception as e:  # noqa: BLE001
            raise HTTPException(404, f"bead {bead_id!r} not found ({e})")
        status = bead.get("status")
        if status not in {"open", "in_progress"}:
            raise HTTPException(
                409, f"bead {bead_id} status={status!r} — only open/in_progress beads can run"
            )
        if not force:
            blockers = _blockers_for(bead, beads)
            if blockers:
                ids = ", ".join(b["id"] for b in blockers)
                raise HTTPException(
                    409,
                    f"bead {bead_id} is blocked by: {ids}. "
                    "Pass force=1 to override (the agent will run, but its prerequisites are unmet).",
                )
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

    @app.post("/actions/profile/init-from-builtins")
    async def action_profile_init_from_builtins(request: Request) -> RedirectResponse:
        if not state.allow_config_edit:
            raise HTTPException(404, "config editor is disabled")
        cfg_path = _cfg_path()
        force = request.query_params.get("force") in {"1", "true", "yes"}
        if cfg_path.exists() and not force:
            raise HTTPException(409, "harbor.yml already exists")
        write_config(cfg_path, load_config(None), backup=force)
        _reload_cfg()
        return RedirectResponse("/setup", status_code=303)

    @app.post("/actions/profile/save")
    async def action_profile_save(request: Request) -> RedirectResponse:
        if not state.allow_config_edit:
            raise HTTPException(404, "config editor is disabled")
        form = await request.form()
        cfg = _config_from_form(form)
        write_config(_cfg_path(), cfg, backup=True)
        _reload_cfg()
        return RedirectResponse("/setup", status_code=303)

    return app


def _parse_list(value: str) -> list[str]:
    raw = value.strip()
    if not raw:
        return []
    if raw.startswith("["):
        parsed = json.loads(raw)
        if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
            raise ValueError("expected a JSON string array")
        return parsed
    return [part.strip() for part in raw.split(",") if part.strip()]


def _config_from_form(form: Any) -> Config:
    names = [str(v).strip() for v in form.getlist("profile_name") if str(v).strip()]
    action = str(form.get("_action") or "save")
    add_name = str(form.get("add_profile_name") or "").strip()
    if action == "add" and add_name and add_name not in names:
        names.append(add_name)
    if action.startswith("remove:"):
        remove_name = action.split(":", 1)[1]
        names = [name for name in names if name != remove_name]
    if not names:
        raise HTTPException(400, "at least one profile is required")

    profiles: dict[str, AgentProfile] = {}
    for name in names:
        prefix = f"profile_{name}_"
        try:
            command = _parse_list(str(form.get(prefix + "command") or ""))
            args_template = _parse_list(str(form.get(prefix + "args_template") or ""))
        except (json.JSONDecodeError, ValueError) as e:
            raise HTTPException(400, f"profile {name}: {e}") from e
        if action == "add" and name == add_name and not command:
            command = ["codex"]
            args_template = ["-m", "{model}", "--reasoning-effort", "{effort}"]
        if not command:
            raise HTTPException(400, f"profile {name}: command is required")
        injection = str(form.get(prefix + "prompt_injection") or "file_ref")
        if injection not in {"file_ref", "send_keys", "prompt_arg", "stdin"}:
            raise HTTPException(400, f"profile {name}: invalid prompt_injection")
        launch_template = str(form.get(prefix + "launch_template") or "")
        if injection == "prompt_arg" and "{prompt_path}" not in launch_template:
            raise HTTPException(
                400,
                f"profile {name}: prompt_arg requires launch_template to contain {{prompt_path}}",
            )
        profiles[name] = AgentProfile(
            name=name,
            agent_kind=str(form.get(prefix + "agent_kind") or "codex"),
            command=command,
            args_template=args_template,
            model=str(form.get(prefix + "model") or ""),
            effort=str(form.get(prefix + "effort") or ""),
            prompt_injection=injection,
            launch_template=launch_template,
        )

    default_profile = str(form.get("default_profile") or "").strip()
    if default_profile not in profiles:
        default_profile = names[0]
    default_shell_raw = str(form.get("default_shell") or "").strip()
    return Config(
        profiles=profiles,
        default_profile=default_profile,
        default_shell=default_shell_raw or None,
    )


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
