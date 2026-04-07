# Ubuntu/Linux Setup

## Install `bd`

```bash
curl -sSL https://raw.githubusercontent.com/steveyegge/beads/main/scripts/install.sh | bash
```

Verify:

```bash
bd version
```

## Install `dolt`

Install Dolt on the machine and verify:

```bash
dolt version
```

## Install Python

Ensure `python3` or `python` is on `PATH`.

Verify:

```bash
python3 --version
```

## Per-Repo Setup

```bash
bash ./scripts/posix/bootstrap-new-repo.sh /path/to/repo yourprefix
```

The bootstrap script initializes git if needed, runs `bd init -p yourprefix --server --skip-agents --skip-hooks`, installs Codex integration, and scaffolds the shared workflow files.

For the full stage-1 then stage-2 adoption flow, see [SETUP-NEW-REPO.md](SETUP-NEW-REPO.md).

## Migrate an Existing `br` Repo

```bash
bash ./scripts/posix/migrate-downstream-to-bd.sh /path/to/repo
```
