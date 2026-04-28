# Windows Setup

## Install `br`

Recommended:

```powershell
irm https://raw.githubusercontent.com/steveyegge/beads/main/install.ps1 | iex
```

Verify:

```powershell
br version
```

## Install Python

The Agent Mail wrappers and workflow helpers use Python. Ensure either `py`, `python`, or `python3` is on `PATH`.

Verify:

```powershell
py -3 --version
```

## Per-Repo Setup

```powershell
pwsh -File .\scripts\windows\bootstrap-new-repo.ps1 -RepoPath D:\path\to\repo -Prefix yourprefix
```

The bootstrap script initializes git if needed, runs `br init --prefix yourprefix --no-db`, installs Codex integration, and scaffolds the shared workflow files.

For the full stage-1 then stage-2 adoption flow, see [SETUP-NEW-REPO.md](SETUP-NEW-REPO.md).

## Migrate an Existing `br` Repo To `bd`

```powershell
pwsh -File .\scripts\windows\migrate-downstream-to-bd.ps1 -RepoPath D:\path\to\repo
```
