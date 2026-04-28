---
name: finishing-a-development-branch
description: "Use after all work for one epic is complete and verified. Reconstructs an epic PR branch from prefixed commits on a feature branch, pushes it, and creates a PR targeting main."
---

# Finishing a Development Branch

**Workflow position:** Final step after all beads for one epic are closed and build-and-test passes. See BEADS_WORKFLOW.md.

**Announce at start:** "I'm using the finishing-a-development-branch skill to reconstruct the epic PR branch from prefixed commits, sync workflow backup, push, and create a PR."

## Prerequisites

Before invoking this skill, ensure:

- the target epic id is known
- all beads for this epic are closed
- `build-and-test` passed on the source feature branch
- all intended changes for this epic are committed on the source feature branch
- every commit for this epic has a subject that starts exactly `<epic-id>:`
- the local backup repo clone exists when the repo uses the workflow-backup mirror model (default: sibling `../agentic-workflows`, override with `AGENTIC_WORKFLOWS_REPO`)

## Steps

### 1. Verify source branch and select commits

```bash
br where --no-db
git fetch origin
git branch --show-current
git status --short
git merge-base --is-ancestor main origin/main
git log --reverse --format="%H%x09%s" origin/main..HEAD
```

- The current branch is the source feature branch, often a temporary mixed-epic branch.
- The source branch does not need to be clean, but all intended changes for this epic must already be committed.
- Stop if the current branch is `main`.
- Stop if local `main` exists and cannot be fast-forwarded from `origin/main`.
- Select only commits from `origin/main..HEAD` whose subject starts exactly `<epic-id>:`.
- Stop if there are no matching commits.
- Stop if any selected commit is a merge commit; require a linear epic slice.
- Do not include commits for other prefixes, even if they are nearby or appear related.
- Check merge commits with `git rev-list --parents -n 1 <commit>`; selected commits must have exactly one parent.

PowerShell selection helper:

```powershell
$epicId = "<epic-id>"
$selected = git log --reverse --format="%H%x09%s" origin/main..HEAD |
  Where-Object { $_ -match "^[0-9a-f]{40}`t$([regex]::Escape($epicId)):" } |
  ForEach-Object { ($_ -split "`t", 2)[0] }
$selected
```

POSIX selection helper:

```bash
epic_id="<epic-id>"
git log --reverse --format='%H%x09%s' origin/main..HEAD |
  awk -F '\t' -v prefix="${epic_id}:" 'index($2, prefix) == 1 {print $1}'
```

### 2. Sync the workflow backup mirror

macOS/Linux:

```bash
bash ./scripts/posix/sync-workflow-backup.sh
```

Windows:

```powershell
pwsh -File .\scripts\windows\sync-workflow-backup.ps1
```

- This syncs the repo-local workflow surface into `agentic-workflows/<project>/`.
- The backup repo must already be a clean checkout before running this command.
- If the sync or backup push fails, stop before creating or pushing the PR branch.

### 3. Reconstruct the epic PR branch

```bash
git switch main
git pull --ff-only origin main
git switch -c epic/<epic-id>
git cherry-pick <selected-commit-1> <selected-commit-2> ...
```

- If `epic/<epic-id>` already exists locally, inspect it before changing it. Do not overwrite it unless the user explicitly asks.
- If uncommitted source-branch changes prevent switching branches, stop and report the blocking paths; do not stash, discard, or auto-commit unrelated work.
- Cherry-pick commits in their original order from the source branch.
- If a cherry-pick conflicts, stop with the conflict details and do not add unrelated commits.
- After cherry-pick, confirm the branch contains only the selected epic commits plus `main`.

### 4. Verify, push, and create the PR

Run the repo-local `build-and-test` skill again on `epic/<epic-id>`.

Then push and create the PR:

```bash
git push -u origin epic/<epic-id>
gh pr create --base main --head epic/<epic-id> --fill
```

- If the user has provided a PR title or description, use `--title` and `--body` instead of only `--fill`.
- If `gh` is not available, push the branch and report the branch name for manual PR creation.
- If PR creation fails, report the error; the branch remains pushed.

### 5. Report completion and temporary branch cleanup

Report:

```text
PR created: <url>
PR branch: epic/<epic-id>
Source branch: <source-branch>
Selected commits: <count>
```

If all prefixed commits from the source branch have already been extracted into PR branches, report the exact cleanup commands but do not run them automatically:

```bash
git branch -d <source-branch>
git push origin --delete <source-branch>
```

If other epic prefixes remain on the source branch, list them and leave the source branch in place.

Prefix discovery helpers:

```powershell
git log --format="%s" origin/main..<source-branch> |
  Where-Object { $_ -match "^[A-Za-z0-9_.-]+:" } |
  ForEach-Object { ($_ -split ":", 2)[0] } |
  Sort-Object -Unique
```

```bash
git log --format='%s' origin/main..<source-branch> |
  awk -F ':' '/^[A-Za-z0-9_.-]+:/ {print $1}' |
  sort -u
```

## Hard Rules

- Never force-push unless the user explicitly asks.
- Never delete local or remote temporary branches automatically.
- Never merge locally; the PR is the merge mechanism.
- Never include commits whose subject does not start exactly `<epic-id>:`.
- Never skip the second verification on the reconstructed PR branch.
- Never skip the workflow-backup sync when the repo uses the local-only workflow mirror model.
- If `br where --no-db` fails, stop and repair the checkout with `br init --prefix <prefix> --no-db` before pushing or creating a PR.

## Quick Reference

| Situation | Action |
|-----------|--------|
| On `main` as source | Stop, choose the source feature branch |
| No matching `<epic-id>:` commits | Stop, nothing to PR |
| Source branch has uncommitted changes | Continue only if all intended epic changes are already committed |
| Selected commit is a merge commit | Stop, require linear commits |
| Existing `epic/<epic-id>` branch | Inspect, do not overwrite without explicit user request |
| Backup repo dirty/missing | Stop, fix the backup checkout first |
| Workflow backup sync fails | Report error, stop before branch push |
| Cherry-pick conflicts | Stop and report conflict details |
| PR-branch verification fails | Stop, do not push or create PR |
| Push fails | Report error, stop |
| `gh` not installed | Push branch, report for manual PR |
| PR creation fails | Report error, branch is pushed |

## Beads Runtime Discipline

- Treat Beads as local runtime. Do not try to publish live `.beads` state through Git during normal branch completion.
- Workflow scaffold files are local-only in downstream Git. Publish them through the workflow backup mirror instead of the downstream project remote.

## Integration

**Called by:**
- **`swarm-epic`** - after all beads in the epic are closed and review passes
- **`executor-loop-epic`** - after all beads in the epic are closed
- Any workflow that completes one epic on a feature branch

**Pairs with:**
- **`build-and-test`** - must pass before invocation and again after PR-branch reconstruction
