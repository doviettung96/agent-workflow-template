#!/usr/bin/env python3
"""Route project execution through the configured local or SSH runtime target."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / ".beads" / "workflow" / "runtime-target.json"
DEFAULT_CONFIG = {
    "version": 1,
    "mode": "local",
    "ssh_host": None,
    "remote_platform": None,
    "remote_workdir": None,
    "sync_strategy": None,
}
EXCLUDE_DIRS = {
    ".git",
    ".beads",
    ".claude",
    ".codex",
    ".venv",
    "node_modules",
    "__pycache__",
}
EXCLUDE_FILES = {
    ".DS_Store",
    "Thumbs.db",
}


class ConfigError(RuntimeError):
    """Raised when the runtime-target configuration is invalid."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    status_parser = subparsers.add_parser("status", help="Show the resolved runtime target")
    status_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    configure_parser = subparsers.add_parser("configure", help="Create or update runtime-target.json")
    configure_parser.add_argument("--mode", choices=("local", "ssh"))
    configure_parser.add_argument("--ssh-host")
    configure_parser.add_argument("--remote-platform", choices=("posix", "windows"))
    configure_parser.add_argument("--remote-workdir")
    configure_parser.add_argument("--sync-strategy", choices=("rsync", "archive"))
    configure_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    run_parser = subparsers.add_parser("run", help="Run one project command through the selected runtime")
    run_parser.add_argument(
        "command_args",
        nargs=argparse.REMAINDER,
        help="Pass the command after `--`, for example: run -- pytest -q",
    )

    return parser.parse_args()


def load_raw_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return dict(DEFAULT_CONFIG)

    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Failed to parse {CONFIG_PATH}: {exc}") from exc

    if not isinstance(data, dict):
        raise ConfigError(f"{CONFIG_PATH} must contain a JSON object")

    merged = dict(DEFAULT_CONFIG)
    merged.update(data)
    return merged


def validate_config(config: dict[str, Any]) -> dict[str, Any]:
    mode = config.get("mode") or "local"
    if mode not in {"local", "ssh"}:
        raise ConfigError("runtime-target mode must be `local` or `ssh`")

    remote_platform = config.get("remote_platform")
    sync_strategy = config.get("sync_strategy")
    resolved = dict(config)
    resolved["mode"] = mode

    if mode == "local":
        resolved["remote_platform"] = remote_platform
        resolved["sync_strategy"] = sync_strategy or "local"
        return resolved

    ssh_host = (config.get("ssh_host") or "").strip()
    remote_workdir = (config.get("remote_workdir") or "").strip()
    if not ssh_host:
        raise ConfigError("runtime-target ssh mode requires `ssh_host`")
    if remote_platform not in {"posix", "windows"}:
        raise ConfigError("runtime-target ssh mode requires `remote_platform` set to `posix` or `windows`")
    if not remote_workdir:
        raise ConfigError("runtime-target ssh mode requires `remote_workdir`")
    if sync_strategy is None:
        sync_strategy = "rsync" if remote_platform == "posix" else "archive"
    if sync_strategy not in {"rsync", "archive"}:
        raise ConfigError("runtime-target sync_strategy must be `rsync` or `archive`")

    resolved["ssh_host"] = ssh_host
    resolved["remote_platform"] = remote_platform
    resolved["remote_workdir"] = remote_workdir
    resolved["sync_strategy"] = sync_strategy
    return resolved


def get_resolved_config() -> dict[str, Any]:
    raw = load_raw_config()
    resolved = validate_config(raw)
    resolved["config_path"] = str(CONFIG_PATH)
    resolved["config_exists"] = CONFIG_PATH.exists()
    return resolved


def print_status(config: dict[str, Any], *, as_json: bool) -> int:
    if as_json:
        json.dump(config, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    print(f"Repo root: {REPO_ROOT}")
    print(f"Config path: {CONFIG_PATH}")
    print(f"Config exists: {'yes' if config['config_exists'] else 'no'}")
    print(f"Mode: {config['mode']}")
    if config["mode"] == "ssh":
        print(f"SSH host: {config['ssh_host']}")
        print(f"Remote platform: {config['remote_platform']}")
        print(f"Remote workdir: {config['remote_workdir']}")
        print(f"Sync strategy: {config['sync_strategy']}")
    else:
        print("Remote target: local default")
    return 0


def write_config(config: dict[str, Any]) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")


def configure_runtime(args: argparse.Namespace) -> int:
    existing = load_raw_config()
    updated = dict(existing)

    for key in ("mode", "ssh_host", "remote_platform", "remote_workdir", "sync_strategy"):
        value = getattr(args, key.replace("-", "_"), None)
        if value is not None:
            updated[key] = value

    validated = validate_config(updated)
    persisted = {
        "version": updated.get("version", 1),
        "mode": validated["mode"],
        "ssh_host": validated.get("ssh_host"),
        "remote_platform": validated.get("remote_platform"),
        "remote_workdir": validated.get("remote_workdir"),
        "sync_strategy": validated.get("sync_strategy"),
    }
    write_config(persisted)
    validated["config_path"] = str(CONFIG_PATH)
    validated["config_exists"] = True
    return print_status(validated, as_json=args.json)


def should_exclude(path: Path) -> bool:
    relative_parts = path.relative_to(REPO_ROOT).parts
    if any(part in EXCLUDE_DIRS for part in relative_parts):
        return True
    if path.name in EXCLUDE_FILES:
        return True
    return False


def run_local(command: str) -> int:
    result = subprocess.run(command, cwd=REPO_ROOT, shell=True, check=False)
    return result.returncode


def check_command(name: str) -> str:
    resolved = shutil.which(name)
    if not resolved:
        raise ConfigError(f"Required command not found: {name}")
    return resolved


def run_checked(args: list[str], *, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=REPO_ROOT,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )


def ssh_run(host: str, remote_command: str) -> subprocess.CompletedProcess[str]:
    check_command("ssh")
    return subprocess.run(
        ["ssh", host, remote_command],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def ensure_remote_directory(config: dict[str, Any]) -> None:
    remote_workdir = config["remote_workdir"]
    if config["remote_platform"] == "posix":
        command = f"mkdir -p {posix_shell_path(remote_workdir)}"
    else:
        quoted = ps_single_quote(remote_workdir)
        command = (
            "powershell -NoProfile -NonInteractive -Command "
            f"\"New-Item -ItemType Directory -Force -Path {quoted} | Out-Null\""
        )
    result = ssh_run(config["ssh_host"], command)
    if result.returncode != 0:
        raise ConfigError(result.stderr.strip() or "Failed to create the remote workdir")


def sync_with_rsync(config: dict[str, Any]) -> None:
    rsync = check_command("rsync")
    destination = f"{config['ssh_host']}:{config['remote_workdir'].rstrip('/')}/"
    args = [
        rsync,
        "-az",
        "--delete",
        "--exclude=.git/",
        "--exclude=.beads/",
        "--exclude=.claude/",
        "--exclude=.codex/",
        "--exclude=.venv/",
        "--exclude=node_modules/",
        "--exclude=__pycache__/",
        f"{REPO_ROOT}{os.sep}",
        destination,
    ]
    result = run_checked(args)
    if result.returncode != 0:
        raise ConfigError(result.stderr.strip() or "rsync failed")


def build_archive(archive_path: Path) -> None:
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as handle:
        for path in REPO_ROOT.rglob("*"):
            if not path.is_file():
                continue
            if should_exclude(path):
                continue
            handle.write(path, path.relative_to(REPO_ROOT))


def ps_single_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def posix_shell_path(value: str) -> str:
    if value == "~":
        return "$HOME"
    if value.startswith("~/"):
        return "$HOME/" + shlex.quote(value[2:])
    return shlex.quote(value)


def sync_with_archive(config: dict[str, Any]) -> None:
    check_command("ssh")
    scp = check_command("scp")
    ensure_remote_directory(config)

    with tempfile.TemporaryDirectory(prefix="target-runtime-") as tmp_dir:
        archive_path = Path(tmp_dir) / "repo-sync.zip"
        build_archive(archive_path)
        remote_base = config["remote_workdir"].rstrip("/\\")
        remote_archive = f"{config['ssh_host']}:{remote_base}/repo-sync.zip"
        copy_result = run_checked([scp, str(archive_path), remote_archive])
        if copy_result.returncode != 0:
            raise ConfigError(copy_result.stderr.strip() or "scp failed")

        remote_workdir = config["remote_workdir"]
        if config["remote_platform"] == "windows":
            remote_command = (
                "powershell -NoProfile -NonInteractive -Command "
                "\""
                f"$archive = Join-Path {ps_single_quote(remote_workdir)} 'repo-sync.zip'; "
                f"if (Test-Path {ps_single_quote(remote_workdir)}) {{ "
                f"Get-ChildItem -LiteralPath {ps_single_quote(remote_workdir)} -Force | "
                "Where-Object { $_.Name -ne 'repo-sync.zip' } | Remove-Item -Recurse -Force }; "
                "Expand-Archive -LiteralPath $archive -DestinationPath "
                f"{ps_single_quote(remote_workdir)} -Force; "
                "Remove-Item -LiteralPath $archive -Force"
                "\""
            )
        else:
            quoted_workdir = posix_shell_path(remote_workdir)
            remote_command = (
                "PYTHON_BIN=''\n"
                "if command -v python3 >/dev/null 2>&1; then PYTHON_BIN=python3; "
                "elif command -v python >/dev/null 2>&1; then PYTHON_BIN=python; "
                "else echo 'python or python3 is required for archive sync' >&2; exit 1; fi\n"
                "\"${PYTHON_BIN}\" - <<'PY'\n"
                "import pathlib\n"
                "import shutil\n"
                "import zipfile\n"
                "root = pathlib.Path("
                + repr(remote_workdir)
                + ").expanduser()\n"
                "archive = root / 'repo-sync.zip'\n"
                "root.mkdir(parents=True, exist_ok=True)\n"
                "for child in list(root.iterdir()):\n"
                "    if child.name == 'repo-sync.zip':\n"
                "        continue\n"
                "    if child.is_dir():\n"
                "        shutil.rmtree(child)\n"
                "    else:\n"
                "        child.unlink()\n"
                "with zipfile.ZipFile(archive) as handle:\n"
                "    handle.extractall(root)\n"
                "archive.unlink()\n"
                "PY"
            )
            remote_command = f"cd {quoted_workdir} && {remote_command}"
        extract_result = ssh_run(config["ssh_host"], remote_command)
        if extract_result.returncode != 0:
            raise ConfigError(extract_result.stderr.strip() or "Remote archive extraction failed")


def sync_repo(config: dict[str, Any]) -> None:
    ensure_remote_directory(config)
    strategy = config["sync_strategy"]
    if strategy == "rsync":
        sync_with_rsync(config)
        return
    if strategy == "archive":
        sync_with_archive(config)
        return
    raise ConfigError(f"Unsupported sync strategy: {strategy}")


def build_remote_command(config: dict[str, Any], command: str) -> str:
    remote_workdir = config["remote_workdir"]
    if config["remote_platform"] == "posix":
        wrapped = f"cd {posix_shell_path(remote_workdir)} && {command}"
        return "bash -lc " + shlex.quote(wrapped)

    command_text = f"Set-Location -LiteralPath {ps_single_quote(remote_workdir)}; {command}"
    return (
        "powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command "
        + ps_single_quote(command_text)
    )


def run_remote(config: dict[str, Any], command: str) -> int:
    sync_repo(config)
    remote_command = build_remote_command(config, command)
    result = subprocess.run(["ssh", config["ssh_host"], remote_command], cwd=REPO_ROOT, check=False)
    return result.returncode


def run_command(args: argparse.Namespace) -> int:
    command_args = list(args.command_args)
    if command_args and command_args[0] == "--":
        command_args = command_args[1:]
    if not command_args:
        raise ConfigError("No command provided. Use: target_runtime.py run -- <command>")

    command = " ".join(command_args)
    config = get_resolved_config()
    if config["mode"] == "local":
        return run_local(command)
    return run_remote(config, command)


def main() -> int:
    args = parse_args()
    try:
        if args.command == "status":
            return print_status(get_resolved_config(), as_json=args.json)
        if args.command == "configure":
            return configure_runtime(args)
        if args.command == "run":
            return run_command(args)
        raise ConfigError(f"Unsupported command: {args.command}")
    except ConfigError as exc:
        sys.stderr.write(f"target-runtime: {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
