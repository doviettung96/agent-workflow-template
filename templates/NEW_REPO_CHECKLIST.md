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
   - `Specialize build-and-test for this repo`
5. Use the general planner flow immediately, even in an empty repo:
   - `plan-beads`
   - `brainstorming`
   - `planner-research` if needed
   - `beads-planner`
6. Keep the bootstrap-created build-and-test specialization bead independent; do not nest it under the first feature epic.
7. Ensure the first execution plans include an exact `## Verification` section because the stage-1 `build-and-test` skill is generic and follows the plan literally.

## Stage 2: Project-Specific Specialization

1. After the first plan and beads make the real runtime shape clear, customize the repo-local `build-and-test` skill.
2. Add repo-specific setup docs only when there is stable runtime, build, serve, deploy, or smoke-test behavior worth documenting.
3. Keep the general workflow skills synced from this template; only the repo-local specializations should diverge.
4. For epic swarm work, run one top-level epic executor session at a time in the checkout.
