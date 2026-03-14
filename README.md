# Agent Workflow Template

Reusable Beads-based project bootstrap for Codex and Claude.

This template repo is intentionally self-contained:

- `skills/` bundles the Codex skills used by the workflow
- `templates/` contains repo-local files and snippets
- `scripts/windows/` and `scripts/posix/` provide setup helpers
- `docs/` contains platform-specific installation guides

## What Is Machine-Wide vs Per-Repo

Install once per machine:

- `bd`
- `dolt`
- Codex skills from `skills/`
- Claude global Beads hooks via `bd setup claude`

Run once per repo:

- `bd init -p <prefix>`
- `bd setup codex`
- copy `BEADS_WORKFLOW.md`
- add the `AGENTS.md` and `CLAUDE.md` snippets outside any Beads-managed block

## Recommended Workflow

1. `brainstorming`
2. `beads-planner`
3. claim a bead
4. `writing-plans`
5. implement
6. `systematic-debugging` if blocked
7. `requesting-code-review` or `verification-before-completion`
8. `beads-task-cycle`

Beads is the source of truth for task state. The execution-quality skills improve planning and delivery, but they do not replace Beads tracking.

## Install Guides

- Windows: [docs/INSTALL-WINDOWS.md](docs/INSTALL-WINDOWS.md)
- macOS: [docs/INSTALL-MACOS.md](docs/INSTALL-MACOS.md)
- Ubuntu/Linux: [docs/INSTALL-UBUNTU.md](docs/INSTALL-UBUNTU.md)

## Quick Start

### 1. Install the bundled Codex skills

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

By default the bootstrap scripts print the Beads commands they would run, then scaffold the workflow files. Pass the execution flag described in the script help to run `bd init` and `bd setup codex` automatically.

## Template Contents

- `templates/BEADS_WORKFLOW.md`
  Shared planner/executor workflow for a repo
- `templates/AGENTS.snippet.md`
  Snippet to append to `AGENTS.md` outside any Beads-managed block
- `templates/CLAUDE.snippet.md`
  Snippet to append to `CLAUDE.md`
- `templates/NEW_REPO_CHECKLIST.md`
  Human checklist for setting up a new project

## Notes

- `bd init` is always per repo.
- `bd setup codex` is per repo because it updates repo instructions.
- `bd setup claude` is primarily machine-wide because it installs global hooks; repo-local Claude guidance still lives in `CLAUDE.md`.
- The scaffolding scripts never edit inside the Beads-managed `AGENTS.md` block.

## Attribution

The bundled execution-quality skills are curated copies derived from `obra/superpowers` under the MIT license. See [ATTRIBUTION.md](ATTRIBUTION.md).
