# New Repo Setup Guide

Use this guide when starting a downstream repo from scratch or when a repo is still too empty to support project-specific workflow customization.

## Stage 1: General Bootstrap

1. Ensure machine prerequisites exist:
   - `bd`
   - `dolt`
   - Python
2. Bootstrap the repo from this template:
   - macOS/Linux: `bash ./scripts/posix/bootstrap-new-repo.sh /path/to/repo <prefix>`
   - Windows: `pwsh -File .\scripts\windows\bootstrap-new-repo.ps1 -RepoPath D:\path\to\repo -Prefix <prefix>`
3. The bootstrap script:
   - initializes git if the target path is not already a repo
   - runs `bd init -p <prefix> --server --skip-agents --skip-hooks`
   - runs `bd setup codex`
   - scaffolds the shared workflow docs, skills, and helper scripts
   - installs the managed root `.gitignore` block for local-only workflow assets
   - seeds `.beads/workflow/runtime-target.json` with local execution as the default
   - creates standalone stage-2 beads for configuring the target runtime and specializing `build-and-test`
4. Verify the repo is ready:
   - `bd where`
   - `bd ready --json`
   - `scripts/posix/workflow-status.sh` or `scripts/windows/workflow-status.ps1`

## First Work In An Empty Repo

You do not need project-specific skills yet.

1. Run a planner session:
   - `plan-beads`
   - `brainstorming`
   - `planner-research` only if facts still matter
   - confirm the settled plan for Beads creation
   - `beads-planner`
   - `validate-beads` when the epic is intended for `swarm-epic`
2. Let the first planning pass define the runtime shape, likely files, verification needs, and the persisted inputs later beads should rely on.
3. For swarm-targeted beads, make sure the bead contract includes `Read:`, `Inputs:`, `Files:`, and `Verify:` so a fresh worker can execute without replaying planner chat.
4. Make sure early execution plans include a precise `## Verification` section with exact commands and expected evidence. The stage-1 `build-and-test` skill depends on that section and will not guess.
5. Keep the bootstrap-created `Configure target runtime for this repo` and `Specialize build-and-test for this repo` beads independent. Do not make them children of the first feature epic.
6. If a repo's first real verification must run on a non-local machine, complete `Configure target runtime for this repo` before those feature beads execute.

## Stage 2: Project-Specific Customization

Customize the repo only after the real workflow becomes obvious from the first plan, first beads, or first implementation cycle.

Typical stage-2 changes:

- optionally customize `.beads/workflow/runtime-target.json` in active checkouts with `python scripts/shared/target_runtime.py configure ...`
- add repo-owned wrapper commands for build, run, and verification when local Windows and remote POSIX/Windows commands differ
- specialize `.codex/skills/build-and-test/SKILL.md`
- mirror the same specialization to `.claude/skills/build-and-test/SKILL.md`
- add runtime-specific setup or operational notes
- add repo-specific guidance outside the managed blocks in `AGENTS.md` or `CLAUDE.md`
- rely on `sync-workflow-backup` / `finishing-a-development-branch` to publish updated workflow docs and skills through the backup repo, not the downstream project remote

When executing `Configure target runtime for this repo`:

- ask the user up front whether this checkout should use `local` or `ssh`
- if the user chooses `ssh`, collect the concrete `ssh_host`, `remote_platform`, `remote_workdir`, and any relevant sync preference before closing the bead
- when `sync_strategy=rsync`, treat sync as additive by default and do not remove remote-only files; if the remote workdir contains disposable files only and the user explicitly wants mirroring, confirm that separately instead of assuming destructive sync
- when `sync_strategy=archive`, use a dedicated remote workdir because archive sync replaces that directory contents during extraction
- collect `remote_python` too when Python-based commands should use a specific interpreter on the remote host (for example a project Miniconda env)
- inspect the repo for stable evidence about the intended target environment first
- use repo evidence to validate or complete the configuration, but not to skip the explicit runtime choice prompt
- do not treat "leave the checked-in default as local" as sufficient completion unless the user explicitly confirms that local execution is the intended steady state for the checkout
- keep machine-specific SSH values checkout-local, but still configure the active checkout when the user wants a real remote target now

Examples:

- web app: `npm run build`, `npm run preview`, HTTP smoke checks, browser inspection
- backend service: package build, process launch, API health checks
- device viewer: serve the app, connect to a live device or image, confirm the UI renders the session correctly

## Ongoing Maintenance

- edit shared workflow skills in this template repo, then run `update-skills` for downstream repos
- keep scaffolded workflow docs, skills, and helper scripts local-only in the downstream repo and sync them to `agentic-workflows/<project>/`
- keep repo-specific `build-and-test` customizations local to the downstream repo
- keep actual SSH host aliases checkout-local in `.beads/workflow/runtime-target.json`
- if template changes should not overwrite a downstream specialization, rely on the existing scaffold behavior that preserves `build-and-test`
