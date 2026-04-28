---
name: finishing-a-development-branch
description: "Use after all work on a feature branch is complete and verified. Pushes the branch and creates a PR targeting main."
---

# Finishing a Development Branch

**Workflow position:** Final step after all beads are closed and build-and-test passes. See BEADS_WORKFLOW.md.

**Announce at start:** "I'm using the finishing-a-development-branch skill to sync workflow backup, push, and create a PR."

## Prerequisites

Before invoking this skill, ensure:

- All beads for this work are closed
- `build-and-test` passes
- All changes are committed on the feature branch
- the local backup repo clone exists (default: sibling `../agentic-workflows`, override with `AGENTIC_WORKFLOWS_REPO`)

## Steps

### 1. Verify clean downstream state

```bash
br where --no-db
git status
git log --oneline main..HEAD
```

- Working tree must be clean (no uncommitted changes)
- There must be commits ahead of main
- `br where --no-db` must succeed in the current checkout
- If dirty, stop and ask the user to commit or stash

### 2. Sync the workflow backup mirror

macOS/Linux:

```bash
bash ./scripts/posix/sync-workflow-backup.sh
```

Windows:

```powershell
pwsh -File .\scripts\windows\sync-workflow-backup.ps1
```

- This syncs the repo-local workflow surface into `agentic-workflows/<project>/`
- The backup repo must already be a clean checkout before running this command
- If the sync or backup push fails, stop before pushing the development branch

### 3. Push the branch

```bash
git push -u origin HEAD
```

If push fails (e.g., no remote, auth issues), report the error and stop.

### 4. Create a pull request

```bash
gh pr create --base main --fill
```

- Use `--fill` to auto-populate title and body from commits
- If the user has provided a PR title or description, use `--title` and `--body` instead
- Report the PR URL to the user

### 5. Report completion

```
PR created: <url>
Branch: <branch-name>
```

## Hard Rules

- Never force-push unless the user explicitly asks
- Never delete the remote branch — let the PR merge process handle that
- Never merge locally — the PR is the merge mechanism
- Never skip the workflow-backup sync when the repo uses the local-only workflow mirror model
- If `gh` is not available, push the branch and report the branch name for manual PR creation

## Quick Reference

| Situation | Action |
|-----------|--------|
| Uncommitted changes | Stop, ask user to commit |
| No commits ahead of main | Stop, nothing to PR |
| Backup repo dirty/missing | Stop, fix the backup checkout first |
| Workflow backup sync fails | Report error, stop before branch push |
| Push fails | Report error, stop |
| `gh` not installed | Push branch, report for manual PR |
| PR creation fails | Report error, branch is pushed |

## Beads Runtime Discipline

- Treat Beads as local runtime. Do not try to publish live `.beads` state through Git during normal branch completion.
- Workflow scaffold files are local-only in downstream Git. Publish them through the workflow backup mirror instead of the downstream project remote.
- If `br where --no-db` fails, stop and repair the checkout with `br init --prefix <prefix> --no-db` before pushing or creating a PR.

## Integration

**Called by:**
- **`executor-loop-epic`** — after all beads in the epic are closed
- Any workflow that completes work on a feature branch

**Pairs with:**
- **`build-and-test`** — must pass before invoking this skill
