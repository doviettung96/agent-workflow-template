#!/usr/bin/env bash
set -euo pipefail

template_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
codex_home="${CODEX_HOME:-$HOME/.codex}"
source_root="${template_root}/skills"
dest_root="${codex_home}/skills"
force="${FORCE_INSTALL:-0}"

mkdir -p "${dest_root}"

for skill_dir in "${source_root}"/*; do
  [[ -d "${skill_dir}" ]] || continue
  skill_name="$(basename "${skill_dir}")"
  destination="${dest_root}/${skill_name}"

  if [[ -e "${destination}" && "${force}" != "1" ]]; then
    printf 'warning: skipping existing skill %s\n' "${destination}" >&2
    continue
  fi

  rm -rf "${destination}"
  cp -R "${skill_dir}" "${destination}"
  printf 'Installed %s to %s\n' "${skill_name}" "${destination}"
done

printf 'Restart Codex to pick up new skills.\n'
