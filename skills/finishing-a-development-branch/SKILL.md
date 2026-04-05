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

### 4. Report completion

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

## Beads Runtime Discipline

- Before checking `git status`, confirm the current checkout still resolves the Beads database with `bd where`.
- Treat Beads as local runtime. Do not try to publish live `.beads` state through Git during normal branch completion.
- If `bd where` fails, stop and repair the checkout with `bd bootstrap --yes` before pushing or creating a PR.

## Integration

**Called by:**
- **`executor-loop-epic`** — after all beads in the epic are closed
- Any workflow that completes work on a feature branch

**Pairs with:**
- **`build-and-test`** — must pass before invoking this skill
