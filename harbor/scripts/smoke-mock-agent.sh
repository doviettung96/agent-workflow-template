#!/usr/bin/env bash
# Phase 1 smoke test using a fake agent (no codex required).
# Run from Git Bash at the template repo root.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

BEAD_ID="${1:-}"
if [[ -z "$BEAD_ID" ]]; then
  echo "usage: $0 <bead-id>" >&2
  echo "  Pass an existing open bead id (one with a small Files: scope and a trivial Verify: command)." >&2
  exit 2
fi

# Drop a temporary harbor.yml that uses a mock agent. The agent just echoes
# the bead-id sentinel and exits.
cat > harbor.yml <<YAML
default_profile: mock
profiles:
  mock:
    agent_kind: mock
    command: ["sh", "-c", "echo 'mock agent stand-in for ${BEAD_ID}'; echo 'HARBOR-DONE: ${BEAD_ID} status=ok classification=none'"]
    args_template: []
    model: ""
    effort: ""
YAML

trap 'rm -f harbor.yml' EXIT

echo "==> running harbor with mock agent for ${BEAD_ID}"
harbor run-bead "$BEAD_ID" --profile mock --timeout 60
echo "==> done"
