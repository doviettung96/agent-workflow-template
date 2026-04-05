#!/usr/bin/env python3
"""Attach worktrees to a shared live Beads store under git-common-dir."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


VERSION = 1


class SharedBeadsError(Exception):
    def __init__(self, message: str, *, code: int = 1, details: Any | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def run_git(repo_root: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise SharedBeadsError("git is required for shared-beads", code=2) from exc
    except subprocess.CalledProcessError as exc:
        raise SharedBeadsError(
            f"git {' '.join(args)} failed",
            code=3,
            details={"stdout": exc.stdout.strip(), "stderr": exc.stderr.strip()},
        ) from exc
    return completed.stdout.strip()


def run_br(repo_root: Path, beads_dir: Path, *args: str) -> str:
    env = os.environ.copy()
    env["BEADS_DIR"] = str(beads_dir)
    try:
        completed = subprocess.run(
            ["br", *args],
            cwd=repo_root,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise SharedBeadsError("br is required for shared-beads", code=4) from exc
    except subprocess.CalledProcessError as exc:
        raise SharedBeadsError(
            f"br {' '.join(args)} failed",
            code=5,
            details={"stdout": exc.stdout.strip(), "stderr": exc.stderr.strip()},
        ) from exc
    return completed.stdout.strip()


def resolve_repo_root(repo_hint: Path) -> Path:
    return Path(run_git(repo_hint, "rev-parse", "--show-toplevel")).resolve()


def resolve_git_common_dir(repo_root: Path) -> Path:
    raw = run_git(repo_root, "rev-parse", "--git-common-dir")
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = (repo_root / candidate).resolve()
    return candidate


def resolve_main_repo_root(repo_root: Path, git_common_dir: Path) -> Path:
    if git_common_dir.name == ".git":
        return git_common_dir.parent.resolve()
    return repo_root


def resolve_branch(repo_root: Path) -> str | None:
    completed = subprocess.run(
        ["git", "-C", str(repo_root), "symbolic-ref", "--quiet", "--short", "HEAD"],
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def branch_exists(repo_root: Path, branch_ref: str) -> bool:
    completed = subprocess.run(
        ["git", "-C", str(repo_root), "show-ref", "--verify", "--quiet", branch_ref],
        capture_output=True,
        text=True,
    )
    return completed.returncode == 0


def resolve_default_branch(repo_root: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo_root), "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"],
        capture_output=True,
        text=True,
    )
    if completed.returncode == 0:
        return Path(completed.stdout.strip()).name

    for name in ("main", "master"):
        if branch_exists(repo_root, f"refs/heads/{name}") or branch_exists(repo_root, f"refs/remotes/origin/{name}"):
            return name

    return "main"


def file_hash(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_file(source: Path, destination: Path) -> None:
    ensure_dir(destination.parent)
    shutil.copyfile(source, destination)


def write_text(path: Path, text: str) -> None:
    ensure_dir(path.parent)
    path.write_text(text, encoding="utf-8", newline="\n")


def read_redirect_target(path: Path) -> Path | None:
    if not path.exists():
        return None
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return None
    target = Path(raw)
    if not target.is_absolute():
        target = (path.parent / target).resolve()
    return target.resolve()


def describe_paths(repo_root: Path) -> dict[str, Path]:
    git_common_dir = resolve_git_common_dir(repo_root)
    main_repo_root = resolve_main_repo_root(repo_root, git_common_dir)
    repo_beads_dir = repo_root / ".beads"
    shared_root = main_repo_root.parent / f"{main_repo_root.name}.shared" / "_beads"
    return {
        "repo_root": repo_root,
        "git_common_dir": git_common_dir,
        "main_repo_root": main_repo_root,
        "repo_beads_dir": repo_beads_dir,
        "shared_root": shared_root,
        "repo_snapshot": repo_beads_dir / "issues.jsonl",
        "repo_config": repo_beads_dir / "config.yaml",
        "repo_metadata": repo_beads_dir / "metadata.json",
        "repo_readme": repo_beads_dir / "README.md",
        "repo_redirect": repo_beads_dir / "redirect",
        "shared_issues": shared_root / "issues.jsonl",
        "shared_config": shared_root / "config.yaml",
        "shared_metadata": shared_root / "metadata.json",
        "shared_readme": shared_root / "README.md",
    }


def ensure_repo_beads_dir(repo_beads_dir: Path) -> None:
    if not repo_beads_dir.exists():
        raise SharedBeadsError(
            "Repo is missing .beads; run br init and scaffold the workflow first",
            code=6,
            details={"repo_beads_dir": str(repo_beads_dir)},
        )


def seed_shared_root(paths: dict[str, Path], *, refresh_repo_managed: bool) -> dict[str, bool]:
    ensure_repo_beads_dir(paths["repo_beads_dir"])
    ensure_dir(paths["shared_root"])

    seeded = {"config": False, "metadata": False, "readme": False, "issues": False}

    if refresh_repo_managed or not paths["shared_config"].exists():
        if not paths["repo_config"].exists():
            raise SharedBeadsError(
                "Repo .beads/config.yaml is missing; cannot seed shared live store",
                code=7,
                details={"repo_config": str(paths["repo_config"])},
            )
        copy_file(paths["repo_config"], paths["shared_config"])
        seeded["config"] = True

    if paths["repo_metadata"].exists() and (refresh_repo_managed or not paths["shared_metadata"].exists()):
        copy_file(paths["repo_metadata"], paths["shared_metadata"])
        seeded["metadata"] = True

    if paths["repo_readme"].exists() and (refresh_repo_managed or not paths["shared_readme"].exists()):
        copy_file(paths["repo_readme"], paths["shared_readme"])
        seeded["readme"] = True

    if not paths["shared_issues"].exists():
        if paths["repo_snapshot"].exists():
            copy_file(paths["repo_snapshot"], paths["shared_issues"])
        else:
            write_text(paths["shared_issues"], "")
        seeded["issues"] = True

    return seeded


def ensure_redirect(paths: dict[str, Path]) -> Path:
    ensure_repo_beads_dir(paths["repo_beads_dir"])
    redirect_text = str(paths["shared_root"]) + "\n"
    current_target = read_redirect_target(paths["repo_redirect"])
    if current_target != paths["shared_root"]:
        write_text(paths["repo_redirect"], redirect_text)
    return paths["repo_redirect"]


def build_status_payload(repo_root: Path) -> dict[str, Any]:
    paths = describe_paths(repo_root)
    redirect_target = read_redirect_target(paths["repo_redirect"])
    current_branch = resolve_branch(repo_root)
    default_branch = resolve_default_branch(repo_root)
    shared_hash = file_hash(paths["shared_issues"])
    snapshot_hash = file_hash(paths["repo_snapshot"])

    if shared_hash is None:
        snapshot_state = "shared-live-missing"
    elif snapshot_hash is None:
        snapshot_state = "snapshot-missing"
    elif shared_hash == snapshot_hash:
        snapshot_state = "in-sync"
    else:
        snapshot_state = "drifted"

    payload: dict[str, Any] = {
        "ok": True,
        "version": VERSION,
        "repo_root": str(paths["repo_root"]),
        "main_repo_root": str(paths["main_repo_root"]),
        "git_common_dir": str(paths["git_common_dir"]),
        "current_branch": current_branch,
        "default_branch": default_branch,
        "is_main_checkout": paths["repo_root"] == paths["main_repo_root"],
        "shared_root": str(paths["shared_root"]),
        "shared_exists": paths["shared_root"].exists(),
        "shared_issues_path": str(paths["shared_issues"]),
        "repo_snapshot_path": str(paths["repo_snapshot"]),
        "redirect_path": str(paths["repo_redirect"]),
        "redirect_target": str(redirect_target) if redirect_target else None,
        "attached": redirect_target == paths["shared_root"],
        "snapshot_state": snapshot_state,
        "shared_issues_hash": shared_hash,
        "repo_snapshot_hash": snapshot_hash,
    }

    try:
        payload["br_where"] = run_br(paths["repo_root"], paths["shared_root"], "where")
    except SharedBeadsError:
        payload["br_where"] = None

    return payload


def attach_shared_beads(repo_hint: Path, *, hydrate: bool = True) -> dict[str, Any]:
    repo_root = resolve_repo_root(repo_hint.resolve())
    paths = describe_paths(repo_root)
    refresh_repo_managed = paths["repo_root"] == paths["main_repo_root"] and resolve_branch(repo_root) == resolve_default_branch(repo_root)
    seeded = seed_shared_root(paths, refresh_repo_managed=refresh_repo_managed)
    redirect_path = ensure_redirect(paths)

    if hydrate:
        run_br(repo_root, paths["shared_root"], "sync", "--import-only")

    payload = build_status_payload(repo_root)
    payload.update(
        {
            "action": "attach",
            "redirect_path": str(redirect_path),
            "seeded": seeded,
            "hydrated": hydrate,
            "refreshed_repo_managed_files": refresh_repo_managed,
        }
    )
    return payload


def export_snapshot(repo_hint: Path, *, force: bool = False) -> dict[str, Any]:
    repo_root = resolve_repo_root(repo_hint.resolve())
    payload = attach_shared_beads(repo_root, hydrate=False)
    paths = describe_paths(repo_root)
    current_branch = payload["current_branch"]
    default_branch = payload["default_branch"]

    if not force:
        if paths["repo_root"] != paths["main_repo_root"]:
            raise SharedBeadsError(
                "export-snapshot must run from the main checkout unless --force is used",
                code=8,
                details={"repo_root": str(paths["repo_root"]), "main_repo_root": str(paths["main_repo_root"])},
            )
        if current_branch != default_branch:
            raise SharedBeadsError(
                f"export-snapshot must run on {default_branch} unless --force is used",
                code=9,
                details={"current_branch": current_branch, "default_branch": default_branch},
            )

    run_br(repo_root, paths["shared_root"], "sync", "--flush-only")
    before_hash = file_hash(paths["repo_snapshot"])
    copy_file(paths["shared_issues"], paths["repo_snapshot"])
    after_hash = file_hash(paths["repo_snapshot"])

    result = build_status_payload(repo_root)
    result.update(
        {
            "action": "export-snapshot",
            "changed": before_hash != after_hash,
            "forced": force,
        }
    )
    return result


def command_attach(_parser: argparse.ArgumentParser, args: argparse.Namespace) -> dict[str, Any]:
    return attach_shared_beads(Path(args.repo), hydrate=True)


def command_export_snapshot(_parser: argparse.ArgumentParser, args: argparse.Namespace) -> dict[str, Any]:
    return export_snapshot(Path(args.repo), force=args.force)


def command_status(_parser: argparse.ArgumentParser, args: argparse.Namespace) -> dict[str, Any]:
    repo_root = resolve_repo_root(Path(args.repo).resolve())
    return build_status_payload(repo_root)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage shared live Beads state under git-common-dir")
    parser.add_argument("--repo", default=".", help="Repo root or existing worktree path")
    subparsers = parser.add_subparsers(dest="command", required=True)

    attach = subparsers.add_parser("attach")
    attach.set_defaults(func=command_attach)

    export_snapshot_parser = subparsers.add_parser("export-snapshot")
    export_snapshot_parser.add_argument("--force", action="store_true")
    export_snapshot_parser.set_defaults(func=command_export_snapshot)

    status = subparsers.add_parser("status")
    status.set_defaults(func=command_status)

    return parser


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = args.func(parser, args)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except SharedBeadsError as exc:
        payload = {"ok": False, "error": str(exc)}
        if exc.details is not None:
            payload["details"] = exc.details
        print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
        return exc.code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
