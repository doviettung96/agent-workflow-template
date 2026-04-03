#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  printf 'usage: %s <repo-path>\n' "$0" >&2
  exit 1
fi

repo_path="$1"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"${script_dir}/check-prereqs.sh"
"${script_dir}/scaffold-repo-files.sh" "${repo_path}"
printf 'Skills synced to %s\n' "${repo_path}"
