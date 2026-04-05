# New Repo Checklist

1. Install `bd`, `dolt`, and Python on the machine.
2. Bootstrap the repo:
   - `bd init -p <prefix> --server --non-interactive --role maintainer --skip-agents --skip-hooks`
   - `bd setup codex`
   - `bd setup claude --check`
3. Scaffold the workflow files from this template.
4. Verify:
   - `bd version`
   - `bd ready --json`
   - `bd where`
   - `scripts/windows/workflow-status.ps1` or `scripts/posix/workflow-status.sh`
5. Confirm repo-specific `build-and-test` is correct.
6. For epic swarm work, run one top-level epic executor session at a time in the checkout.
