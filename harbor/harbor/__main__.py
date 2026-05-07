from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _not_implemented(name: str) -> int:
    print(f"harbor: '{name}' is not implemented yet (Phase 1 in progress)", file=sys.stderr)
    return 2


def cmd_run_bead(args: argparse.Namespace) -> int:
    from .orchestrator import RunBeadOptions, run_bead

    opts = RunBeadOptions(
        bead_id=args.bead_id,
        profile=args.profile,
        model=args.model,
        effort=args.effort,
        repo_root=Path(args.repo_root or Path.cwd()).resolve(),
        timeout_s=args.timeout,
    )
    result = run_bead(opts)
    print()
    print(result.render_summary())
    return 0 if result.closed else 1


def cmd_run_epic(args: argparse.Namespace) -> int:
    from .epic import RunEpicOptions, run_epic

    opts = RunEpicOptions(
        epic_id=args.epic_id,
        profile=args.profile,
        model=args.model,
        effort=args.effort,
        repo_root=Path(args.repo_root or Path.cwd()).resolve(),
        max_concurrency=args.max_concurrency,
        interval_s=args.interval,
        max_iterations=args.max_iterations,
        bead_timeout_s=args.bead_timeout,
    )
    result = run_epic(opts)
    print()
    print(result.render_summary())
    if result.exit_reason == "lock_held":
        return 2
    return 0 if not result.failed else 1


def cmd_daemon(args: argparse.Namespace) -> int:
    import uvicorn
    from .webui.server import create_app

    repo_root = Path(args.repo_root or Path.cwd()).resolve()
    app = create_app(repo_root)
    print(f"harbor daemon: serving http://{args.host}:{args.port}/ for repo {repo_root}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    return _not_implemented("status")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="harbor",
        description="Tmux-pane-per-bead runner. Drives a beads epic to completion without "
        "consuming the chat session's context window.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    rb = sub.add_parser("run-bead", help="Run a single bead in a tmux pane.")
    rb.add_argument("bead_id")
    rb.add_argument("--profile", default=None, help="Agent profile from harbor.yml.")
    rb.add_argument("--model", default=None, help="Override model (else profile default).")
    rb.add_argument("--effort", default=None, help="Override reasoning effort.")
    rb.add_argument("--repo-root", default=None, help="Repo root (default: cwd).")
    rb.add_argument("--timeout", type=int, default=3600, help="Seconds to wait for runner (default 3600).")
    rb.set_defaults(func=cmd_run_bead)

    re = sub.add_parser("run-epic", help="Run all ready descendants of an epic, polling for new ones.")
    re.add_argument("epic_id")
    re.add_argument("--profile", default=None, help="Agent profile from harbor.yml.")
    re.add_argument("--model", default=None, help="Override model (else profile default).")
    re.add_argument("--effort", default=None, help="Override reasoning effort.")
    re.add_argument("--repo-root", default=None, help="Repo root (default: cwd).")
    re.add_argument("--max-concurrency", type=int, default=3, help="Max concurrent run_bead workers (default 3, 1 = sequential).")
    re.add_argument("--interval", type=float, default=30.0, help="Poll interval seconds (timeout per outer loop tick).")
    re.add_argument("--max-iterations", type=int, default=None, help="Stop after N tick iterations (default: unlimited).")
    re.add_argument("--bead-timeout", type=int, default=60 * 60 * 6, help="Per-bead timeout seconds (default 6h).")
    re.set_defaults(func=cmd_run_epic)

    d = sub.add_parser("daemon", help="Run the long-lived orchestrator + webview server.")
    d.add_argument("--host", default="127.0.0.1")
    d.add_argument("--port", type=int, default=8765)
    d.add_argument("--repo-root", default=None, help="Repo root (default: cwd).")
    d.set_defaults(func=cmd_daemon)

    st = sub.add_parser("status", help="Print current runner state.")
    st.set_defaults(func=cmd_status)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
