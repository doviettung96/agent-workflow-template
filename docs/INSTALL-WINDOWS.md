# Windows Setup

## Install `br`

Recommended for native Windows:

```powershell
cargo install --git https://github.com/Dicklesworthstone/beads_rust.git
```

Verify:

```powershell
br version
```

## Install Python

The Agent Mail wrappers and shared control-plane helpers use Python. Ensure either `py`, `python`, or `python3` is on `PATH`.

Verify:

```powershell
py -3 --version
```

or:

```powershell
python --version
```

## Per-Repo Setup

In each new repo:

```powershell
br init --prefix yourprefix
```

Then scaffold the workflow files:

```powershell
pwsh -File .\scripts\windows\bootstrap-new-repo.ps1 -RepoPath D:\path\to\repo -Prefix yourprefix
```

The bootstrap script now scaffolds only. Run `br init --prefix yourprefix` first.

## Migrate an Existing `bd` Repo

```powershell
pwsh -File .\scripts\windows\migrate-downstream-to-br.ps1 -RepoPath D:\path\to\repo
```
