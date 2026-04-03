#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  printf 'usage: %s <repo-path> [prefix]\n' "$0" >&2
  exit 1
fi

repo_path="$1"
explicit_prefix="${2:-}"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

for cmd in git br bd; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    printf 'missing required command: %s\n' "$cmd" >&2
    exit 1
  fi
done

if command -v python3 >/dev/null 2>&1; then
  python_cmd="python3"
elif command -v python >/dev/null 2>&1; then
  python_cmd="python"
else
  printf 'python is required for migration\n' >&2
  exit 1
fi

if [[ ! -d "${repo_path}" ]]; then
  printf 'repo path does not exist: %s\n' "${repo_path}" >&2
  exit 1
fi

if [[ ! -d "${repo_path}/.beads" ]]; then
  printf 'repo does not contain .beads/: %s\n' "${repo_path}" >&2
  exit 1
fi

tmp_dir="$(mktemp -d)"
trap 'rm -rf "${tmp_dir}"' EXIT
export_path="${tmp_dir}/issues.jsonl"

detect_prefix() {
  local repo="$1"
  local provided="$2"
  if [[ -n "${provided}" ]]; then
    printf '%s\n' "${provided}"
    return
  fi

  local from_where
  from_where="$(cd "${repo}" && bd where 2>/dev/null | sed -nE 's/^  prefix: (.+)$/\1/p' | head -n 1)"
  if [[ -n "${from_where}" ]]; then
    printf '%s\n' "${from_where}"
    return
  fi

  if [[ -f "${repo}/.beads/config.yaml" ]]; then
    local from_config
    from_config="$(sed -nE 's/^[[:space:]]*issue[-_]prefix:[[:space:]]*"?([^"#]+)"?.*$/\1/p' "${repo}/.beads/config.yaml" | head -n 1)"
    if [[ -n "${from_config}" ]]; then
      printf '%s\n' "${from_config}"
      return
    fi
  fi

  printf '%s\n' "$(basename "${repo}" | tr '[:upper:]' '[:lower:]')"
}

prefix="$(detect_prefix "${repo_path}" "${explicit_prefix}")"

printf 'Exporting existing bd issue state from %s\n' "${repo_path}"
(cd "${repo_path}" && bd export -o "${export_path}")

printf 'Initializing br with prefix %s\n' "${prefix}"
(cd "${repo_path}" && br init --force --prefix "${prefix}")

cp "${export_path}" "${repo_path}/.beads/issues.jsonl"

rm -rf "${repo_path}/.beads/dolt"
rm -rf "${repo_path}/.beads/hooks"
rm -rf "${repo_path}/.beads/backup"
rm -f "${repo_path}/.beads/.local_version"
rm -f "${repo_path}/.beads/dolt-access.lock"
rm -f "${repo_path}/.beads/dolt-server.lock"
rm -f "${repo_path}/.beads/dolt-server.log"
rm -f "${repo_path}/.beads/dolt-server.pid"
rm -f "${repo_path}/.beads/dolt-server.port"
rm -f "${repo_path}/.beads/redirect"

"${script_dir}/scaffold-repo-files.sh" "${repo_path}" "${prefix}"

printf 'Smoke-checking migrated repo with br list --json\n'
(cd "${repo_path}" && br list --json >/dev/null)

printf 'Migration complete for %s\n' "${repo_path}"
