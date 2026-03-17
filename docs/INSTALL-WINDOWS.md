# Windows Setup

## Install Beads

Use the official PowerShell installer:

```powershell
irm https://raw.githubusercontent.com/steveyegge/beads/main/install.ps1 | iex
```

Verify:

```powershell
bd version
```

## Install Dolt

Use the latest Windows installer from the Dolt releases page, or Chocolatey if that is already part of your workflow.

Official installer:

- https://github.com/dolthub/dolt/releases

Chocolatey:

```powershell
choco install dolt
```

Verify:

```powershell
dolt version
```

## Verify Claude Hooks

If you use Claude Code, install global Beads hooks once:

```powershell
bd setup claude
bd setup claude --check
```

## Per-Repo Setup

In each new repo:

```powershell
bd init -p yourprefix
bd setup codex
```

Or use the bootstrap script to scaffold everything (workflow files, all Codex skills, all Claude skills):

```powershell
pwsh -File .\scripts\windows\bootstrap-new-repo.ps1 -RepoPath D:\path\to\repo -Prefix yourprefix
```
