# Agent Workflow Template

Reusable Beads workflow scaffold for Codex and Claude, standardized on local-only `bd` with Dolt in server mode plus single-checkout swarm execution, with optional SSH-backed runtime execution for downstream repos.

This template repo is intentionally self-contained:

- `skills/` contains the shared workflow skills scaffolded into each repo
- `templates/` contains repo-local files and snippets
- `templates/.codex/skills/build-and-test/` contains the generic stage-1 validator that downstream repos can later specialize
- `templates/.codex/skills/plan-critic/` and `templates/.claude/skills/plan-critic/` contain provider-specific debate critics
- `scripts/shared/target_runtime.py` routes project execution through the selected local or SSH runtime target
- `scripts/windows/` and `scripts/posix/` provide setup, migration, and sync helpers
- `docs/` contains install and troubleshooting notes

## What Is Machine-Wide vs Per-Repo

Install once per machine:

- `bd`
- `dolt`
- Python (for Agent Mail and workflow helpers)

Initialize per repo:

- `bd init -p <prefix> --server --skip-agents --skip-hooks`
- `bd setup codex`
- `BEADS_WORKFLOW.md`
- `.codex/skills/`
- `.claude/skills/`
- `AGENTS.md` and `CLAUDE.md` managed snippets

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

## General vs Project-Specific Downstream Files

General downstream files:

- `BEADS_WORKFLOW.md`
- `.beads/PRIME.md`, `.beads/README.md`
- `.beads/workflow/runtime-target.json` with local defaults
- managed workflow blocks in `AGENTS.md` and `CLAUDE.md`
- `.codex/skills/` and `.claude/skills/` copied from `skills/` plus any provider-specific template skills
- helper scripts under `scripts/`
- `docs/TROUBLESHOOTING.md`

Project-specific downstream files:

- the repo-local specialized `build-and-test`
- any repo-owned wrapper scripts for platform-specific build or verification commands
- any repo-context prose outside the managed workflow blocks
- runtime-specific setup, deployment, or smoke-test docs
- handoff files such as `LOCAL_WORKFLOW_SETUP.md`

## Recommended Workflow

### Planner Session

1. `plan-beads`
2. `brainstorming`
3. `planner-research` when facts still need verification
4. `plan-debate` when the user asks for extra scrutiny or the plan is risky
5. `beads-planner`
6. `validate-beads`

### Executor Session

Use one of:

- `executor-once` for one manual bead or a fresh-session manual bead-by-bead rhythm
- `executor-loop` for sequential manual execution when a long-lived session is still acceptable
- `swarm-epic <epic-id>` for epic-scoped multi-agent execution

`swarm-epic` runs in the current checkout and uses branch `epic/<epic-id>` for the target epic.

## Local-Only Beads Model

- Live Beads state is local to this clone under `.beads/`
- Beads task state is not shared through Git or Dolt remotes
- Code still moves through normal feature branches and pull requests
- Run one top-level epic executor session at a time in a clone

`swarm-epic` still parallelizes ready descendant beads inside one epic, but it does not try to isolate multiple epics with worktrees anymore.

Swarm-ready does not mean dependency-free. It means each bead is fresh-session-safe: a new worker can execute it from the bead contract, persisted inputs, and local code inspection without replaying the full epic chat.

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

The bootstrap script initializes git if needed, initializes Beads locally with `bd`, installs Codex integration, scaffolds the workflow docs, skills, and helper scripts into the repo, seeds the local runtime-target config, and creates standalone stage-2 follow-up beads for configuring the target runtime and specializing `build-and-test`.

### 2. Plan the first work

Use the planner flow immediately, even if the repo is mostly empty:

1. `plan-beads`
2. `brainstorming`
3. `planner-research` only when facts still matter
4. `plan-debate` if needed
5. `beads-planner`
6. `validate-beads` when the resulting epic is meant for `swarm-epic`

Make the first execution plans explicit about `## Verification`, because the stage-1 `build-and-test` skill follows that section literally.

Make the first swarm-targeted beads explicit about `Read:` and `Inputs:` as well, so a fresh worker can execute without replaying planner chat.

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

### 4. Migrate an existing `br` repo back to `bd`

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

This template has two skill sources:

- `skills/` for shared workflow skills copied to both providers
- `templates/.codex/skills/` and `templates/.claude/skills/` for provider-specific skills

Target repos carry two provider copies:

- `.codex/skills/`
- `.claude/skills/`

When updating a shared workflow skill:

1. Edit `skills/<name>/` in this template repo
2. Run `update-skills` against each target repo

When updating a provider-specific skill:

1. Edit `templates/.codex/skills/<name>/` or `templates/.claude/skills/<name>/`
2. Run `update-skills` against each target repo

Do not hand-edit shared skill copies in downstream repos unless you intentionally want a repo-specific divergence.

The intended repo-specific divergences are the local `build-and-test` skill, repo-owned runtime wrappers, and the checkout-local runtime-target config. `update-skills` preserves an existing downstream `build-and-test`, and the scaffold seeds missing workflow files without overwriting an existing runtime-target config.

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
- `templates/.codex/skills/build-and-test/SKILL.md`
  Generic stage-1 validation skill scaffolded into each target repo
- `templates/.codex/skills/plan-critic/` and `templates/.claude/skills/plan-critic/`
  Provider-specific plan critics used by the planner debate gate
- `skills/target-runtime-exec/`
  Shared skill for routing build/test/run/deploy commands through the selected target runtime
- `templates/AGENTS.snippet.md`
  Managed snippet for `AGENTS.md`
- `templates/CLAUDE.snippet.md`
  Managed snippet for `CLAUDE.md`
- `templates/NEW_REPO_CHECKLIST.md`
  Human checklist for setting up a new project

## Notes

- `bd init` is per repo.
- `bd setup codex` is per repo.
- The scaffolding scripts do not use Dolt remotes.
- Live `.beads` runtime is local-only and should not be committed.

## Attribution

The bundled execution-quality skills are curated copies derived from `obra/superpowers` and adapted with Beads-native planning/execution flow plus selected ideas from GSD and Khuym. See [ATTRIBUTION.md](ATTRIBUTION.md).
