# Ubuntu/Linux Setup

## Install `br`

```bash
curl -sSL https://raw.githubusercontent.com/steveyegge/beads/main/scripts/install.sh | bash
```

Verify:

```bash
br version
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

The bootstrap script initializes git if needed, runs `br init --prefix yourprefix --no-db`, installs Codex integration, and scaffolds the shared workflow files.

For the full stage-1 then stage-2 adoption flow, see [SETUP-NEW-REPO.md](SETUP-NEW-REPO.md).

## Migrate an Existing `br` Repo To `bd`

```bash
bash ./scripts/posix/migrate-downstream-to-bd.sh /path/to/repo
```
