# Agent Workflow Template

Reusable Beads workflow scaffold for Codex and Claude, standardized on `br` (`beads_rust`) with repo-local `.beads/` state plus shared swarm coordination in Git's common dir.

## What This Template Standardizes

- `br` is the issue tracker CLI
- `.beads/config.yaml` is committed with `no-db: true`
- `.beads/issues.jsonl` is the repo-shared source of truth
- Agent workflow docs, skills, status scripts, and Agent Mail wrappers are scaffolded per repo
- AGENTS/CLAUDE instructions are template-owned, not generated from stock `br agents`

This keeps downstream repos cloneable across machines without local Dolt state or `bd` runtime artifacts.

## Install Once Per Machine

- `br`
- `git`
- Python 3 for the repo-local Agent Mail wrappers and shared control-plane helpers

Install guides:

- Windows: [docs/INSTALL-WINDOWS.md](docs/INSTALL-WINDOWS.md)
- macOS: [docs/INSTALL-MACOS.md](docs/INSTALL-MACOS.md)
- Ubuntu/Linux: [docs/INSTALL-UBUNTU.md](docs/INSTALL-UBUNTU.md)

## Scaffold Per Repo

- run `br init --prefix <prefix>` first
- Template-managed `.beads/config.yaml`, `.beads/.gitignore`, `.beads/metadata.json`, `.beads/README.md`, `.beads/PRIME.md`
- `BEADS_WORKFLOW.md`
- `.beads/workflow/` local worktree runtime files for swarm coordination
- `.codex/skills/`
- `.claude/skills/`
- `scripts/windows/start-epic-worktree.ps1`
- `scripts/posix/start-epic-worktree.sh`
- `scripts/windows/workflow-status.ps1`
- `scripts/posix/workflow-status.sh`
- template-owned managed blocks in `AGENTS.md` and `CLAUDE.md`

## Recommended Workflow

### Planner Session

1. `plan-beads`
2. `brainstorming`
3. `planner-research` when discussion still leaves material technical or domain uncertainty
4. `beads-planner`
5. `validate-beads` runs automatically before the planner session ends when the epic is intended for swarm execution

### Manual Executor Session

1. `executor-once`, `executor-loop`, or `executor-loop-epic`
2. `beads-claim`
3. `writing-plans`
4. implement
5. `systematic-debugging` if blocked
6. repo-local `build-and-test`
7. `requesting-code-review` or `verification-before-completion`
8. `beads-close`

### Swarm Executor Session

1. `swarm-epic`
3. `execute-bead-worker`
4. repo-local `build-and-test`
5. `review-epic`
6. `finishing-a-development-branch`

Beads remains the source of truth for task state. Agent Mail is the shared reservation and coordination layer for swarm execution across all worktrees for the repo.

`planner-research` is intentionally planner-only. It exists to answer factual unknowns before bead creation and should fold findings back into the approved design and bead descriptions instead of creating a second planning/state system.

`swarm-epic` is the composed epic executor now:
- it assumes validation already happened during `plan-beads`
- it creates or reuses the epic worktree if needed
- it runs epic-level review before finishing

## Quick Start

### 1. Initialize `br`, Then Scaffold a New Repo

Run `br` once per repo first:

```bash
br init --prefix myproj
```

Windows:

```powershell
pwsh -File .\scripts\windows\bootstrap-new-repo.ps1 -RepoPath D:\path\to\repo -Prefix myproj
```

macOS/Linux:

```bash
bash ./scripts/posix/bootstrap-new-repo.sh /path/to/repo myproj
```

The bootstrap scripts now scaffold only. They expect `.beads/` to already exist and then copy workflow files, managed instruction blocks, status scripts, worktree helpers, and repo-local skills.

### 2. Sync Template Changes Into an Existing Repo

Windows:

```powershell
pwsh -File .\scripts\windows\update-skills.ps1 -RepoPath D:\path\to\repo
```

macOS/Linux:

```bash
bash ./scripts/posix/update-skills.sh /path/to/repo
```

This refreshes workflow docs, managed AGENTS/CLAUDE blocks, repo-local skills, `.beads/` template files, Agent Mail helpers, worktree helpers, and workflow status scripts.

### 3. Migrate an Existing `bd` Repo

Windows:

```powershell
pwsh -File .\scripts\windows\migrate-downstream-to-br.ps1 -RepoPath D:\path\to\repo
```

macOS/Linux:

```bash
bash ./scripts/posix/migrate-downstream-to-br.sh /path/to/repo
```

The migration helpers export the current `bd` issue state first, replace stale `bd`/Dolt settings, initialize `br`, switch the repo to `no-db: true`, and sync the template-owned workflow files.

## Editing Skills

This template's `skills/` directory is the single source of truth for workflow skills. Codex and Claude read skills from different locations, so each downstream repo carries two copies.

When updating a skill:

1. Edit `skills/<name>/`
2. Run `update-skills` against each downstream repo

Do not edit skills directly inside a target repo's `.codex/skills/` or `.claude/skills/`.

## Template Contents

- `templates/BEADS_WORKFLOW.md`
- `templates/.beads/`
- `templates/.codex/skills/build-and-test/`
- `templates/AGENTS.snippet.md`
- `templates/CLAUDE.snippet.md`
- `skills/`
- `scripts/windows/`
- `scripts/posix/`
- `scripts/shared/agent_mail.py`

## Notes

- The template standard is `br` plus `.beads/config.yaml` with `no-db: true`.
- In no-db mode, normal `br` mutations write the repo-shared JSONL directly. Downstream repos do not need routine `br sync --flush-only` in normal sessions.
- `br sync --import-only` or other sync commands are reserved for migration, recovery, or non-standard storage setups.
- In swarm mode, local runtime stays in `.beads/workflow/`, while shared locks, reservations, and mailbox threads live under `git rev-parse --git-common-dir`.

## Attribution

The bundled execution-quality skills are curated copies derived from `obra/superpowers` under the MIT license. See [ATTRIBUTION.md](ATTRIBUTION.md).
