---
name: finishing-a-development-branch
description: "Use after all work on a feature branch is complete and verified. Pushes the branch, creates a PR targeting main, and cleans up the worktree."
---

# Finishing a Development Branch

**Workflow position:** Final step after all beads are closed and build-and-test passes. See BEADS_WORKFLOW.md.

**Announce at start:** "I'm using the finishing-a-development-branch skill to push, create a PR, and clean up."

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

### 4. Clean up the worktree

If currently working inside a worktree:

```bash
# Record the worktree path and branch name
worktree_path=$(git rev-parse --show-toplevel)
branch_name=$(git rev-parse --abbrev-ref HEAD)

# Move back to the main working tree
cd $(git worktree list --porcelain | head -1 | sed 's/worktree //')

# Remove the worktree
git worktree remove "$worktree_path"
```

If NOT in a worktree (working directly on a branch in the main tree), skip cleanup.

### 5. Report completion

```
PR created: <url>
Branch: <branch-name>
Worktree cleaned up: <path> (if applicable)
```

## Hard Rules

- Never force-push unless the user explicitly asks
- Never delete the remote branch — let the PR merge process handle that
- Never merge locally — the PR is the merge mechanism
- If the worktree has uncommitted changes, stop and report instead of discarding
- If `gh` is not available, push the branch and report the branch name for manual PR creation

## Quick Reference

| Situation | Action |
|-----------|--------|
| Uncommitted changes | Stop, ask user to commit |
| No commits ahead of main | Stop, nothing to PR |
| Push fails | Report error, stop |
| `gh` not installed | Push branch, report for manual PR |
| Not in a worktree | Skip worktree cleanup |
| PR creation fails | Report error, branch is pushed |

## Integration

**Called by:**
- **`executor-loop-epic`** — after all beads in the epic are closed
- Any workflow that completes work on a feature branch

**Pairs with:**
- **`using-git-worktrees`** — creates the worktree this skill cleans up
- **`build-and-test`** — must pass before invoking this skill
