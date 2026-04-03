#!/usr/bin/env bash
set -euo pipefail

require_codex="${REQUIRE_CODEX:-0}"
missing=()

for cmd in git br; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    missing+=("$cmd")
  fi
done

if [[ "${require_codex}" == "1" ]] && ! command -v codex >/dev/null 2>&1; then
  printf 'warning: codex is not on PATH\n' >&2
fi

if ! command -v python3 >/dev/null 2>&1 && ! command -v python >/dev/null 2>&1; then
  missing+=("python")
fi

if (( ${#missing[@]} > 0 )); then
  printf 'missing required commands: %s\n' "${missing[*]}" >&2
  exit 1
fi

printf 'Required commands found: git, br, python\n'
