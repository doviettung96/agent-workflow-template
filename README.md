# Agent Workflow Template

Reusable Beads workflow scaffold for Codex and Claude, standardized on local-only `br --no-db` plus checkout-local swarm execution, with optional hydrated Git worktrees for parallel epics and optional SSH-backed runtime execution for downstream repos.

This template repo is intentionally self-contained:

- `skills/` contains the shared workflow skills scaffolded into each repo
- `templates/` contains repo-local files and snippets
- `templates/.codex/skills/build-and-test/` contains the generic stage-1 validator that downstream repos can later specialize
- `scripts/shared/target_runtime.py` routes project execution through the selected local or SSH runtime target
- `scripts/shared/sync_workflow_backup.py` mirrors downstream workflow files into the separate backup repo
- `scripts/windows/` and `scripts/posix/` provide setup, migration, and sync helpers
- `docs/` contains install and troubleshooting notes

## What Is Machine-Wide vs Per-Repo

Install once per machine:

- `br`
- Python (for Agent Mail and workflow helpers)

Initialize per repo:

- `br init --prefix <prefix> --no-db`
- `br agents --add --force --no-db`
- `BEADS_WORKFLOW.md`
- `.codex/skills/`
- `.claude/skills/`
- `AGENTS.md` as the canonical managed instructions file plus a thin `CLAUDE.md` reference snippet
- managed `.gitignore` block for local-only workflow assets

## Two-Stage Adoption

### Stage 1: General workflow bootstrap

Use this when the downstream repo is brand new or too empty to infer a runtime profile.

- bootstrap the repo with the template script
- install the general workflow docs and skills
- seed `.beads/workflow/runtime-target.json` with local execution as the default
- create standalone stage-2 bootstrap beads for configuring the target runtime and specializing `build-and-test`
- use `plan-beads` immediately to create the first plan and beads
- rely on the generic stage-1 `build-and-test`, which executes the `## Verification` commands from each execution plan without guessing the stack

### Stage 2: Project-specific specialization

Do this after the first real plan or bead set makes the repo's runtime shape obvious.

- optionally configure a non-local target runtime for SSH execution
- specialize repo-local `build-and-test`
- add repo-specific setup or operational docs
- keep the shared workflow skills synced from this template

## Workflow Backup Mirror

Downstream repos keep the workflow scaffold on disk, but stop publishing it through the downstream project remote.

- downstream Git ignores the scaffolded workflow surface
- `agentic-workflows/<project>/` becomes the remote history for those workflow files
- `finishing-a-development-branch` runs workflow-backup sync before branch push / PR creation
- the default backup repo is a sibling checkout `../agentic-workflows`; override with `AGENTIC_WORKFLOWS_REPO`

Sync manually when needed:

Windows:

```powershell
pwsh -File .\scripts\windows\sync-workflow-backup.ps1
```

macOS/Linux:

```bash
bash ./scripts/posix/sync-workflow-backup.sh
```

Migrate an older downstream repo that still tracks workflow files:

Windows:

```powershell
pwsh -File .\scripts\windows\migrate-downstream-to-workflow-backup.ps1 -RepoPath D:\path\to\repo
```

macOS/Linux:

```bash
bash ./scripts/posix/migrate-downstream-to-workflow-backup.sh /path/to/repo
```

The migration helper refreshes the scaffold, syncs the current workflow surface to the backup repo, and removes tracked workflow files from the downstream Git index while leaving them on disk.

## General vs Project-Specific Downstream Files

All of the files below remain local in the downstream checkout. Their remote copy lives in the backup mirror, not the downstream project remote.

General downstream files:

- `BEADS_WORKFLOW.md`
- `.beads/PRIME.md`, `.beads/README.md`
- `.beads/workflow/runtime-target.json` with local defaults
- the managed workflow block in `AGENTS.md` plus a thin `CLAUDE.md` reference block
- `.codex/skills/` and `.claude/skills/` copied from `skills/` plus any provider-specific template skills
- helper scripts under `scripts/`
- `docs/TROUBLESHOOTING.md`

Project-specific downstream files:

- the repo-local specialized `build-and-test`
- any repo-owned wrapper scripts for platform-specific build or verification commands
- any repo-context prose outside the managed `AGENTS.md` workflow block
- runtime-specific setup, deployment, or smoke-test docs
- handoff files such as `LOCAL_WORKFLOW_SETUP.md`

## Recommended Workflow

### Planner Session

1. `plan-beads`
2. `brainstorming`
3. `planner-research` when facts still need verification
4. brief the settled recommendation and get confirmation to create Beads
5. `beads-planner`
6. `validate-beads`

### Executor Session

Use one of:

- `executor-once` for one worker-backed bead with a fresh implementation subagent
- `executor-loop` for sequential manual execution when a long-lived session is still acceptable
- `executor-loop-epic <epic-id>` for sequential worker-backed execution inside one epic
- `swarm-epic <epic-id>` for epic-scoped multi-agent execution

`swarm-epic` runs in the current checkout and uses branch `epic/<epic-id>` for the target epic.

If you want checkout isolation for a truly parallel epic, run `start-epic-worktree` from the current checkout first. It creates the worktree and copies the ignored workflow surface into it so `swarm-epic` works there too.

## Local-Only Beads Model

- Live Beads state is local to this clone under `.beads/`
- Beads task state is not shared through Git remotes
- Code still moves through normal feature branches and pull requests
- Run one top-level epic executor session at a time in a clone

`executor-once` and `executor-loop-epic` also use fresh workers for implementation, but keep one bead active at a time. `swarm-epic` parallelizes ready descendant beads inside one epic. When you need a separate checkout, `start-epic-worktree` prepares a worktree with its own copied local workflow surface.

Worker-ready does not mean dependency-free. It means each bead is fresh-session-safe: a new worker can execute it from the bead contract, persisted inputs, and local code inspection without replaying the full epic chat.

When a worker blocks, the worker should classify the blocker. Local clarifications or environment issues can stay on the same worker; contract or scope problems should be fixed by the coordinator and usually retried with a fresh worker.

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

The bootstrap script initializes git if needed, initializes Beads locally with `br`, installs Codex integration, scaffolds the workflow docs, skills, and helper scripts into the repo, seeds the local runtime-target config, and creates standalone stage-2 follow-up beads for configuring the target runtime and specializing `build-and-test`.
It also installs the managed root `.gitignore` block and the downstream `sync-workflow-backup` helper.

### 2. Plan the first work

Use the planner flow immediately, even if the repo is mostly empty:

1. `plan-beads`
2. `brainstorming`
3. `planner-research` only when facts still matter
4. confirm the settled plan for Beads creation
5. `beads-planner`
6. `validate-beads` when the resulting epic is meant for `swarm-epic`

Make the first execution plans explicit about `## Verification`, because the stage-1 `build-and-test` skill follows that section literally.

Make the first worker-targeted beads explicit about `Read:` and `Inputs:` as well, so a fresh worker can execute without replaying planner chat.

If verification may run through SSH or across mixed Windows/POSIX environments, prefer repo-owned wrapper commands in `## Verification` instead of brittle ad hoc shell pipelines.

### 3. Update workflow files in an existing repo

Windows:

```powershell
pwsh -File .\scripts\windows\update-skills.ps1 -RepoPath D:\path\to\repo
```

macOS/Linux:

```bash
bash ./scripts/posix/update-skills.sh /path/to/repo
```

`update-skills` refreshes the shared workflow surface, keeps repo-local `build-and-test`, refreshes the managed root `.gitignore` workflow block, and updates the backup-sync helper scripts.

### 4. Migrate an existing downstream repo to the backup mirror model

Windows:

```powershell
pwsh -File .\scripts\windows\migrate-downstream-to-workflow-backup.ps1 -RepoPath D:\path\to\repo
```

macOS/Linux:

```bash
bash ./scripts/posix/migrate-downstream-to-workflow-backup.sh /path/to/repo
```

This is the one-time cleanup for older repos that still track `AGENTS.md`, `CLAUDE.md`, `BEADS_WORKFLOW.md`, `docs/plans/`, repo-local skills, and scaffolded helper scripts in the downstream project remote.

### 5. Migrate an existing `bd` repo to `br`

Windows:

```powershell
pwsh -File .\scripts\windows\migrate-downstream-to-br.ps1 -RepoPath D:\path\to\repo
```

macOS/Linux:

```bash
bash ./scripts/posix/migrate-downstream-to-br.sh /path/to/repo
```

The migration helper converts the current local `bd` state into a `br --no-db` JSONL workflow, archives the previous `.beads` state under `.beads/backup/`, removes obsolete `bd` artifacts, and then reapplies the template workflow files.

## Editing Skills

This template has two skill sources:

- `skills/` for shared workflow skills copied to both providers
- `templates/.codex/skills/` and `templates/.claude/skills/` for provider-specific skills

Target repos carry two provider copies:

- `.codex/skills/`
- `.claude/skills/`

When updating a shared workflow skill:

1. Edit `skills/<name>/` in this template repo
2. Run `update-skills` against each target repo
3. Run `sync-workflow-backup` in the downstream repo before pushing a PR there

When updating a provider-specific skill:

1. Edit `templates/.codex/skills/<name>/` or `templates/.claude/skills/<name>/`
2. Run `update-skills` against each target repo
3. Run `sync-workflow-backup` in the downstream repo before pushing a PR there

Do not hand-edit shared skill copies in downstream repos unless you intentionally want a repo-specific divergence.

The intended repo-specific divergences are the local `build-and-test` skill, repo-owned runtime wrappers, and the checkout-local runtime-target config. `update-skills` preserves an existing downstream `build-and-test`, refreshes the local-only workflow ignore block, and seeds missing workflow files without overwriting an existing runtime-target config.

## Install Guides

- Windows: [docs/INSTALL-WINDOWS.md](docs/INSTALL-WINDOWS.md)
- macOS: [docs/INSTALL-MACOS.md](docs/INSTALL-MACOS.md)
- Ubuntu/Linux: [docs/INSTALL-UBUNTU.md](docs/INSTALL-UBUNTU.md)
- New repo walkthrough: [docs/SETUP-NEW-REPO.md](docs/SETUP-NEW-REPO.md)

## Template Contents

- `templates/BEADS_WORKFLOW.md`
  Shared planner/executor workflow for a repo
- `skills/swarm-epic/`
  Epic-scoped multi-agent execution
- `skills/start-epic-worktree/`
  Optional helper for creating a hydrated parallel worktree before epic execution
- `templates/.codex/skills/build-and-test/SKILL.md`
  Generic stage-1 validation skill scaffolded into each target repo
- `skills/target-runtime-exec/`
  Shared skill for routing build/test/run/deploy commands through the selected target runtime
- `templates/AGENTS.snippet.md`
  Canonical managed snippet for `AGENTS.md`
- `templates/CLAUDE.snippet.md`
  Thin reference snippet for `CLAUDE.md`
- `templates/NEW_REPO_CHECKLIST.md`
  Human checklist for setting up a new project
- `scripts/shared/workflow_backup.py`
  Shared manifest and `.gitignore` management for the workflow backup mirror
- `scripts/shared/sync_workflow_backup.py`
  Syncs the downstream workflow surface into `agentic-workflows/<project>/`

## Notes

- `br init` is per repo.
- `br agents --add --force --no-db` is per repo.
- The scaffolding scripts do not use tracker remotes.
- Live `.beads` runtime and local agent settings such as `.beads/config.yaml`, `.beads/metadata.json`, and `.claude/settings.json` are local-only and should not be committed.
- Scaffolded workflow files are local-only in downstream Git and should be mirrored through the backup repo before PRs, including repo-specific workflow notes such as `docs/WORKFLOW_NOTES.md`.

## Attribution

The bundled execution-quality skills are curated copies derived from `obra/superpowers` and adapted with Beads-native planning/execution flow plus selected ideas from GSD and Khuym. See [ATTRIBUTION.md](ATTRIBUTION.md).
