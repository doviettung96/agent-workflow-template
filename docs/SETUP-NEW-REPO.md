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
   - `beads-planner`
2. Let the first planning pass define the runtime shape, likely files, and verification needs.
3. Make sure early execution plans include a precise `## Verification` section with exact commands and expected evidence. The stage-1 `build-and-test` skill depends on that section and will not guess.

## Stage 2: Project-Specific Customization

Customize the repo only after the real workflow becomes obvious from the first plan, first beads, or first implementation cycle.

Typical stage-2 changes:

- specialize `.codex/skills/build-and-test/SKILL.md`
- mirror the same specialization to `.claude/skills/build-and-test/SKILL.md`
- add runtime-specific setup or operational notes
- add repo-specific guidance outside the managed blocks in `AGENTS.md` or `CLAUDE.md`

Examples:

- web app: `npm run build`, `npm run preview`, HTTP smoke checks, browser inspection
- backend service: package build, process launch, API health checks
- device viewer: serve the app, connect to a live device or image, confirm the UI renders the session correctly

## Ongoing Maintenance

- edit shared workflow skills in this template repo, then run `update-skills` for downstream repos
- keep repo-specific `build-and-test` customizations local to the downstream repo
- if template changes should not overwrite a downstream specialization, rely on the existing scaffold behavior that preserves `build-and-test`
