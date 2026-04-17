# New Repo Checklist

## Stage 1: General Workflow Bootstrap

1. Install `bd`, `dolt`, and Python on the machine.
2. Bootstrap the repo with the template script. If the target path is empty, the script initializes git first.
   - macOS/Linux: `bash ./scripts/posix/bootstrap-new-repo.sh /path/to/repo <prefix>`
   - Windows: `pwsh -File .\scripts\windows\bootstrap-new-repo.ps1 -RepoPath D:\path\to\repo -Prefix <prefix>`
3. Verify:
   - `bd version`
   - `bd ready --json`
   - `bd where`
   - `scripts/windows/workflow-status.ps1` or `scripts/posix/workflow-status.sh`
4. Confirm the standalone bootstrap bead exists:
   - `Configure target runtime for this repo`
   - `Specialize build-and-test for this repo`
5. Use the general planner flow immediately, even in an empty repo:
   - `plan-beads`
   - `brainstorming`
   - `planner-research` if needed
   - `plan-debate` if needed
   - `beads-planner`
   - `validate-beads` if the epic is intended for `swarm-epic`
6. Ensure early swarm-targeted beads include `Read:`, `Inputs:`, `Files:`, and `Verify:` so a fresh worker can execute them without replaying planner chat.
7. Keep the bootstrap-created runtime-target and build-and-test beads independent; do not nest them under the first feature epic.
8. Ensure the first execution plans include an exact `## Verification` section because the stage-1 `build-and-test` skill is generic and follows the plan literally.
9. If the first runtime-changing feature must verify against a remote machine, finish `Configure target runtime for this repo` first.

## Stage 2: Project-Specific Specialization

1. After the first plan and beads make the real runtime shape clear, optionally configure the target runtime for the active checkout.
2. Customize the repo-local `build-and-test` skill once the repeated verification flow is clear.
3. Add repo-specific setup docs only when there is stable runtime, build, serve, deploy, or smoke-test behavior worth documenting.
4. Keep the general workflow skills synced from this template; only the repo-local specializations should diverge.
5. For epic swarm work, run one top-level epic executor session at a time in the checkout.
6. Prefer `executor-once` for manual bead-by-bead work; treat long-running loop executors as compatibility paths.
