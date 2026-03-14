#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  printf 'usage: %s <repo-path> <prefix>\n' "$0" >&2
  exit 1
fi

repo_path="$1"
prefix="$2"
run_setup="${RUN_SETUP:-0}"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"${script_dir}/check-prereqs.sh"

printf 'Repo:   %s\n' "${repo_path}"
printf 'Prefix: %s\n' "${prefix}"

if [[ "${run_setup}" == "1" ]]; then
  (
    cd "${repo_path}"
    bd init -p "${prefix}"
    bd setup codex
    bd setup claude --check
  )
else
  printf 'Dry run. Commands to execute in %s:\n' "${repo_path}"
  printf '  bd init -p %s\n' "${prefix}"
  printf '  bd setup codex\n'
  printf '  bd setup claude --check\n'
fi

"${script_dir}/scaffold-repo-files.sh" "${repo_path}"
printf 'Bootstrap complete.\n'
