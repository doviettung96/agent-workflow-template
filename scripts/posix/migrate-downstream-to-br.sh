#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  printf 'usage: %s <repo-path> [prefix] [profile]\n' "$0" >&2
  exit 1
fi

repo_path="$1"
prefix="${2:-}"
profile="${3:-}"
case "${profile}" in
  ""|generic|game-re) ;;
  *) printf 'invalid profile: %s (expected generic | game-re)\n' "${profile}" >&2; exit 1 ;;
esac

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
template_root="$(cd "${script_dir}/../.." && pwd)"

bash "${script_dir}/check-prereqs.sh"
if ! command -v bd >/dev/null 2>&1; then
  printf 'bd is required for migrate-downstream-to-br.sh but was not found on PATH\n' >&2
  exit 1
fi

python_cmd=""
if command -v python3 >/dev/null 2>&1; then
  python_cmd="python3"
elif command -v python >/dev/null 2>&1; then
  python_cmd="python"
else
  printf 'python is required for migrate-downstream-to-br.sh but was not found on PATH\n' >&2
  exit 1
fi

args=(--repo "${repo_path}")
if [[ -n "${prefix}" ]]; then
  args+=(--prefix "${prefix}")
fi

"${python_cmd}" "${template_root}/scripts/shared/migrate_bd_to_br.py" "${args[@]}"
bash "${script_dir}/update-skills.sh" "${repo_path}" "${profile}"
"${python_cmd}" "${template_root}/scripts/shared/dedupe_stage1_beads.py" --repo "${repo_path}"

(cd "${repo_path}" && br list --json --no-db >/dev/null)
printf 'Migrated %s to br --no-db\n' "${repo_path}"
