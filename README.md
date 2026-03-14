# Agent Workflow Template

Reusable Beads-based project bootstrap for Codex and Claude.

This template repo is intentionally self-contained:

- `skills/` bundles the machine-wide Codex skills used by the workflow
- `templates/` contains repo-local files and snippets
- `templates/.codex/skills/build-and-test/` contains the repo-local Codex testing skill
- `scripts/windows/` and `scripts/posix/` provide setup helpers
- `docs/` contains platform-specific installation guides

## What Is Machine-Wide vs Per-Repo

Install once per machine:

- `bd`
- `dolt`
- Codex skills from `skills/`
- Claude global Beads hooks via `bd setup claude`

Scaffold per repo:

- `bd init -p <prefix>`
- `bd setup codex`
- `BEADS_WORKFLOW.md`
- `.codex/skills/build-and-test/SKILL.md`
- `AGENTS.md` and `CLAUDE.md` snippets outside any Beads-managed block

## Recommended Workflow

### Planner Session

1. `plan-beads`
2. `brainstorming`
3. `beads-planner`

### Executor Session

1. `executor-once` or `executor-loop`
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

### 1. Install the bundled global Codex skills

Windows:

```powershell
pwsh -File .\scripts\windows\install-codex-skills.ps1
```

macOS/Linux:

```bash
bash ./scripts/posix/install-codex-skills.sh
```

Restart Codex after installing skills.

### 2. Bootstrap a new repo

Windows:

```powershell
pwsh -File .\scripts\windows\bootstrap-new-repo.ps1 -RepoPath D:\path\to\repo -Prefix myproj
```

macOS/Linux:

```bash
bash ./scripts/posix/bootstrap-new-repo.sh /path/to/repo myproj
```

By default the bootstrap scripts print the Beads commands they would run, then scaffold the repo-local workflow files and the repo-local Codex `build-and-test` skill.

## Template Contents

- `templates/BEADS_WORKFLOW.md`
  Shared planner/executor workflow for a repo
- `templates/.codex/skills/build-and-test/SKILL.md`
  Repo-local Codex testing skill scaffolded into each target repo
- `templates/AGENTS.snippet.md`
  Snippet to append to `AGENTS.md` outside any Beads-managed block
- `templates/CLAUDE.snippet.md`
  Snippet to append to `CLAUDE.md`
- `templates/NEW_REPO_CHECKLIST.md`
  Human checklist for setting up a new project

## Notes

- `bd init` is always per repo.
- `bd setup codex` is per repo because it updates repo instructions.
- Repo-local Codex `build-and-test` is scaffolded into `.codex/skills/build-and-test/SKILL.md`.
- `bd setup claude` is primarily machine-wide because it installs global hooks; repo-local Claude guidance still lives in `CLAUDE.md`.
- The scaffolding scripts never edit inside the Beads-managed `AGENTS.md` block.

## Attribution

The bundled execution-quality skills are curated copies derived from `obra/superpowers` under the MIT license. See [ATTRIBUTION.md](ATTRIBUTION.md).
