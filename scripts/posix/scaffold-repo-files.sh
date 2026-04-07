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

python_cmd=""
if command -v python3 >/dev/null 2>&1; then
  python_cmd="python3"
elif command -v python >/dev/null 2>&1; then
  python_cmd="python"
else
  printf 'python is required for scaffold-repo-files.sh\n' >&2
  exit 1
fi

mkdir -p "${repo_path}"

cp "${template_root}/templates/BEADS_WORKFLOW.md" "${repo_path}/BEADS_WORKFLOW.md"
printf 'Copied BEADS_WORKFLOW.md\n'

mkdir -p "${repo_path}/.beads"
cp "${template_root}/templates/PRIME.md" "${repo_path}/.beads/PRIME.md"
cp "${template_root}/templates/.beads/.gitignore" "${repo_path}/.beads/.gitignore"
cp "${template_root}/templates/.beads/README.md" "${repo_path}/.beads/README.md"
printf 'Copied .beads/PRIME.md\n'
printf 'Copied .beads/.gitignore\n'
printf 'Copied .beads/README.md\n'

mkdir -p "${repo_path}/.beads/workflow"
if [[ -d "${template_root}/templates/.beads/workflow" ]]; then
  find "${template_root}/templates/.beads/workflow" -maxdepth 1 -type f | while read -r src; do
    name="$(basename "${src}")"
    dst="${repo_path}/.beads/workflow/${name}"
    if [[ ! -f "${dst}" ]]; then
      cp "${src}" "${dst}"
    fi
  done
  printf 'Seeded missing .beads/workflow/*\n'
else
  printf 'No .beads/workflow seed files in template; skipped\n'
fi

mkdir -p "${repo_path}/.codex/skills"
if [[ ! -d "${repo_path}/.codex/skills/build-and-test" ]]; then
  cp -R "${template_root}/templates/.codex/skills/build-and-test" "${repo_path}/.codex/skills/build-and-test"
  printf 'Copied Codex build-and-test skill\n'
else
  printf 'Preserved existing Codex build-and-test skill\n'
fi

find "${template_root}/skills" -mindepth 1 -maxdepth 1 -type d | while read -r src; do
  name="$(basename "${src}")"
  dst="${repo_path}/.codex/skills/${name}"
  rm -rf "${dst}"
  cp -R "${src}" "${dst}"
  printf 'Copied Codex skill: %s\n' "${name}"
done
rm -rf "${repo_path}/.codex/skills/start-epic-worktree"

mkdir -p "${repo_path}/.claude/skills"
if [[ ! -d "${repo_path}/.claude/skills/build-and-test" ]]; then
  cp -R "${template_root}/templates/.codex/skills/build-and-test" "${repo_path}/.claude/skills/build-and-test"
  printf 'Copied Claude build-and-test skill\n'
else
  printf 'Preserved existing Claude build-and-test skill\n'
fi

find "${template_root}/skills" -mindepth 1 -maxdepth 1 -type d | while read -r src; do
  name="$(basename "${src}")"
  dst="${repo_path}/.claude/skills/${name}"
  rm -rf "${dst}"
  cp -R "${src}" "${dst}"
  printf 'Copied Claude skill: %s\n' "${name}"
done
rm -rf "${repo_path}/.claude/skills/start-epic-worktree"

mkdir -p "${repo_path}/scripts/windows" "${repo_path}/scripts/posix" "${repo_path}/scripts/shared"
cp "${template_root}/scripts/windows/workflow-status.ps1" "${repo_path}/scripts/windows/workflow-status.ps1"
cp "${template_root}/scripts/windows/agent-mail.ps1" "${repo_path}/scripts/windows/agent-mail.ps1"
rm -f "${repo_path}/scripts/windows/shared-beads.ps1"
rm -f "${repo_path}/scripts/windows/start-epic-worktree.ps1"
cp "${template_root}/scripts/posix/workflow-status.sh" "${repo_path}/scripts/posix/workflow-status.sh"
cp "${template_root}/scripts/posix/agent-mail.sh" "${repo_path}/scripts/posix/agent-mail.sh"
rm -f "${repo_path}/scripts/posix/shared-beads.sh"
rm -f "${repo_path}/scripts/posix/start-epic-worktree.sh"
chmod +x "${repo_path}/scripts/posix/workflow-status.sh" "${repo_path}/scripts/posix/agent-mail.sh"
cp "${template_root}/scripts/shared/agent_mail.py" "${repo_path}/scripts/shared/agent_mail.py"
cp "${template_root}/scripts/shared/manage_instructions.py" "${repo_path}/scripts/shared/manage_instructions.py"
rm -f "${repo_path}/scripts/shared/shared_beads.py"
rm -f "${repo_path}/scripts/shared/start_epic_worktree.py"
printf 'Copied script helpers\n'

mkdir -p "${repo_path}/docs"
cp "${template_root}/docs/TROUBLESHOOTING.md" "${repo_path}/docs/TROUBLESHOOTING.md"
printf 'Copied docs/TROUBLESHOOTING.md\n'

"${python_cmd}" "${template_root}/scripts/shared/manage_instructions.py" "${repo_path}/AGENTS.md" "${template_root}/templates/AGENTS.snippet.md"
"${python_cmd}" "${template_root}/scripts/shared/manage_instructions.py" "${repo_path}/CLAUDE.md" "${template_root}/templates/CLAUDE.snippet.md"
printf 'Updated AGENTS.md managed block\n'
printf 'Updated CLAUDE.md managed block\n'
