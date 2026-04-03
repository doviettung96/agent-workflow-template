#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  printf 'usage: %s <repo-path> <prefix>\n' "$0" >&2
  exit 1
fi

repo_path="$1"
prefix="$2"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"${script_dir}/check-prereqs.sh"

printf 'Repo:   %s\n' "${repo_path}"
printf 'Prefix: %s\n' "${prefix}"

if [[ ! -d "${repo_path}/.beads" ]]; then
  printf "this script now scaffolds only. run 'br init --prefix %s' in %s first.\n" "${prefix}" "${repo_path}" >&2
  exit 1
fi

"${script_dir}/scaffold-repo-files.sh" "${repo_path}" "${prefix}"
printf 'Scaffold complete.\n'
