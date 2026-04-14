---
name: apply-stage1-downstream
description: "Apply this template repo's stage-1 workflow scaffold to one downstream repository. Use when the user wants to initialize a downstream repo from this template, refresh its shared skills/docs from this template, or ensure the standalone stage-2 runtime-target and build-and-test follow-up beads exist."
---

# Apply Stage 1 Downstream

## Overview

Run this skill from the template repo to bootstrap or refresh one downstream repo with the shared Beads workflow scaffold, while leaving standalone stage-2 beads for configuring the target runtime and specializing `build-and-test`.

This skill is template-private. It belongs only in this repo's local agent skill folders and must not be added to the top-level `skills/` tree that gets copied downstream.

## Hard Gates

Use this skill only when all of the following are true:

- the current repo is the workflow template repo
- the user wants to apply or refresh stage 1 in a downstream repo
- the work targets exactly one downstream repo

Before mutating anything, confirm the template sources exist:

- `scripts/windows/bootstrap-new-repo.ps1`
- `scripts/windows/update-skills.ps1`
- `scripts/shared/ensure_stage1_beads.py`

If those files are missing, stop and report that the current repo does not look like the template source of truth.

Do not use this skill to:

- specialize the downstream repo's `build-and-test` skill
- manage multiple downstream repos in one invocation
- add this skill to the template's top-level `skills/` directory

## Inputs

Required:

- downstream repo path

Optional:

- Beads prefix for bootstrap

If the target repo needs bootstrap and the user did not provide a prefix, inspect the downstream folder name, propose that as the default prefix, and ask for confirmation before proceeding.

## Decision Flow

### 1. Resolve the downstream repo

- use the repo path from the request
- if the path does not exist yet, bootstrap may still create it
- keep all operations scoped to that one path

### 2. Detect whether stage 1 is already initialized

Run from the downstream repo root:

```bash
bd where
```

Interpret the result this way:

- success: the repo is already Beads-initialized; use the update flow
- failure: the repo is not ready for stage 1 yet; use the bootstrap flow

Do not guess based only on file names or the presence of `.beads/`.

## Update Flow

Use this when `bd where` succeeds.

1. Run the template's platform-appropriate update script against the downstream repo.
2. Run `scripts/shared/ensure_stage1_beads.py <repo>` from the template repo afterward.
3. Rely on the scaffold behavior that preserves an existing downstream `build-and-test` specialization and does not overwrite an existing checkout-local `runtime-target.json`.

Platform commands:

Windows:

```powershell
& .\scripts\windows\update-skills.ps1 -RepoPath "<downstream-repo>"
python .\scripts\shared\ensure_stage1_beads.py "<downstream-repo>"
```

macOS/Linux:

```bash
bash ./scripts/posix/update-skills.sh "<downstream-repo>"
python ./scripts/shared/ensure_stage1_beads.py "<downstream-repo>"
```

## Bootstrap Flow

Use this when `bd where` fails.

1. Determine the Beads prefix.
2. If the prefix was omitted, propose the downstream folder name as the default and ask before continuing.
3. Run the template's platform-appropriate bootstrap script.
4. Do not add extra downstream customizations beyond stage 1.

Platform commands:

Windows:

```powershell
& .\scripts\windows\bootstrap-new-repo.ps1 -RepoPath "<downstream-repo>" -Prefix "<prefix>"
```

macOS/Linux:

```bash
bash ./scripts/posix/bootstrap-new-repo.sh "<downstream-repo>" "<prefix>"
```

The bootstrap script already:

- initializes git when needed
- runs `bd init`
- runs `bd setup codex`
- scaffolds shared docs, skills, and scripts
- creates the standalone stage-2 beads for configuring the target runtime and specializing `build-and-test`

## Post-Run Verification

After either flow completes, verify the downstream repo with:

```bash
bd where
bd ready --json
bd list --json
```

Check for exactly one bead titled:

```text
Configure target runtime for this repo
```

And exactly one bead titled:

```text
Specialize build-and-test for this repo
```

If either bead is missing, report it as a failure of the stage-1 flow. If duplicates exist, report that clearly instead of creating another one.

## Reporting

Report all of the following:

- whether the skill chose bootstrap or update
- the downstream repo path
- the prefix used, if bootstrap ran
- whether each stage-2 bead was created or already existed
- whether verification passed

If the scaffold scripts update downstream instruction files in a way that looks malformed or duplicated, report the affected file and the issue instead of silently inventing extra cleanup.
