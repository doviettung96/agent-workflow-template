#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  printf 'usage: %s <repo-path>\n' "$0" >&2
  exit 1
fi

repo_path="$1"
template_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
skills_source="${template_root}/skills"

if [[ ! -d "${repo_path}" ]]; then
  printf 'repo path does not exist: %s\n' "${repo_path}" >&2
  exit 1
fi

# Workflow files
cp "${template_root}/templates/BEADS_WORKFLOW.md" "${repo_path}/BEADS_WORKFLOW.md"
printf 'Updated BEADS_WORKFLOW.md\n'

if [[ -d "${repo_path}/.beads" ]]; then
  cp "${template_root}/templates/PRIME.md" "${repo_path}/.beads/PRIME.md"
  printf 'Updated .beads/PRIME.md\n'
fi

# Codex skills
mkdir -p "${repo_path}/.codex/skills"
for skill_dir in "${skills_source}"/*; do
  [[ -d "${skill_dir}" ]] || continue
  skill_name="$(basename "${skill_dir}")"
  rm -rf "${repo_path}/.codex/skills/${skill_name}"
  cp -R "${skill_dir}" "${repo_path}/.codex/skills/${skill_name}"
  printf 'Updated Codex skill: %s\n' "${skill_name}"
done

# Claude skills
mkdir -p "${repo_path}/.claude/skills"
for skill_dir in "${skills_source}"/*; do
  [[ -d "${skill_dir}" ]] || continue
  skill_name="$(basename "${skill_dir}")"
  rm -rf "${repo_path}/.claude/skills/${skill_name}"
  cp -R "${skill_dir}" "${repo_path}/.claude/skills/${skill_name}"
  printf 'Updated Claude skill: %s\n' "${skill_name}"
done

printf 'Skills synced to %s\n' "${repo_path}"
