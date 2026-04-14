---
name: target-runtime-exec
description: "Use when project execution should follow the repo's selected runtime target instead of assuming the local machine. This covers build, test, run, deploy, migration, codegen, or environment-bootstrap commands that should route through `scripts/shared/target_runtime.py` when `.beads/workflow/runtime-target.json` selects SSH."
---

# Target Runtime Exec

Route environment-dependent project commands through the repo's selected runtime target.

Keep local exploration local. This skill is only for commands that execute repo code or depend on the target runtime environment.

## Use This For

- builds
- tests
- app or service launch commands
- migrations
- code generation tied to the project runtime
- Docker, Conda, or similar repo bootstrap commands

## Do Not Use This For

- reading files
- searching the repo
- `git status`, `git diff`, or similar inspection
- checking what tools or files exist locally

## Steps

1. Inspect the runtime target:

   ```bash
   python scripts/shared/target_runtime.py status
   ```

2. If the status reports `local`, run the project command through the helper anyway so the execution path stays explicit:

   ```bash
   python scripts/shared/target_runtime.py run -- <exact command>
   ```

3. If the status reports `ssh`, use the same helper command. It will:
   - sync the repo to the configured remote workdir
   - execute the command on the configured SSH host
   - fail if the SSH target, sync step, or remote command fails

4. Preserve the repo's exact command string.
   - Do not substitute another command because it seems more convenient.
   - Prefer repo-owned wrapper scripts when the repo already provides them.

## Command Shape

Always pass the exact project command after `--`.

Examples:

```bash
python scripts/shared/target_runtime.py run -- pytest tests/api/test_health.py -q
python scripts/shared/target_runtime.py run -- bash scripts/verify.sh
python scripts/shared/target_runtime.py run -- pwsh -File .\scripts\verify.ps1
python scripts/shared/target_runtime.py run -- docker compose up --build --detach
```

## Hard Rules

- Do not silently bypass the helper for runtime-dependent commands.
- Do not silently fall back to local execution if SSH mode fails.
- If the configured target is invalid, stop and report the exact config or connectivity problem.
- If the surrounding task is `Configure target runtime for this repo`, ask the user to choose `local` or `ssh` before treating the current config as the answer.
- If the user chooses `ssh`, collect or confirm `ssh_host`, `remote_platform`, and `remote_workdir` before proceeding.
- If Python-based commands should run under a specific remote interpreter, collect or confirm `remote_python` too.
