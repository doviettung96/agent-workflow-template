# Ubuntu/Linux Setup

## Install `br`

Recommended:

```bash
curl -fsSL "https://raw.githubusercontent.com/Dicklesworthstone/beads_rust/main/install.sh?$(date +%s)" | bash
```

Alternative:

```bash
cargo install --git https://github.com/Dicklesworthstone/beads_rust.git
```

Verify:

```bash
br version
```

## Install Python

The Agent Mail wrappers and shared control-plane helpers use Python.

Verify:

```bash
python3 --version
```

## Per-Repo Setup

In each new repo:

```bash
br init --prefix yourprefix
```

Then scaffold the workflow files:

```bash
bash ./scripts/posix/bootstrap-new-repo.sh /path/to/repo yourprefix
```

The bootstrap script now scaffolds only. Run `br init --prefix yourprefix` first.

## Migrate an Existing `bd` Repo

```bash
bash ./scripts/posix/migrate-downstream-to-br.sh /path/to/repo
```
