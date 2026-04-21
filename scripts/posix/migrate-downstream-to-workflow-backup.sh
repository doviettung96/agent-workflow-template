#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  printf 'usage: %s <repo-path> [--backup-repo <path>] [--project-name <name>] [profile]\n' "$0" >&2
  exit 1
fi

repo_path="$1"
shift

backup_repo=""
project_name=""
profile=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --backup-repo)
      backup_repo="$2"
      shift 2
      ;;
    --project-name)
      project_name="$2"
      shift 2
      ;;
    generic|game-re)
      profile="$1"
      shift
      ;;
    *)
      printf 'unknown argument: %s\n' "$1" >&2
      exit 1
      ;;
  esac
done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
template_root="$(cd "${script_dir}/../.." && pwd)"

bash "${script_dir}/check-prereqs.sh"

python_cmd=""
if command -v python3 >/dev/null 2>&1; then
  python_cmd="python3"
elif command -v python >/dev/null 2>&1; then
  python_cmd="python"
else
  printf 'python is required for migrate-downstream-to-workflow-backup.sh\n' >&2
  exit 1
fi

update_args=("${repo_path}")
if [[ -n "${profile}" ]]; then
  update_args+=("${profile}")
fi
bash "${script_dir}/update-skills.sh" "${update_args[@]}"

args=(--repo "${repo_path}")
if [[ -n "${backup_repo}" ]]; then
  args+=(--backup-repo "${backup_repo}")
fi
if [[ -n "${project_name}" ]]; then
  args+=(--project-name "${project_name}")
fi

"${python_cmd}" "${template_root}/scripts/shared/migrate_downstream_to_workflow_backup.py" "${args[@]}"
printf 'Migrated workflow files in %s to local-only plus backup mirror sync\n' "${repo_path}"
