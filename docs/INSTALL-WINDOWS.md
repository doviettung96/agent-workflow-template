# Windows Setup

## Install `bd`

Recommended:

```powershell
irm https://raw.githubusercontent.com/steveyegge/beads/main/install.ps1 | iex
```

Verify:

```powershell
bd version
```

## Install `dolt`

Install Dolt on the machine and verify:

```powershell
dolt version
```

## Install Python

The Agent Mail wrappers and workflow helpers use Python. Ensure either `py`, `python`, or `python3` is on `PATH`.

Verify:

```powershell
py -3 --version
```

## Per-Repo Setup

In each new repo:

```powershell
bd init -p yourprefix --server --non-interactive --role maintainer --skip-agents --skip-hooks
bd setup codex
bd setup claude --check
```

Then scaffold the workflow files:

```powershell
pwsh -File .\scripts\windows\bootstrap-new-repo.ps1 -RepoPath D:\path\to\repo -Prefix yourprefix
```

## Migrate an Existing `br` Repo

```powershell
pwsh -File .\scripts\windows\migrate-downstream-to-bd.ps1 -RepoPath D:\path\to\repo
```
