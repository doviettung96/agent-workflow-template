---
name: finishing-a-development-branch
description: "Use after all work on a feature branch is complete and verified. Pushes the branch and creates a PR targeting main."
---

# Finishing a Development Branch

**Workflow position:** Final step after all beads are closed and build-and-test passes. See BEADS_WORKFLOW.md.

**Announce at start:** "I'm using the finishing-a-development-branch skill to push and create a PR."

## Prerequisites

Before invoking this skill, ensure:

- All beads for this work are closed
- `build-and-test` passes
- All changes are committed on the feature branch

## Steps

### 1. Verify clean state

```bash
git status
git log --oneline main..HEAD
```

- Working tree must be clean (no uncommitted changes)
- There must be commits ahead of main
- If dirty, stop and ask the user to commit or stash

### 2. Push the branch

```bash
git push -u origin HEAD
```

If push fails (e.g., no remote, auth issues), report the error and stop.

### 3. Create a pull request

```bash
gh pr create --base main --fill
```

- Use `--fill` to auto-populate title and body from commits
- If the user has provided a PR title or description, use `--title` and `--body` instead
- Report the PR URL to the user

### 4. Snapshot export is separate

The live Beads store is shared per clone outside branch-local tracked files, not carried branch-by-branch in the PR.

If you want the latest Beads state committed for Git sharing across machines, switch to the main checkout after merge and run `shared-beads export-snapshot` there.

### 5. Report completion

```
PR created: <url>
Branch: <branch-name>
```

## Hard Rules

- Never force-push unless the user explicitly asks
- Never delete the remote branch — let the PR merge process handle that
- Never merge locally — the PR is the merge mechanism
- If `gh` is not available, push the branch and report the branch name for manual PR creation

## Quick Reference

| Situation | Action |
|-----------|--------|
| Uncommitted changes | Stop, ask user to commit |
| No commits ahead of main | Stop, nothing to PR |
| Push fails | Report error, stop |
| `gh` not installed | Push branch, report for manual PR |
| PR creation fails | Report error, branch is pushed |

## Sync Discipline

- Before checking `git status`, run `br sync --flush-only`.
- Treat `br sync --flush-only` as part of branch completion, not optional cleanup.
- Do not expect a feature branch PR to carry the Beads snapshot by default; snapshot export happens explicitly from main.
- If `git status` is dirty after the flush, stop and resolve that state before pushing or creating a PR.

## Integration

**Called by:**
- **`executor-loop-epic`** — after all beads in the epic are closed
- Any workflow that completes work on a feature branch

**Pairs with:**
- **`build-and-test`** — must pass before invoking this skill
