#!/usr/bin/env sh
# Distribute the global agent guidelines (this repo's AGENTS.md) and init LESSONS.md.
#
# The repo's AGENTS.md is the single source of truth for general guidelines. This script
# symlinks the global instruction files to it and initializes lessons stores. It NEVER
# creates or edits a project's own AGENTS.md — that is the project's responsibility.
#
# Usage:
#   bootstrap-agent-config.sh --global                 # once per machine
#   bootstrap-agent-config.sh --project <repo>         # per project
#   bootstrap-agent-config.sh --global --project <repo>
set -eu

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MASTER="$REPO_ROOT/AGENTS.md"
[ -f "$MASTER" ] || { echo "Master AGENTS.md not found: $MASTER" >&2; exit 1; }

DO_GLOBAL=0
PROJECT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --global)  DO_GLOBAL=1; shift ;;
    --project) PROJECT="${2:?--project needs a path}"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 1 ;;
  esac
done
[ "$DO_GLOBAL" -eq 1 ] || [ -n "$PROJECT" ] || { echo "Nothing to do. Pass --global and/or --project <repo>." >&2; exit 1; }

lessons_if_missing() {
  if [ -f "$1" ]; then echo "  kept    $1 (exists)"; return; fi
  mkdir -p "$(dirname "$1")"
  cat > "$1" <<'EOF'
# Lessons Learned

Gotchas worth never hitting twice. Read before debugging (grep by error text or tag);
append after resolving a non-obvious error. One atomic entry each, newest on top.

Format:
```
### <one-line title>
- Date: YYYY-MM-DD
- Symptom: what was observed (paste the actual error text)
- Root cause: why it really happened
- Rule: what to do — and what never to do again
- Tags: #build #windows #flaky #async ...
```

---

<!-- Add lessons below this line -->
EOF
  echo "  created $1"
}

if [ "$DO_GLOBAL" -eq 1 ]; then
  echo "Global setup:"
  # Each agent's global instruction file links straight to the master. Add more agents here.
  for link in "$HOME/.claude/CLAUDE.md" "$HOME/.codex/AGENTS.md"; do
    mkdir -p "$(dirname "$link")"
    ln -sf "$MASTER" "$link"; echo "  linked  $link -> $MASTER"
  done
  lessons_if_missing "$HOME/.agents/LESSONS.md"
fi

if [ -n "$PROJECT" ]; then
  PROJ="$(cd "$PROJECT" && pwd)"
  echo "Project setup: $PROJ"
  lessons_if_missing "$PROJ/LESSONS.md"
  if [ -f "$PROJ/AGENTS.md" ]; then
    # Relative in-repo target so the link survives clone/move.
    ( cd "$PROJ" && ln -sf "AGENTS.md" "CLAUDE.md" )
    echo "  linked  $PROJ/CLAUDE.md -> AGENTS.md"
  else
    echo "  SKIP CLAUDE.md — no project AGENTS.md yet. The project owns its AGENTS.md;"
    echo "       create it, then re-run with --project to link CLAUDE.md."
  fi
fi

echo "Done."
