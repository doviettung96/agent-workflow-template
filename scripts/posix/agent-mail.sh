#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
shared_script="${script_dir}/../shared/agent_mail.py"

python_cmd=""
if command -v python3 >/dev/null 2>&1; then
  python_cmd="python3"
elif command -v python >/dev/null 2>&1; then
  python_cmd="python"
else
  printf 'python is required for agent-mail.sh but was not found on PATH\n' >&2
  exit 1
fi

"${python_cmd}" "${shared_script}" "$@"
