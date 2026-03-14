#!/usr/bin/env bash
set -euo pipefail

require_codex="${REQUIRE_CODEX:-0}"
missing=()

for cmd in git bd dolt; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    missing+=("$cmd")
  fi
done

if [[ "${require_codex}" == "1" ]] && ! command -v codex >/dev/null 2>&1; then
  printf 'warning: codex is not on PATH\n' >&2
fi

if (( ${#missing[@]} > 0 )); then
  printf 'missing required commands: %s\n' "${missing[*]}" >&2
  exit 1
fi

printf 'Required commands found: git, bd, dolt\n'
if bd setup claude --check >/dev/null 2>&1; then
  printf 'Claude Beads hooks appear to be installed.\n'
else
  printf "warning: Claude hooks were not verified. Run 'bd setup claude' if you use Claude Code.\n" >&2
fi
