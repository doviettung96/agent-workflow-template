#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  printf 'usage: %s <repo-path> [prefix]\n' "$0" >&2
  exit 1
fi

repo_path="$1"
prefix="${2:-}"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
template_root="$(cd "${script_dir}/../.." && pwd)"

bash "${script_dir}/check-prereqs.sh"

python_cmd=""
if command -v python3 >/dev/null 2>&1; then
  python_cmd="python3"
elif command -v python >/dev/null 2>&1; then
  python_cmd="python"
else
  printf 'python is required for migrate-downstream-to-bd.sh but was not found on PATH\n' >&2
  exit 1
fi

args=(--repo "${repo_path}")
if [[ -n "${prefix}" ]]; then
  args+=(--prefix "${prefix}")
fi

"${python_cmd}" "${template_root}/scripts/shared/migrate_br_to_bd.py" "${args[@]}"
bash "${script_dir}/scaffold-repo-files.sh" "${repo_path}" "${prefix}"

(cd "${repo_path}" && bd list --json >/dev/null)
printf 'Migrated %s to bd/local Dolt\n' "${repo_path}"
