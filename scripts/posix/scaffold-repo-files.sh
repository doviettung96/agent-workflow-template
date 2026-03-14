#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  printf 'usage: %s <repo-path>\n' "$0" >&2
  exit 1
fi

repo_path="$1"
template_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

if [[ ! -d "${repo_path}" ]]; then
  printf 'repo path does not exist: %s\n' "${repo_path}" >&2
  exit 1
fi

cp "${template_root}/templates/BEADS_WORKFLOW.md" "${repo_path}/BEADS_WORKFLOW.md"
printf 'Copied BEADS_WORKFLOW.md\n'

mkdir -p "${repo_path}/.codex/skills"
rm -rf "${repo_path}/.codex/skills/build-and-test"
cp -R "${template_root}/templates/.codex/skills/build-and-test" "${repo_path}/.codex/skills/build-and-test"
printf 'Copied repo-local Codex build-and-test skill\n'

add_snippet() {
  local target_path="$1"
  local snippet_path="$2"
  local sentinel="$3"
  local snippet
  snippet="$(cat "${snippet_path}")"

  if [[ -f "${target_path}" ]]; then
    if grep -Fq "${sentinel}" "${target_path}"; then
      printf 'Snippet already present in %s\n' "${target_path}"
      return
    fi
    printf '\n\n%s\n' "${snippet}" >> "${target_path}"
    printf 'Appended snippet to %s\n' "${target_path}"
    return
  fi

  printf '%s\n' "${snippet}" > "${target_path}"
  printf 'Created %s\n' "${target_path}"
}

add_snippet "${repo_path}/AGENTS.md" "${template_root}/templates/AGENTS.snippet.md" "BEADS_WORKFLOW.md"
add_snippet "${repo_path}/CLAUDE.md" "${template_root}/templates/CLAUDE.snippet.md" 'Uses `bd` (beads/Dolt).'
