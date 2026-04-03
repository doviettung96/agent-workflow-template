#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  printf 'usage: %s <repo-path> [prefix]\n' "$0" >&2
  exit 1
fi

repo_path="$1"
explicit_prefix="${2:-}"
template_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
skills_source="${template_root}/skills"
workflow_state_source="${template_root}/templates/.beads/workflow"
python_cmd=""

if command -v python3 >/dev/null 2>&1; then
  python_cmd="python3"
elif command -v python >/dev/null 2>&1; then
  python_cmd="python"
else
  printf 'python is required for scaffold-repo-files.sh\n' >&2
  exit 1
fi

if [[ ! -d "${repo_path}" ]]; then
  printf 'repo path does not exist: %s\n' "${repo_path}" >&2
  exit 1
fi

detect_prefix() {
  local repo="$1"
  local provided="$2"
  local config_path="$repo/.beads/config.yaml"

  if [[ -n "${provided}" ]]; then
    printf '%s\n' "${provided}"
    return
  fi

  if [[ -f "${config_path}" ]]; then
    local existing
    existing="$(sed -nE 's/^[[:space:]]*issue_prefix:[[:space:]]*"?([^"#]+)"?.*$/\1/p' "${config_path}" | head -n 1)"
    if [[ -n "${existing}" ]]; then
      printf '%s\n' "${existing}"
      return
    fi
  fi

  printf '%s\n' "$(basename "${repo}" | tr '[:upper:]' '[:lower:]')"
}

write_br_config() {
  local config_path="$1"
  local prefix="$2"
  cat > "${config_path}" <<EOF
# Beads Project Configuration
issue_prefix: ${prefix}
no-db: true
EOF
}

prefix="$(detect_prefix "${repo_path}" "${explicit_prefix}")"

cp "${template_root}/templates/BEADS_WORKFLOW.md" "${repo_path}/BEADS_WORKFLOW.md"
printf 'Copied BEADS_WORKFLOW.md\n'

if [[ -d "${repo_path}/.beads" ]]; then
  cp "${template_root}/templates/PRIME.md" "${repo_path}/.beads/PRIME.md"
  cp "${template_root}/templates/.beads/.gitignore" "${repo_path}/.beads/.gitignore"
  cp "${template_root}/templates/.beads/metadata.json" "${repo_path}/.beads/metadata.json"
  cp "${template_root}/templates/.beads/README.md" "${repo_path}/.beads/README.md"
  write_br_config "${repo_path}/.beads/config.yaml" "${prefix}"
  [[ -f "${repo_path}/.beads/issues.jsonl" ]] || : > "${repo_path}/.beads/issues.jsonl"
  printf 'Copied .beads/PRIME.md\n'
  printf 'Copied .beads/.gitignore\n'
  printf 'Copied .beads/metadata.json\n'
  printf 'Copied .beads/README.md\n'
  printf 'Updated .beads/config.yaml\n'

  mkdir -p "${repo_path}/.beads/workflow"
  for workflow_file in "${workflow_state_source}/"*; do
    [[ -f "${workflow_file}" ]] || continue
    destination="${repo_path}/.beads/workflow/$(basename "${workflow_file}")"
    if [[ ! -e "${destination}" ]]; then
      cp "${workflow_file}" "${destination}"
    fi
  done
  printf 'Seeded missing .beads/workflow/*\n'
fi

mkdir -p "${repo_path}/.codex/skills"
rm -rf "${repo_path}/.codex/skills/build-and-test"
cp -R "${template_root}/templates/.codex/skills/build-and-test" "${repo_path}/.codex/skills/build-and-test"
printf 'Copied Codex build-and-test skill\n'

for skill_dir in "${skills_source}"/*; do
  [[ -d "${skill_dir}" ]] || continue
  skill_name="$(basename "${skill_dir}")"
  rm -rf "${repo_path}/.codex/skills/${skill_name}"
  cp -R "${skill_dir}" "${repo_path}/.codex/skills/${skill_name}"
  printf 'Copied Codex skill: %s\n' "${skill_name}"
done

mkdir -p "${repo_path}/.claude/skills"
for skill_dir in "${skills_source}"/*; do
  [[ -d "${skill_dir}" ]] || continue
  skill_name="$(basename "${skill_dir}")"
  rm -rf "${repo_path}/.claude/skills/${skill_name}"
  cp -R "${skill_dir}" "${repo_path}/.claude/skills/${skill_name}"
  printf 'Copied Claude skill: %s\n' "${skill_name}"
done

mkdir -p "${repo_path}/scripts/windows"
cp "${template_root}/scripts/windows/workflow-status.ps1" "${repo_path}/scripts/windows/workflow-status.ps1"
cp "${template_root}/scripts/windows/agent-mail.ps1" "${repo_path}/scripts/windows/agent-mail.ps1"
cp "${template_root}/scripts/windows/start-epic-worktree.ps1" "${repo_path}/scripts/windows/start-epic-worktree.ps1"
printf 'Copied scripts/windows/workflow-status.ps1\n'
printf 'Copied scripts/windows/agent-mail.ps1\n'
printf 'Copied scripts/windows/start-epic-worktree.ps1\n'

mkdir -p "${repo_path}/scripts/posix"
cp "${template_root}/scripts/posix/workflow-status.sh" "${repo_path}/scripts/posix/workflow-status.sh"
cp "${template_root}/scripts/posix/agent-mail.sh" "${repo_path}/scripts/posix/agent-mail.sh"
cp "${template_root}/scripts/posix/start-epic-worktree.sh" "${repo_path}/scripts/posix/start-epic-worktree.sh"
chmod +x "${repo_path}/scripts/posix/workflow-status.sh"
chmod +x "${repo_path}/scripts/posix/agent-mail.sh"
chmod +x "${repo_path}/scripts/posix/start-epic-worktree.sh"
printf 'Copied scripts/posix/workflow-status.sh\n'
printf 'Copied scripts/posix/agent-mail.sh\n'
printf 'Copied scripts/posix/start-epic-worktree.sh\n'

mkdir -p "${repo_path}/scripts/shared"
cp "${template_root}/scripts/shared/agent_mail.py" "${repo_path}/scripts/shared/agent_mail.py"
cp "${template_root}/scripts/shared/start_epic_worktree.py" "${repo_path}/scripts/shared/start_epic_worktree.py"
cp "${template_root}/scripts/shared/manage_instructions.py" "${repo_path}/scripts/shared/manage_instructions.py"
printf 'Copied scripts/shared/agent_mail.py\n'
printf 'Copied scripts/shared/start_epic_worktree.py\n'
printf 'Copied scripts/shared/manage_instructions.py\n'

"${python_cmd}" "${template_root}/scripts/shared/manage_instructions.py" "${repo_path}/AGENTS.md" "${template_root}/templates/AGENTS.snippet.md"
printf 'Updated AGENTS.md managed block\n'
"${python_cmd}" "${template_root}/scripts/shared/manage_instructions.py" "${repo_path}/CLAUDE.md" "${template_root}/templates/CLAUDE.snippet.md"
printf 'Updated CLAUDE.md managed block\n'
