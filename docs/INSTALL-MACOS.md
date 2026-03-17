# macOS Setup

## Install Beads

Recommended:

```bash
brew install beads
```

Alternative official install script:

```bash
curl -fsSL https://raw.githubusercontent.com/steveyegge/beads/main/scripts/install.sh | bash
```

Verify:

```bash
bd version
```

## Install Dolt

Recommended:

```bash
brew install dolt
```

Alternative official install script:

```bash
sudo bash -c 'curl -L https://github.com/dolthub/dolt/releases/latest/download/install.sh | bash'
```

Verify:

```bash
dolt version
```

## Verify Claude Hooks

If you use Claude Code, install global Beads hooks once:

```bash
bd setup claude
bd setup claude --check
```

## Per-Repo Setup

In each new repo:

```bash
bd init -p yourprefix
bd setup codex
```

Or use the bootstrap script to scaffold everything (workflow files, all Codex skills, all Claude skills):

```bash
bash ./scripts/posix/bootstrap-new-repo.sh /path/to/repo yourprefix
```
