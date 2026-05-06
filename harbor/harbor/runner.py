"""harbor-bead-runner: the wrapper that runs INSIDE a tmux pane for one bead.

The harbor daemon (or `harbor run-bead`) launches this entry point inside a
tmux window. It:

1. Loads the bead contract from `br show`.
2. Loads the chosen agent profile from `harbor.yml` (or built-ins).
3. Renders a worker prompt and spawns the agent CLI with that prompt on stdin.
   stdout is teed: written to the pane (so a user attaching with
   `tmux -L harbor attach -t ...` sees live output) AND captured in memory so
   we can scan for the `HARBOR-DONE: <id> ...` sentinel after the agent exits.
4. POSTs `{bead_id, exit_code, sentinel, last_output}` to the harbor daemon at
   http://127.0.0.1:8765/_internal/finished. If unreachable, writes a fallback
   file at `.beads/workflow/runner-finished/<bead-id>.json` for the daemon to
   pick up later.
5. Leaves the pane alive showing the final output so the user can inspect it
   before the daemon kills the window.

The pipe-tee approach works whether or not we're actually inside tmux — useful
for unit tests and for running outside tmux during dev.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

from .agent import AgentProfile, load_config
from .beads import Beads
from .prompt import parse_sentinel, render_worker_prompt

DEFAULT_DAEMON_URL = "http://127.0.0.1:8765"
FALLBACK_DIR = Path(".beads/workflow/runner-finished")
LAST_OUTPUT_LINES = 30


def _spawn_agent(profile: AgentProfile, model: str | None, effort: str | None, prompt: str) -> tuple[int, str]:
    """Run the agent CLI with `prompt` on stdin, tee stdout to ours, return (exit_code, captured_output)."""
    argv = profile.render_argv(model=model, effort=effort)
    env = {**os.environ, **(profile.env or {})}

    proc = subprocess.Popen(
        argv,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
        text=True,
        env=env,
    )

    # Send the prompt and close stdin so the agent knows input is done.
    assert proc.stdin is not None
    try:
        proc.stdin.write(prompt)
        proc.stdin.flush()
    finally:
        proc.stdin.close()

    captured: list[str] = []

    def _drain() -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            captured.append(line)

    t = threading.Thread(target=_drain, daemon=True)
    t.start()
    proc.wait()
    t.join(timeout=5.0)
    return proc.returncode, "".join(captured)


def _notify_daemon(daemon_url: str, payload: dict[str, Any]) -> bool:
    """POST to the daemon. Returns True on success, False if unreachable."""
    try:
        import httpx  # local import keeps cold-start fast for the no-daemon path
    except ImportError:
        return False
    try:
        resp = httpx.post(f"{daemon_url}/_internal/finished", json=payload, timeout=5.0)
        return resp.status_code < 400
    except Exception:
        return False


def _write_fallback(repo_root: Path, payload: dict[str, Any]) -> Path:
    target_dir = repo_root / FALLBACK_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    p = target_dir / f"{payload['bead_id']}.json"
    p.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return p


def _last_lines(text: str, n: int) -> str:
    lines = text.splitlines()
    return "\n".join(lines[-n:])


def _print_attach_hint(bead_id: str) -> None:
    """Echo a cue to the pane so a human attaching after agent exit sees what just ran."""
    pane = os.environ.get("TMUX_PANE", "")
    server = os.environ.get("TMUX", "")
    print()
    print(f"--- harbor-bead-runner finished {bead_id} ---")
    if pane:
        print(f"(tmux pane: {pane}, server: {server or '<default>'})")
    print("Pane is left open for inspection. Daemon may close it after verify.")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="harbor-bead-runner",
        description="Run one bead inside a tmux pane: render prompt, exec agent, "
        "emit HARBOR-DONE sentinel, notify daemon.",
    )
    p.add_argument("bead_id")
    p.add_argument("--profile", default=None, help="Agent profile from harbor.yml.")
    p.add_argument("--model", default=None, help="Override model.")
    p.add_argument("--effort", default=None, help="Override reasoning effort.")
    p.add_argument("--daemon-url", default=DEFAULT_DAEMON_URL)
    p.add_argument(
        "--repo-root",
        default=str(Path.cwd()),
        help="Repository root (defaults to cwd; daemon usually launches the pane in repo root).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Render the prompt and exit without running an agent (for testing).",
    )
    args = p.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()

    # 1. Load bead contract
    beads = Beads()
    bead = beads.show(args.bead_id)

    # 2. Load profile
    cfg = load_config()
    profile = cfg.get(args.profile)

    # 3. Render prompt
    prompt = render_worker_prompt(bead)

    print(f"[harbor-bead-runner] bead={args.bead_id} profile={profile.name}")
    print(f"[harbor-bead-runner] argv={shlex.join(profile.render_argv(model=args.model, effort=args.effort))}")
    print("[harbor-bead-runner] --- prompt preview (first 12 lines) ---")
    for line in prompt.splitlines()[:12]:
        print(f"  {line}")
    print("[harbor-bead-runner] --- end preview ---\n")

    if args.dry_run:
        print("[harbor-bead-runner] --dry-run: not spawning agent")
        return 0

    # 4. Run the agent
    exit_code, output = _spawn_agent(profile, args.model, args.effort, prompt)

    # 5. Parse sentinel
    sent = parse_sentinel(output, args.bead_id)
    if sent is None:
        sentinel_status = None
        classification = None
    else:
        sentinel_status, classification = sent

    # 6. Notify daemon (or write fallback)
    payload = {
        "bead_id": args.bead_id,
        "exit_code": exit_code,
        "sentinel_status": sentinel_status,
        "blocker_class": classification,
        "last_output": _last_lines(output, LAST_OUTPUT_LINES),
        "profile": profile.name,
        "model": args.model or profile.model,
        "effort": args.effort or profile.effort,
    }
    delivered = _notify_daemon(args.daemon_url, payload)
    if not delivered:
        fallback = _write_fallback(repo_root, payload)
        print(f"[harbor-bead-runner] daemon unreachable; wrote fallback at {fallback}")
    else:
        print(f"[harbor-bead-runner] notified daemon at {args.daemon_url}")

    _print_attach_hint(args.bead_id)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
