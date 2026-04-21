#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python_cmd=""
if command -v python3 >/dev/null 2>&1; then
  python_cmd="python3"
elif command -v python >/dev/null 2>&1; then
  python_cmd="python"
else
  printf 'python is required for sync-workflow-backup.sh\n' >&2
  exit 1
fi

"${python_cmd}" "${script_dir}/../shared/sync_workflow_backup.py" sync "$@"
