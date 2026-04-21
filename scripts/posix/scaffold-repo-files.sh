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

# Resolve effective profile: CLI arg > persisted profile.json > "generic" default.
profile_file="${repo_path}/.beads/workflow/profile.json"
effective_profile="${profile}"
if [[ -z "${effective_profile}" && -f "${profile_file}" ]]; then
  effective_profile="$(python - "${profile_file}" <<'PY' 2>/dev/null || true
import json, sys
try:
    with open(sys.argv[1], "r", encoding="utf-8") as fh:
        print(json.load(fh).get("profile", ""))
except Exception:
    pass
PY
)"
fi
effective_profile="${effective_profile:-generic}"
profile_gated_skills=(game-action-harness)

skill_is_profile_gated() {
  local name="$1"
  for s in "${profile_gated_skills[@]}"; do
    if [[ "${s}" == "${name}" ]]; then return 0; fi
  done
  return 1
}

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
  if skill_is_profile_gated "${name}" && [[ "${effective_profile}" != "game-re" ]]; then
    printf 'Skipped Codex skill (profile=%s): %s\n' "${effective_profile}" "${name}"
    continue
  fi
  dst="${repo_path}/.codex/skills/${name}"
  rm -rf "${dst}"
  cp -R "${src}" "${dst}"
  printf 'Copied Codex skill: %s\n' "${name}"
done
rm -rf "${repo_path}/.codex/skills/plan-debate"
rm -rf "${repo_path}/.codex/skills/plan-critic"
if [[ -d "${template_root}/templates/.codex/skills" ]]; then
  find "${template_root}/templates/.codex/skills" -mindepth 1 -maxdepth 1 -type d | while read -r src; do
    name="$(basename "${src}")"
    if [[ "${name}" == "build-and-test" ]]; then
      continue
    fi
    dst="${repo_path}/.codex/skills/${name}"
    rm -rf "${dst}"
    cp -R "${src}" "${dst}"
    printf 'Copied Codex provider skill: %s\n' "${name}"
  done
fi
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
  if skill_is_profile_gated "${name}" && [[ "${effective_profile}" != "game-re" ]]; then
    printf 'Skipped Claude skill (profile=%s): %s\n' "${effective_profile}" "${name}"
    continue
  fi
  dst="${repo_path}/.claude/skills/${name}"
  rm -rf "${dst}"
  cp -R "${src}" "${dst}"
  printf 'Copied Claude skill: %s\n' "${name}"
done
rm -rf "${repo_path}/.claude/skills/plan-debate"
rm -rf "${repo_path}/.claude/skills/plan-critic"
if [[ -d "${template_root}/templates/.claude/skills" ]]; then
  find "${template_root}/templates/.claude/skills" -mindepth 1 -maxdepth 1 -type d | while read -r src; do
    name="$(basename "${src}")"
    if [[ "${name}" == "build-and-test" ]]; then
      continue
    fi
    dst="${repo_path}/.claude/skills/${name}"
    rm -rf "${dst}"
    cp -R "${src}" "${dst}"
    printf 'Copied Claude provider skill: %s\n' "${name}"
  done
fi
rm -rf "${repo_path}/.claude/skills/start-epic-worktree"

mkdir -p "${repo_path}/scripts/windows" "${repo_path}/scripts/posix" "${repo_path}/scripts/shared"
cp "${template_root}/scripts/windows/workflow-status.ps1" "${repo_path}/scripts/windows/workflow-status.ps1"
cp "${template_root}/scripts/windows/agent-mail.ps1" "${repo_path}/scripts/windows/agent-mail.ps1"
cp "${template_root}/scripts/windows/sync-workflow-backup.ps1" "${repo_path}/scripts/windows/sync-workflow-backup.ps1"
rm -f "${repo_path}/scripts/windows/shared-beads.ps1"
rm -f "${repo_path}/scripts/windows/start-epic-worktree.ps1"
cp "${template_root}/scripts/posix/workflow-status.sh" "${repo_path}/scripts/posix/workflow-status.sh"
cp "${template_root}/scripts/posix/agent-mail.sh" "${repo_path}/scripts/posix/agent-mail.sh"
cp "${template_root}/scripts/posix/sync-workflow-backup.sh" "${repo_path}/scripts/posix/sync-workflow-backup.sh"
rm -f "${repo_path}/scripts/posix/shared-beads.sh"
rm -f "${repo_path}/scripts/posix/start-epic-worktree.sh"
chmod +x "${repo_path}/scripts/posix/workflow-status.sh" "${repo_path}/scripts/posix/agent-mail.sh" "${repo_path}/scripts/posix/sync-workflow-backup.sh"
cp "${template_root}/scripts/shared/agent_mail.py" "${repo_path}/scripts/shared/agent_mail.py"
cp "${template_root}/scripts/shared/manage_instructions.py" "${repo_path}/scripts/shared/manage_instructions.py"
cp "${template_root}/scripts/shared/target_runtime.py" "${repo_path}/scripts/shared/target_runtime.py"
rm -f "${repo_path}/scripts/shared/run_plan_critic.py"
cp "${template_root}/scripts/shared/sync_workflow_backup.py" "${repo_path}/scripts/shared/sync_workflow_backup.py"
cp "${template_root}/scripts/shared/workflow_backup.py" "${repo_path}/scripts/shared/workflow_backup.py"
rm -f "${repo_path}/scripts/shared/shared_beads.py"
rm -f "${repo_path}/scripts/shared/start_epic_worktree.py"
printf 'Copied script helpers\n'

# Profile-gated: harness runtime installs only for game-re repos.
if [[ "${effective_profile}" == "game-re" ]]; then
  cp "${template_root}/scripts/shared/harness.py" "${repo_path}/scripts/shared/harness.py"
  mkdir -p "${repo_path}/scripts/shared/harness_backends"
  find "${template_root}/scripts/shared/harness_backends" -maxdepth 1 -type f | while read -r src; do
    cp "${src}" "${repo_path}/scripts/shared/harness_backends/$(basename "${src}")"
  done
  printf 'Copied scripts/shared/harness.py and harness_backends/ (profile=game-re)\n'
fi

# Persist the effective profile so subsequent runs without --profile stay consistent.
mkdir -p "${repo_path}/.beads/workflow"
python - "${profile_file}" "${effective_profile}" <<'PY'
import json, sys
path, profile = sys.argv[1], sys.argv[2]
with open(path, "w", encoding="utf-8") as fh:
    json.dump({"version": 1, "profile": profile}, fh)
PY
printf 'Persisted profile=%s to .beads/workflow/profile.json\n' "${effective_profile}"

mkdir -p "${repo_path}/docs"
cp "${template_root}/docs/TROUBLESHOOTING.md" "${repo_path}/docs/TROUBLESHOOTING.md"
printf 'Copied docs/TROUBLESHOOTING.md\n'

"${python_cmd}" "${template_root}/scripts/shared/sync_workflow_backup.py" ensure-ignore --repo "${repo_path}"
printf 'Updated .gitignore managed workflow block\n'

"${python_cmd}" "${template_root}/scripts/shared/manage_instructions.py" "${repo_path}/AGENTS.md" "${template_root}/templates/AGENTS.snippet.md"
"${python_cmd}" "${template_root}/scripts/shared/manage_instructions.py" "${repo_path}/CLAUDE.md" "${template_root}/templates/CLAUDE.snippet.md"
printf 'Updated AGENTS.md managed block\n'
printf 'Updated CLAUDE.md managed block\n'
