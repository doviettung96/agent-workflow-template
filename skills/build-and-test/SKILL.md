---
name: build-and-test
description: "Generic finalize prompt for discovering and running a repository's build and test checks when no repo-specific top-level skill has been written yet."
---

# Build and Test

Run the repository's normal build and test checks. This is a generic finalize default for newly bootstrapped downstream repos; replace it with repo-specific commands once the project workflow is known.

## Discovery

Read the local project files before running commands:

- `README.md` or equivalent setup docs
- `pyproject.toml`
- `package.json`
- `Makefile`
- CI configuration, if present

Prefer explicit project scripts over guessed commands. If more than one plausible stack exists, choose the smallest check set that validates the files changed in the current work and state the reason.

Files:
- (no files modified - verification only)

Verify:
- discover and run the repo's documented build/test commands

## Steps

1. Inspect `git status --short` and the changed paths.
2. Read the build/test configuration files listed above.
3. Identify the exact commands that are appropriate for the changed areas.
4. Run those commands from the repository root.
5. Report each command, its exit code, and the relevant output.

If the repository does not yet document a runnable build or test command, emit `blocked classification=contract` and explain what command or project metadata is missing. If a command exists but cannot run because of the local environment, emit `blocked classification=env` and include the failing command and error.
