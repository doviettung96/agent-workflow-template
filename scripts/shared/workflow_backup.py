"""Shared helpers for downstream workflow backup mirrors."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path


IGNORE_BLOCK_START = "# BEGIN TEMPLATE AGENT WORKFLOW LOCAL-ONLY"
IGNORE_BLOCK_END = "# END TEMPLATE AGENT WORKFLOW LOCAL-ONLY"
LEGACY_IGNORE_HEADER = "# Local agent workflow assets"

ROOT_FILES = (
    "AGENTS.md",
    "CLAUDE.md",
    "BEADS_WORKFLOW.md",
)

BEADS_FILES = (
    ".beads/.gitignore",
    ".beads/README.md",
    ".beads/PRIME.md",
)

DOC_FILES = (
    "docs/WORKFLOW_NOTES.md",
    "docs/TROUBLESHOOTING.md",
)

RUNTIME_LOCAL_ONLY_FILES = (
    ".beads/config.yaml",
    ".beads/metadata.json",
    ".claude/settings.json",
)

MANAGED_DIRS = (
    "docs/plans",
    ".codex/skills",
    ".claude/skills",
)

SCRIPT_FILES = (
    "scripts/posix/agent-mail.sh",
    "scripts/posix/start-epic-worktree.sh",
    "scripts/posix/sync-workflow-backup.sh",
    "scripts/posix/workflow-status.sh",
    "scripts/shared/agent_mail.py",
    "scripts/shared/harness.py",
    "scripts/shared/manage_instructions.py",
    "scripts/shared/start_epic_worktree.py",
    "scripts/shared/sync_workflow_backup.py",
    "scripts/shared/target_runtime.py",
    "scripts/shared/workflow_backup.py",
    "scripts/windows/agent-mail.ps1",
    "scripts/windows/start-epic-worktree.ps1",
    "scripts/windows/sync-workflow-backup.ps1",
    "scripts/windows/workflow-status.ps1",
)

OPTIONAL_DIRS = (
    "scripts/shared/harness_backends",
)

LOCAL_STATE_ENTRIES = (
    ".beads/.br_history/",
    ".beads/.sync.lock",
    ".beads/backup/",
    ".beads/config.yaml",
    ".beads/issues.jsonl",
    ".beads/last-touched",
    ".beads/metadata.json",
)

WORKTREE_LOCAL_STATE_FILES = (
    ".beads/config.yaml",
    ".beads/issues.jsonl",
    ".beads/last-touched",
    ".beads/metadata.json",
)

WORKTREE_LOCAL_STATE_DIRS = (
    ".beads/workflow",
)

IGNORE_ENTRIES = (
    *LOCAL_STATE_ENTRIES,
    ".beads/workflow/",
    ".beads/PRIME.md",
    ".beads/.gitignore",
    ".beads/README.md",
    ".codex/skills/",
    ".claude/skills/",
    "AGENTS.md",
    "BEADS_WORKFLOW.md",
    "CLAUDE.md",
    "docs/WORKFLOW_NOTES.md",
    "docs/plans/",
    "docs/TROUBLESHOOTING.md",
    ".beads/config.yaml",
    ".beads/metadata.json",
    ".claude/settings.json",
    "scripts/posix/agent-mail.sh",
    "scripts/posix/start-epic-worktree.sh",
    "scripts/posix/sync-workflow-backup.sh",
    "scripts/posix/workflow-status.sh",
    "scripts/shared/agent_mail.py",
    "scripts/shared/harness.py",
    "scripts/shared/harness_backends/",
    "scripts/shared/manage_instructions.py",
    "scripts/shared/start_epic_worktree.py",
    "scripts/shared/sync_workflow_backup.py",
    "scripts/shared/target_runtime.py",
    "scripts/shared/workflow_backup.py",
    "scripts/windows/agent-mail.ps1",
    "scripts/windows/start-epic-worktree.ps1",
    "scripts/windows/sync-workflow-backup.ps1",
    "scripts/windows/workflow-status.ps1",
)


@dataclass
class SyncResult:
    repo_root: Path
    backup_repo: Path
    project_name: str
    backup_branch: str
    copied: list[str]
    removed: list[str]
    committed: bool
    pushed: bool
    commit_message: str | None


def _run(
    command: list[str],
    *,
    cwd: Path | None = None,
    capture_output: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        check=True,
        text=True,
        capture_output=capture_output,
    )


def git(repo: Path, *args: str, capture_output: bool = True) -> subprocess.CompletedProcess[str]:
    return _run(["git", "-C", str(repo), *args], capture_output=capture_output)


def resolve_repo_root(path: str | Path) -> Path:
    candidate = Path(path).expanduser().resolve()
    try:
        result = git(candidate, "rev-parse", "--show-toplevel")
    except subprocess.CalledProcessError:
        return candidate
    return Path(result.stdout.strip()).resolve()


def resolve_backup_repo(repo_root: Path, override: str | None) -> Path:
    raw = override or os.environ.get("AGENTIC_WORKFLOWS_REPO")
    if raw:
        return Path(raw).expanduser().resolve()
    return (repo_root.parent / "agentic-workflows").resolve()


def collect_managed_files(repo_root: Path) -> list[str]:
    files: set[str] = set()
    for rel in (*ROOT_FILES, *BEADS_FILES, *DOC_FILES, *SCRIPT_FILES):
        path = repo_root / rel
        if path.is_file():
            files.add(rel)
    for rel_dir in (*MANAGED_DIRS, *OPTIONAL_DIRS):
        base = repo_root / rel_dir
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file():
                files.add(path.relative_to(repo_root).as_posix())
    return sorted(files)


def collect_worktree_local_files(repo_root: Path) -> list[str]:
    files: set[str] = set(collect_managed_files(repo_root))
    for rel in WORKTREE_LOCAL_STATE_FILES:
        path = repo_root / rel
        if path.is_file():
            files.add(rel)
    for rel_dir in WORKTREE_LOCAL_STATE_DIRS:
        base = repo_root / rel_dir
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file():
                files.add(path.relative_to(repo_root).as_posix())
    return sorted(files)


def list_tracked_managed_files(repo_root: Path) -> list[str]:
    candidates = collect_managed_files(repo_root)
    if not candidates:
        return []
    result = git(repo_root, "ls-files", "-z", "--", *candidates)
    return [item for item in result.stdout.split("\0") if item]


def collect_runtime_local_only_files(repo_root: Path) -> list[str]:
    files: list[str] = []
    for rel in RUNTIME_LOCAL_ONLY_FILES:
        if (repo_root / rel).is_file():
            files.append(rel)
    return files


def list_tracked_local_only_files(repo_root: Path) -> list[str]:
    candidates = sorted(set(list_tracked_managed_files(repo_root) + collect_runtime_local_only_files(repo_root)))
    if not candidates:
        return []
    result = git(repo_root, "ls-files", "-z", "--", *candidates)
    return [item for item in result.stdout.split("\0") if item]


def _strip_ignore_block(content: str) -> str:
    start = content.find(IGNORE_BLOCK_START)
    end = content.find(IGNORE_BLOCK_END)
    if start == -1 or end == -1 or end < start:
        return content
    end += len(IGNORE_BLOCK_END)
    before = content[:start].rstrip("\r\n")
    after = content[end:].lstrip("\r\n")
    if before and after:
        return before + "\n\n" + after
    return before or after


def _squash_blank_runs(lines: list[str]) -> list[str]:
    squashed: list[str] = []
    blank = False
    for line in lines:
        if line.strip():
            squashed.append(line.rstrip())
            blank = False
            continue
        if not blank:
            squashed.append("")
        blank = True
    while squashed and squashed[0] == "":
        squashed.pop(0)
    while squashed and squashed[-1] == "":
        squashed.pop()
    return squashed


def ensure_ignore_block(repo_root: Path) -> bool:
    target = repo_root / ".gitignore"
    content = target.read_text(encoding="utf-8") if target.exists() else ""
    stripped = _strip_ignore_block(content)

    filtered_lines: list[str] = []
    managed = set(IGNORE_ENTRIES)
    for line in stripped.splitlines():
        raw = line.rstrip("\r")
        if raw == LEGACY_IGNORE_HEADER:
            continue
        if raw in managed:
            continue
        filtered_lines.append(raw)
    filtered_lines = _squash_blank_runs(filtered_lines)

    block_lines = [
        IGNORE_BLOCK_START,
        *IGNORE_ENTRIES,
        IGNORE_BLOCK_END,
    ]

    merged = "\n".join(filtered_lines + ([""] if filtered_lines else []) + block_lines) + "\n"
    if merged == content:
        return False
    target.write_text(merged, encoding="utf-8")
    return True


def _file_bytes(path: Path) -> bytes:
    return path.read_bytes()


def _is_executable(path: Path) -> bool:
    return bool(path.stat().st_mode & stat.S_IXUSR)


def _files_match(src: Path, dst: Path) -> bool:
    if not dst.exists() or not dst.is_file():
        return False
    if src.stat().st_size != dst.stat().st_size:
        return False
    if _is_executable(src) != _is_executable(dst):
        return False
    return _file_bytes(src) == _file_bytes(dst)


def _prune_empty_dirs(start: Path, stop: Path) -> None:
    current = start
    while current != stop and current.exists():
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent


def _require_clean_backup_repo(backup_repo: Path) -> str:
    if not (backup_repo / ".git").exists():
        raise RuntimeError(f"Backup repo is not a git checkout: {backup_repo}")
    try:
        branch = git(backup_repo, "symbolic-ref", "--quiet", "--short", "HEAD").stdout.strip()
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        if "not a symbolic ref" in stderr:
            raise RuntimeError(f"Backup repo is in detached HEAD state: {backup_repo}") from exc
        raise
    status = git(backup_repo, "status", "--short").stdout.strip()
    if status:
        raise RuntimeError(f"Backup repo must be clean before sync: {backup_repo}")
    return branch


def _source_revision(repo_root: Path) -> str:
    try:
        return git(repo_root, "rev-parse", "--short", "HEAD").stdout.strip()
    except subprocess.CalledProcessError:
        return "no-head"


def sync_workflow_backup(
    repo_root: Path,
    backup_repo: Path,
    project_name: str,
    *,
    dry_run: bool = False,
    push: bool = True,
) -> SyncResult:
    repo_root = resolve_repo_root(repo_root)
    backup_repo = backup_repo.expanduser().resolve()
    backup_branch = _require_clean_backup_repo(backup_repo)

    source_files = collect_managed_files(repo_root)
    project_root = backup_repo / project_name
    existing_backup_files = set(collect_managed_files(project_root)) if project_root.exists() else set()
    desired_files = set(source_files)

    copied: list[str] = []
    for rel in source_files:
        src = repo_root / rel
        dst = project_root / rel
        if _files_match(src, dst):
            continue
        copied.append(rel)
        if dry_run:
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    removed = sorted(existing_backup_files - desired_files)
    if not dry_run:
        for rel in removed:
            dst = project_root / rel
            if not dst.exists():
                continue
            dst.unlink()
            _prune_empty_dirs(dst.parent, project_root)

    committed = False
    pushed = False
    commit_message = None

    if not dry_run:
        git(backup_repo, "add", "--all", "--", project_name, capture_output=False)
        status = git(backup_repo, "status", "--short", "--", project_name).stdout.strip()
        if status:
            commit_message = (
                f"workflow-backup({project_name}): sync from "
                f"{repo_root.name}@{_source_revision(repo_root)}"
            )
            git(backup_repo, "commit", "-m", commit_message, capture_output=False)
            committed = True
        if push:
            git(backup_repo, "push", "origin", "HEAD", capture_output=False)
            pushed = True

    return SyncResult(
        repo_root=repo_root,
        backup_repo=backup_repo,
        project_name=project_name,
        backup_branch=backup_branch,
        copied=copied,
        removed=removed,
        committed=committed,
        pushed=pushed,
        commit_message=commit_message,
    )


def remove_managed_files_from_index(repo_root: Path) -> list[str]:
    tracked = list_tracked_local_only_files(repo_root)
    if not tracked:
        return []
    git(repo_root, "rm", "--cached", "--sparse", "-f", "--", *tracked, capture_output=False)
    return tracked


def remove_local_state_files_from_index(repo_root: Path) -> list[str]:
    result = git(repo_root, "ls-files", "-z", "--", *LOCAL_STATE_ENTRIES)
    tracked = [item for item in result.stdout.split("\0") if item]
    if not tracked:
        return []
    git(repo_root, "rm", "--cached", "--sparse", "-f", "--", *tracked, capture_output=False)
    return tracked


def copy_worktree_local_files(source_repo: Path, dest_repo: Path) -> list[str]:
    source_repo = resolve_repo_root(source_repo)
    dest_repo = resolve_repo_root(dest_repo)
    copied: list[str] = []
    for rel in collect_worktree_local_files(source_repo):
        src = source_repo / rel
        dst = dest_repo / rel
        if _files_match(src, dst):
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append(rel)
    return copied
