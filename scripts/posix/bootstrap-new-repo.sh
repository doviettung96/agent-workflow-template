#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  printf 'usage: %s <repo-path> <prefix> [profile]\n' "$0" >&2
  printf '  profile: generic | game-re (default: generic)\n' >&2
  exit 1
fi

repo_path="$1"
prefix="$2"
profile="${3:-generic}"
case "${profile}" in
  generic|game-re) ;;
  *) printf 'invalid profile: %s (expected generic | game-re)\n' "${profile}" >&2; exit 1 ;;
esac
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

bash "${script_dir}/check-prereqs.sh"

mkdir -p "${repo_path}"

if ! git -C "${repo_path}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git -C "${repo_path}" init >/dev/null
  printf 'Initialized git repository\n'
fi

printf 'Repo:    %s\n' "${repo_path}"
printf 'Prefix:  %s\n' "${prefix}"
printf 'Profile: %s\n' "${profile}"

(
  cd "${repo_path}"
  br init --prefix "${prefix}" --no-db
  rm -f .beads/beads.db .beads/beads.db-wal .beads/beads.db-shm
  br config set issue_prefix "${prefix}" --no-db
  br agents --add --force --no-db
)

bash "${script_dir}/scaffold-repo-files.sh" "${repo_path}" "${prefix}" "${profile}"
python "${script_dir}/../shared/ensure_stage1_beads.py" "${repo_path}" --profile "${profile}"
printf 'Bootstrap complete.\n'
