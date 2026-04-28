#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  printf 'usage: %s <epic-id> [worktree-path] [branch] [base-ref] [repo-path]\n' "$0" >&2
  exit 1
fi

epic_id="$1"
worktree_path="${2:-}"
branch="${3:-}"
base_ref="${4:-HEAD}"
repo_path="${5:-.}"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
shared_script="${script_dir}/../shared/start_epic_worktree.py"

python_cmd=""
if command -v python3 >/dev/null 2>&1; then
  python_cmd="python3"
elif command -v python >/dev/null 2>&1; then
  python_cmd="python"
else
  printf 'python is required for start-epic-worktree.sh\n' >&2
  exit 1
fi

args=(--source-repo "${repo_path}" --epic-id "${epic_id}" --base-ref "${base_ref}")
if [[ -n "${worktree_path}" ]]; then
  args+=(--worktree-path "${worktree_path}")
fi
if [[ -n "${branch}" ]]; then
  args+=(--branch "${branch}")
fi

"${python_cmd}" "${shared_script}" "${args[@]}"
