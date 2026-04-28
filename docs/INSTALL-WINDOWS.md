# Windows Setup

## Install `br`

Native PowerShell helpers require `br` on the Windows `PATH`. If Rust is installed:

```powershell
cargo install --git https://github.com/Dicklesworthstone/beads_rust.git
```

WSL install:

```powershell
wsl bash -lc 'curl -fsSL "https://raw.githubusercontent.com/Dicklesworthstone/beads_rust/main/install.sh?$(date +%s)" | bash'
```

Verify:

```powershell
br --version
```

If `br` is installed only inside WSL, run the POSIX setup helpers from WSL instead of the PowerShell helpers.

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

## Migrate an Existing `bd` Repo To `br`

```powershell
pwsh -File .\scripts\windows\migrate-downstream-to-br.ps1 -RepoPath D:\path\to\repo
```
