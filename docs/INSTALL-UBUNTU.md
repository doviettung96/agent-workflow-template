# Ubuntu/Linux Setup

## Install Beads

Use the official install script:

```bash
curl -fsSL https://raw.githubusercontent.com/steveyegge/beads/main/scripts/install.sh | bash
```

If you already use Homebrew on Linux, this also works:

```bash
brew install beads
```

Verify:

```bash
bd version
```

## Install Dolt

Use the official Linux installer:

```bash
sudo bash -c 'curl -L https://github.com/dolthub/dolt/releases/latest/download/install.sh | bash'
```

Verify:

```bash
dolt version
```

## Install Bundled Codex Skills

From this template repo:

```bash
bash ./scripts/posix/install-codex-skills.sh
```

Restart Codex after installing skills.

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

Then copy or scaffold:

- `BEADS_WORKFLOW.md`
- `AGENTS.md` snippet outside the Beads-managed block
- `CLAUDE.md` snippet

You can use:

```bash
bash ./scripts/posix/bootstrap-new-repo.sh /path/to/repo yourprefix
```
