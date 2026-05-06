"""Single source of truth for the harbor runner.

- SQLite at `.beads/workflow/harbor.db` is the authoritative log of runs, bead
  spawns, completions, and events.
- After every mutation we re-emit two derived views the rest of the workflow
  already reads:
    * `.beads/workflow/state.json` — the same shape `swarm-epic` writes today,
      so other sessions and tooling don't see a regression.
    * `.beads/workflow/STATE.md` — human-readable summary.

The `runner` field in state.json is new (active flag + pid + mode) so the
session-driven flow can detect that harbor is in charge of an epic and stay
out of the way.
"""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

WORKFLOW_DIRNAME = ".beads/workflow"
DB_FILENAME = "harbor.db"
STATE_JSON_FILENAME = "state.json"
STATE_MD_FILENAME = "STATE.md"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id      TEXT PRIMARY KEY,
    mode        TEXT NOT NULL,
    epic_id     TEXT,
    pid         INTEGER,
    started_at  TEXT NOT NULL,
    ended_at    TEXT,
    status      TEXT NOT NULL DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS bead_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT NOT NULL REFERENCES runs(run_id),
    bead_id         TEXT NOT NULL,
    profile         TEXT NOT NULL,
    model           TEXT,
    effort          TEXT,
    window_name     TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'spawning',
    started_at      TEXT NOT NULL,
    ended_at        TEXT,
    exit_code       INTEGER,
    sentinel_status TEXT,
    blocker_class   TEXT
);

CREATE INDEX IF NOT EXISTS idx_bead_runs_run ON bead_runs(run_id);
CREATE INDEX IF NOT EXISTS idx_bead_runs_status ON bead_runs(status);

CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT NOT NULL REFERENCES runs(run_id),
    bead_id     TEXT,
    ts          TEXT NOT NULL,
    type        TEXT NOT NULL,
    payload     TEXT
);

CREATE INDEX IF NOT EXISTS idx_events_run ON events(run_id);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


@dataclass(frozen=True)
class WorkerSnapshot:
    bead_id: str
    profile: str
    model: str
    effort: str
    window_name: str
    status: str
    started_at: str


class StateStore:
    """Wraps a sqlite3 connection plus the derived state.json / STATE.md writers."""

    def __init__(self, repo_root: str | os.PathLike[str]):
        self.repo_root = Path(repo_root).resolve()
        self.workflow_dir = self.repo_root / WORKFLOW_DIRNAME
        self.workflow_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.workflow_dir / DB_FILENAME
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        with closing(self._conn.cursor()) as cur:
            cur.executescript(_SCHEMA)
        self._conn.commit()

    # ---- run lifecycle ----

    def start_run(self, *, mode: str, epic_id: str | None, pid: int | None = None) -> str:
        if mode not in {"single", "epic"}:
            raise ValueError(f"mode must be 'single' or 'epic', got {mode!r}")
        run_id = uuid.uuid4().hex[:12]
        now = _now()
        self._conn.execute(
            "INSERT INTO runs (run_id, mode, epic_id, pid, started_at, status) "
            "VALUES (?, ?, ?, ?, ?, 'active')",
            (run_id, mode, epic_id, pid if pid is not None else os.getpid(), now),
        )
        self._conn.commit()
        self.record_event(run_id=run_id, type="run_started", payload={"mode": mode, "epic_id": epic_id})
        return run_id

    def end_run(self, run_id: str, *, status: str = "finished") -> None:
        if status not in {"finished", "aborted"}:
            raise ValueError("status must be 'finished' or 'aborted'")
        self._conn.execute(
            "UPDATE runs SET ended_at = ?, status = ? WHERE run_id = ?",
            (_now(), status, run_id),
        )
        self._conn.commit()
        self.record_event(run_id=run_id, type="run_ended", payload={"status": status})
        self.write_state_files()

    # ---- bead lifecycle ----

    def record_bead_start(
        self,
        *,
        run_id: str,
        bead_id: str,
        profile: str,
        model: str,
        effort: str,
        window_name: str,
    ) -> int:
        cur = self._conn.execute(
            "INSERT INTO bead_runs "
            "(run_id, bead_id, profile, model, effort, window_name, status, started_at) "
            "VALUES (?, ?, ?, ?, ?, ?, 'running', ?)",
            (run_id, bead_id, profile, model, effort, window_name, _now()),
        )
        self._conn.commit()
        bead_run_id = int(cur.lastrowid)
        self.record_event(
            run_id=run_id,
            bead_id=bead_id,
            type="bead_started",
            payload={"profile": profile, "window_name": window_name},
        )
        self.write_state_files()
        return bead_run_id

    def record_bead_finish(
        self,
        *,
        run_id: str,
        bead_id: str,
        exit_code: int,
        sentinel_status: str | None,
        blocker_class: str | None,
    ) -> None:
        final_status = "finished" if (sentinel_status == "ok" and exit_code == 0) else "failed"
        self._conn.execute(
            "UPDATE bead_runs SET ended_at = ?, exit_code = ?, sentinel_status = ?, "
            "blocker_class = ?, status = ? "
            "WHERE run_id = ? AND bead_id = ? AND ended_at IS NULL",
            (_now(), exit_code, sentinel_status, blocker_class, final_status, run_id, bead_id),
        )
        self._conn.commit()
        self.record_event(
            run_id=run_id,
            bead_id=bead_id,
            type="bead_finished",
            payload={
                "exit_code": exit_code,
                "sentinel_status": sentinel_status,
                "blocker_class": blocker_class,
            },
        )
        self.write_state_files()

    # ---- events ----

    def record_event(
        self,
        *,
        run_id: str,
        type: str,
        bead_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        self._conn.execute(
            "INSERT INTO events (run_id, bead_id, ts, type, payload) VALUES (?, ?, ?, ?, ?)",
            (run_id, bead_id, _now(), type, json.dumps(payload or {})),
        )
        self._conn.commit()

    # ---- queries ----

    def active_run(self) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM runs WHERE status = 'active' ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None

    def active_workers(self, run_id: str) -> list[WorkerSnapshot]:
        rows = self._conn.execute(
            "SELECT * FROM bead_runs WHERE run_id = ? AND status = 'running' "
            "ORDER BY started_at",
            (run_id,),
        ).fetchall()
        return [
            WorkerSnapshot(
                bead_id=r["bead_id"],
                profile=r["profile"],
                model=r["model"] or "",
                effort=r["effort"] or "",
                window_name=r["window_name"],
                status=r["status"],
                started_at=r["started_at"],
            )
            for r in rows
        ]

    def recent_blockers(self, run_id: str, limit: int = 10) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT bead_id, blocker_class, ended_at FROM bead_runs "
            "WHERE run_id = ? AND status = 'failed' "
            "ORDER BY ended_at DESC LIMIT ?",
            (run_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    # ---- derived files ----

    def snapshot(self) -> dict[str, Any]:
        run = self.active_run()
        if not run:
            return {
                "version": 1,
                "mode": "idle",
                "epic_id": None,
                "coordinator": None,
                "agent_mail": {"status": "unknown", "last_error": None},
                "workers": [],
                "assignments": [],
                "reservations": [],
                "blockers": [],
                "last_action": None,
                "next_action": "Start `harbor run-bead` or `harbor run-epic`.",
                "runner": {"active": False, "pid": None, "mode": "idle"},
            }

        run_id = run["run_id"]
        workers = self.active_workers(run_id)
        blockers = self.recent_blockers(run_id)
        return {
            "version": 1,
            "mode": "swarm" if run["mode"] == "epic" else "single",
            "epic_id": run["epic_id"],
            "coordinator": f"harbor/{run['pid']}" if run["pid"] else "harbor",
            "agent_mail": {"status": "managed-by-harbor", "last_error": None},
            "workers": [
                {
                    "bead_id": w.bead_id,
                    "profile": w.profile,
                    "model": w.model,
                    "effort": w.effort,
                    "window_name": w.window_name,
                    "status": w.status,
                    "started_at": w.started_at,
                }
                for w in workers
            ],
            # Harbor doesn't model `assignments` separately — workers ARE the assignments.
            "assignments": [{"bead_id": w.bead_id, "worker": w.window_name} for w in workers],
            # Reservations are written by harbor.mail directly into Agent Mail's store; we
            # don't duplicate them here. Left empty so the schema stays compatible.
            "reservations": [],
            "blockers": [
                {"bead_id": b["bead_id"], "classification": b["blocker_class"], "at": b["ended_at"]}
                for b in blockers
                if b["blocker_class"]
            ],
            "last_action": None,
            "next_action": None,
            "runner": {
                "active": True,
                "pid": run["pid"],
                "mode": run["mode"],
            },
        }

    def write_state_files(self) -> None:
        snap = self.snapshot()
        self._write_json(self.workflow_dir / STATE_JSON_FILENAME, snap)
        self._write_md(self.workflow_dir / STATE_MD_FILENAME, snap)

    @staticmethod
    def _write_json(path: Path, data: dict[str, Any]) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        tmp.replace(path)

    @staticmethod
    def _write_md(path: Path, snap: dict[str, Any]) -> None:
        lines: list[str] = ["# Workflow State", "", "This file is maintained by `harbor`.", "", "## Status", ""]
        lines.append(f"- Mode: `{snap['mode']}`")
        lines.append(f"- Epic: `{snap['epic_id'] or 'none'}`")
        lines.append(f"- Coordinator: `{snap['coordinator'] or 'none'}`")
        lines.append(f"- Agent Mail: `{snap['agent_mail']['status']}`")
        lines.append("")
        lines.append("## Workers")
        lines.append("")
        if snap["workers"]:
            for w in snap["workers"]:
                lines.append(
                    f"- `{w['bead_id']}` — profile=`{w['profile']}` model=`{w['model']}` "
                    f"effort=`{w['effort']}` window=`{w['window_name']}`"
                )
        else:
            lines.append("- None")
        lines.append("")
        lines.append("## Blockers")
        lines.append("")
        if snap["blockers"]:
            for b in snap["blockers"]:
                lines.append(f"- `{b['bead_id']}` — {b['classification']} ({b['at']})")
        else:
            lines.append("- None")
        lines.append("")
        lines.append("## Next Action")
        lines.append("")
        lines.append(f"- {snap.get('next_action') or 'Continue current run.'}")
        lines.append("")
        path.write_text("\n".join(lines), encoding="utf-8")

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "StateStore":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
