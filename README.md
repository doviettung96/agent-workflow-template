# Agent Workflow Template

Reusable Beads workflow scaffold for Codex and Claude, standardized on local-only `bd` with Dolt in server mode plus native Beads worktrees.

This template repo is intentionally self-contained:

- `skills/` contains the workflow skills scaffolded into each repo
- `templates/` contains repo-local files and snippets
- `templates/.codex/skills/build-and-test/` contains the starter Codex testing skill
- `scripts/windows/` and `scripts/posix/` provide setup, migration, and sync helpers
- `docs/` contains install and troubleshooting notes

## What Is Machine-Wide vs Per-Repo

Install once per machine:

- `bd` 1.0.0+
- `dolt`
- Python (for Agent Mail and worktree helpers)

Initialize per repo:

- `bd init -p <prefix> --server --non-interactive --role maintainer --skip-agents --skip-hooks`
- `bd setup codex`
- `bd setup claude --check`
- `BEADS_WORKFLOW.md`
- `.codex/skills/`
- `.claude/skills/`
- `AGENTS.md` and `CLAUDE.md` managed snippets

## Recommended Workflow

### Planner Session

1. `plan-beads`
2. `brainstorming`
3. `planner-research` when facts still need verification
4. `beads-planner`
5. `validate-beads`

### Executor Session

Use one of:

- `executor-once` for one manual bead
- `executor-loop` for sequential manual execution
- `swarm-epic <epic-id>` for epic-scoped multi-agent execution

Worktree-backed epic execution uses `start-epic-worktree`, which wraps Beads’ native `bd worktree create`.

## Local-Only Beads Model

- Live Beads state is local to this clone under `.beads/`
- Worktrees share the main checkout’s `.beads` through Beads redirect files
- Beads task state is not shared through Git or Dolt remotes
- Code still moves through normal feature branches and pull requests

Inside a worktree, `bd` should work directly as long as the worktree was created through `bd worktree create` or `start-epic-worktree`.

## Quick Start

### 1. Bootstrap a repo

Windows:

```powershell
pwsh -File .\scripts\windows\bootstrap-new-repo.ps1 -RepoPath D:\path\to\repo -Prefix myproj
```

macOS/Linux:

```bash
bash ./scripts/posix/bootstrap-new-repo.sh /path/to/repo myproj
```

The bootstrap script initializes Beads locally with `bd`, then scaffolds the workflow docs, skills, and helper scripts into the repo.

### 2. Update workflow files in an existing repo

Windows:

```powershell
pwsh -File .\scripts\windows\update-skills.ps1 -RepoPath D:\path\to\repo
```

macOS/Linux:

```bash
bash ./scripts/posix/update-skills.sh /path/to/repo
```

### 3. Migrate an existing `br` repo back to `bd`

Windows:

```powershell
pwsh -File .\scripts\windows\migrate-downstream-to-bd.ps1 -RepoPath D:\path\to\repo
```

macOS/Linux:

```bash
bash ./scripts/posix/migrate-downstream-to-bd.sh /path/to/repo
```

The migration helper imports the current live `issues.jsonl` into a new local `bd` database, archives the old `br` state under `.beads/backup/`, removes the shared-beads layer, and then reapplies the template workflow files.

## Editing Skills

This template’s `skills/` directory is the source of truth for workflow skills. Target repos carry two copies:

- `.codex/skills/`
- `.claude/skills/`

When updating a skill:

1. Edit `skills/<name>/` in this template repo
2. Run `update-skills` against each target repo

Do not hand-edit skill copies in downstream repos unless you intentionally want a repo-specific divergence.

## Install Guides

- Windows: [docs/INSTALL-WINDOWS.md](docs/INSTALL-WINDOWS.md)
- macOS: [docs/INSTALL-MACOS.md](docs/INSTALL-MACOS.md)
- Ubuntu/Linux: [docs/INSTALL-UBUNTU.md](docs/INSTALL-UBUNTU.md)

## Template Contents

- `templates/BEADS_WORKFLOW.md`
  Shared planner/executor workflow for a repo
- `skills/swarm-epic/`
  Epic-scoped multi-agent execution
- `templates/.codex/skills/build-and-test/SKILL.md`
  Starter Codex testing skill scaffolded into each target repo
- `templates/AGENTS.snippet.md`
  Managed snippet for `AGENTS.md`
- `templates/CLAUDE.snippet.md`
  Managed snippet for `CLAUDE.md`
- `templates/NEW_REPO_CHECKLIST.md`
  Human checklist for setting up a new project

## Notes

- `bd init` is per repo.
- `bd setup codex` is per repo.
- `bd setup claude --check` verifies project-local Claude integration.
- The scaffolding scripts do not use Dolt remotes.
- Live `.beads` runtime is local-only and should not be committed.

## Attribution

The bundled execution-quality skills are curated copies derived from `obra/superpowers` and adapted with Beads-native planning/execution flow plus selected ideas from GSD and Khuym. See [ATTRIBUTION.md](ATTRIBUTION.md).
