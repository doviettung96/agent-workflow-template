#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  printf 'usage: %s <repo-path> [profile]\n' "$0" >&2
  printf '  profile: generic | game-re (default: read .beads/workflow/profile.json, fall back to generic)\n' >&2
  exit 1
fi

repo_path="$1"
profile="${2:-}"
case "${profile}" in
  ""|generic|game-re) ;;
  *) printf 'invalid profile: %s (expected generic | game-re)\n' "${profile}" >&2; exit 1 ;;
esac
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

bash "${script_dir}/check-prereqs.sh"
bash "${script_dir}/scaffold-repo-files.sh" "${repo_path}" "" "${profile}"

# Resolve effective profile after scaffold (it persists profile.json).
effective="${profile}"
if [[ -z "${effective}" && -f "${repo_path}/.beads/workflow/profile.json" ]]; then
  effective="$(python - "${repo_path}/.beads/workflow/profile.json" <<'PY'
import json, sys
with open(sys.argv[1], "r", encoding="utf-8") as fh:
    print(json.load(fh).get("profile", "generic"))
PY
)"
fi
effective="${effective:-generic}"

python "${script_dir}/../shared/ensure_stage1_beads.py" "${repo_path}" --profile "${effective}"

printf 'Skills synced to %s (profile=%s)\n' "${repo_path}" "${effective}"
