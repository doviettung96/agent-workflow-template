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
bd init -p yourprefix --server --non-interactive --role maintainer --skip-agents --skip-hooks
bd setup codex
bd setup claude --check
bash ./scripts/posix/bootstrap-new-repo.sh /path/to/repo yourprefix
```

## Migrate an Existing `br` Repo

```bash
bash ./scripts/posix/migrate-downstream-to-bd.sh /path/to/repo
```
