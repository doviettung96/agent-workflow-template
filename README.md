# Agent Workflow Template

Reusable Beads-based project bootstrap for Codex and Claude.

This template repo is intentionally self-contained:

- `skills/` contains the workflow skills scaffolded into each repo
- `templates/` contains repo-local files and snippets
- `templates/.codex/skills/build-and-test/` contains the repo-local Codex testing skill
- `scripts/windows/` and `scripts/posix/` provide setup helpers
- `docs/` contains platform-specific installation guides

## What Is Machine-Wide vs Per-Repo

Install once per machine:

- `bd`
- `dolt`
- Claude global Beads hooks via `bd setup claude`

Scaffold per repo:

- `bd init -p <prefix>`
- `bd setup codex`
- `BEADS_WORKFLOW.md`
- `.codex/skills/` — all Codex skills from `skills/` plus `build-and-test`
- `.claude/skills/` — all Claude Code skills from `skills/`
- `AGENTS.md` and `CLAUDE.md` snippets outside any Beads-managed block

## Recommended Workflow

### Planner Session

1. `plan-beads`
2. `brainstorming`
3. `beads-planner`

### Executor Session

1. `executor-once`, `executor-loop`, or `executor-loop-epic`
2. `beads-claim`
3. `writing-plans`
4. implement
5. `systematic-debugging` if blocked
6. repo-local `build-and-test`
7. `requesting-code-review` or `verification-before-completion`
8. `beads-close`

Beads is the source of truth for task state. The execution-quality skills improve planning and delivery, but they do not replace Beads tracking.

## Install Guides

- Windows: [docs/INSTALL-WINDOWS.md](docs/INSTALL-WINDOWS.md)
- macOS: [docs/INSTALL-MACOS.md](docs/INSTALL-MACOS.md)
- Ubuntu/Linux: [docs/INSTALL-UBUNTU.md](docs/INSTALL-UBUNTU.md)

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

By default the bootstrap scripts print the Beads commands they would run, then scaffold all workflow files, Codex skills, and Claude skills into the target repo.

### 2. Update skills in an existing repo

After editing skills in this template, sync them to a target repo:

Windows:

```powershell
pwsh -File .\scripts\windows\update-skills.ps1 -RepoPath D:\path\to\repo
```

macOS/Linux:

```bash
bash ./scripts/posix/update-skills.sh /path/to/repo
```

This re-copies all skills from `skills/` into both `.codex/skills/` and `.claude/skills/`, and updates `BEADS_WORKFLOW.md` in the target repo.

## Editing Skills

This template's `skills/` directory is the **single source of truth** for all workflow skills. Codex and Claude read skills from different locations (`.codex/skills/` and `.claude/skills/`), so each target repo carries two copies.

When updating a skill:

1. Edit the skill in this repo's `skills/<name>/`
2. Run `update-skills` against each target repo to sync both Codex and Claude copies

Never edit skills directly in a target repo's `.codex/skills/` or `.claude/skills/` — those are overwritten on sync.

## Template Contents

- `templates/BEADS_WORKFLOW.md`
  Shared planner/executor workflow for a repo
- `skills/executor-loop-epic/`
  Optional epic-scoped loop skill for focused autonomous execution within one epic
- `templates/.codex/skills/build-and-test/SKILL.md`
  Codex testing skill scaffolded into each target repo
- `templates/AGENTS.snippet.md`
  Snippet to append to `AGENTS.md` outside any Beads-managed block
- `templates/CLAUDE.snippet.md`
  Snippet to append to `CLAUDE.md`
- `templates/NEW_REPO_CHECKLIST.md`
  Human checklist for setting up a new project

## Notes

- `bd init` is always per repo.
- `bd setup codex` is per repo because it updates repo instructions.
- All workflow skills are scaffolded per repo: Codex skills in `.codex/skills/`, Claude skills in `.claude/skills/`.
- `bd setup claude` is machine-wide because it installs global hooks; repo-local Claude guidance lives in `CLAUDE.md` and `.claude/skills/`.
- The scaffolding scripts never edit inside the Beads-managed `AGENTS.md` block.

## Attribution

The bundled execution-quality skills are curated copies derived from `obra/superpowers` under the MIT license. See [ATTRIBUTION.md](ATTRIBUTION.md).
