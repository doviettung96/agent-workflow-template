# Next steps — work has moved to D:\Projects\harbor

This template repo is **legacy as of 2026-05-10**. Stop adding features here.

## Where to continue

**`D:\Projects\harbor`** — combined repo containing:
- The harbor Python package (extracted from this template's `harbor/` via `git subtree split`, full history preserved).
- The new agtx-style workflow template: brainstorm → sweep → one-agent-per-task with explicit per-task acceptance criteria.
- Game-RE runtime targeting (emulator/device/game-window) via `.agtx/runtime-target.json` and `scripts/shared/target_runtime.py`.

## What's there already (committed locally; no remote yet)

- All 4 new skills: `agtx-sweep-with-acceptance`, `agtx-task-worker`, `agtx-task-verify`, `runtime-target-config`.
- 4 carried-over skills: `brainstorming`, `verification-before-completion`, `systematic-debugging`, `writing-plans`.
- 2 edited skills: `build-and-test` (with `## Verification Probes` parsing), `target-runtime-exec` (pointed at `.agtx/runtime-target.json`).
- `scripts/shared/target_runtime.py` extended with `target.kind` + emulator/device/game-window subobjects + user-defined probe_command.
- `scripts/shared/probe_target.py` for runtime-target reachability checks.
- `.agtx/runtime-target.json` (committed default) + `.agtx/runtime-target.example.json` (LDPlayer + Blue Archive).
- `README.md`, `AGENTS.md` (canonical contract), `CLAUDE.md`, `docs/INSTALL-WINDOWS.md`.
- harbor's bead-coupled modules tagged `# DEPRECATED:` in their docstrings: `beads.py`, `epic.py`, `runner.py`, `mail.py`, `finalize.py`.

## Open items to pick up next

| # | Item | Notes |
|---|------|-------|
| 1 | **Phase D end-to-end validation on Windows** | Drive a mock task through Backlog → Planning → Running → Review in `agtx --experimental`. Mock task already seeded. Verify worktree spawns, tmux window opens, worker honors `## Verification Probes`. |
| 2 | **Tighten the worker/verify gate** | agtx's default plugin doesn't explicitly invoke `agtx-task-worker` / `agtx-task-verify`. The worker reads the three headers but can drift. Either ship a custom agtx plugin (`plugin.toml` with our skill calls baked into the running/review prompts) or override the default plugin's prompts in the project. |
| 3 | **Push to a git remote** | Neither the new harbor repo nor this template repo has a remote yet. Pick where to host (GitHub org/repo) and push. |
| 4 | **Decide harbor's post-bead role** | The bead-coupled modules are deprecated but not deleted. Options: rebuild harbor's webui as the agtx dashboard, or keep harbor as a tmux-fallback launcher for flows agtx doesn't cover. Decide, then delete the deprecated modules. |
| 5 | **Polish `target set-local`** | Currently doesn't reset previously-set device/emulator/game-window subobjects when switching back to local. Low priority. |
| 6 | **agtx binary** | Single canonical binary at `~/.cargo/bin/agtx.exe` (8.23 MB, built 2026-05-10 from patched D:\Projects\agtx source). Both Claude (`~/.claude.json`) and Codex (`~/.codex/config.toml`) MCP configs point at it. The patched source still has 9 failing cargo tests on Windows (sh assumptions, stale tmux mocks) — fix those if you want a clean test suite. |
| 7 | **Mock task** | Already seeded in agtx for D:\Projects\harbor. Title: "Write hello marker file". Body has the three header sections including 2 Python probes. Use it for end-to-end validation. |

## Reference

The original migration plan is at `C:\Users\Admin\.claude\plans\i-think-we-should-pure-allen.md`.

## What stays in THIS template repo

The bead workflow itself stays here — `.beads/`, `executor-once`, `executor-loop`, `swarm-epic`, `beads-claim`, `BEADS_WORKFLOW.md`, etc. — for any downstream repo that's still on the bead workflow. New work goes in `D:\Projects\harbor`.
