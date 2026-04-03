#!/usr/bin/env bash
set -euo pipefail

repo_path="${1:-.}"
repo_root="$(cd "${repo_path}" && pwd)"
workflow_root="${repo_root}/.beads/workflow"
state_path="${workflow_root}/state.json"
handoff_path="${workflow_root}/HANDOFF.json"
summary_path="${workflow_root}/STATE.md"
agent_mail_script="${repo_root}/scripts/posix/agent-mail.sh"

printf 'Repo: %s\n' "${repo_root}"

python_cmd=""
if command -v python3 >/dev/null 2>&1; then
  python_cmd="python3"
elif command -v python >/dev/null 2>&1; then
  python_cmd="python"
fi

if [[ ! -d "${workflow_root}" ]]; then
  printf 'Workflow state: not scaffolded in this worktree\n'
elif [[ -n "${python_cmd}" && -f "${state_path}" ]]; then
  "${python_cmd}" - "${state_path}" "${handoff_path}" <<'PY'
import json
import sys

state_path, handoff_path = sys.argv[1], sys.argv[2]

def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        print(f"warning: failed to parse JSON: {path}")
        return None

state = load_json(state_path)
handoff = load_json(handoff_path)

if state is None:
    print("state.json: missing or invalid")
else:
    print(f"Mode: {state.get('mode') or 'unknown'}")
    print(f"Epic: {state.get('epic_id') or 'none'}")
    print(f"Branch: {state.get('branch') or 'unknown'}")
    print(f"Worktree: {state.get('worktree_path') or 'unknown'}")
    print(f"Coordinator: {state.get('coordinator') or 'none'}")

    workers = state.get("workers") or []
    if workers:
        print("Workers:")
        for worker in workers:
            line = f"- {worker.get('name') or 'unnamed'}"
            if worker.get("status"):
                line += f" [{worker['status']}]"
            if worker.get("bead_id"):
                line += f" bead={worker['bead_id']}"
            print(line)
    else:
        print("Workers: none")

    reservations = state.get("reservations") or []
    if reservations:
        print("Local reservations:")
        for reservation in reservations:
            line = f"- {reservation.get('path') or 'unknown-path'}"
            if reservation.get("owner"):
                line += f" owner={reservation['owner']}"
            if reservation.get("bead_id"):
                line += f" bead={reservation['bead_id']}"
            print(line)
    else:
        print("Local reservations: none")

    blockers = state.get("blockers") or []
    if blockers:
        print("Blockers:")
        for blocker in blockers:
            if isinstance(blocker, str):
                print(f"- {blocker}")
                continue
            line = f"- {blocker.get('summary') or 'unspecified blocker'}"
            if blocker.get("bead_id"):
                line += f" bead={blocker['bead_id']}"
            print(line)
    else:
        print("Blockers: none")

    print(f"Last action: {state.get('last_action') or 'none'}")
    print(f"Next action: {state.get('next_action') or 'none'}")

if handoff and (
    handoff.get("role")
    or handoff.get("bead_id")
    or handoff.get("summary")
    or (handoff.get("status") and handoff.get("status") != "idle")
):
    print(f"Handoff role: {handoff.get('role') or 'unknown'}")
    print(f"Handoff bead: {handoff.get('bead_id') or 'none'}")
    print(f"Handoff next action: {handoff.get('next_action') or 'none'}")
else:
    print("Handoff: none")
PY
else
  printf 'state.json: missing or Python unavailable\n'
  if [[ -f "${handoff_path}" ]]; then
    printf 'Handoff: present\n'
  else
    printf 'Handoff: none\n'
  fi
fi

if [[ -f "${summary_path}" ]]; then
  printf 'STATE.md: present\n'
else
  printf 'STATE.md: missing\n'
fi

epic_id=""
if [[ -n "${python_cmd}" && -f "${state_path}" ]]; then
  epic_id="$("${python_cmd}" - "${state_path}" <<'PY'
import json
import sys

try:
    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)
except Exception:
    raise SystemExit(0)

value = data.get("epic_id")
if value:
    print(value)
PY
)"
fi

if command -v br >/dev/null 2>&1 && [[ -n "${epic_id}" ]]; then
  ready_json="$(RUST_LOG=error br ready --parent "${epic_id}" --json 2>/dev/null || true)"
  if [[ -z "${ready_json}" ]]; then
    printf 'Ready descendants: none\n'
  elif [[ -n "${python_cmd}" ]]; then
    READY_JSON="${ready_json}" "${python_cmd}" - <<'PY'
import json
import os

raw = os.environ.get("READY_JSON", "")
try:
    data = json.loads(raw)
except json.JSONDecodeError:
    print("Ready descendants: failed to parse")
    raise SystemExit(0)

items = data if isinstance(data, list) else [data]
if not items:
    print("Ready descendants: none")
else:
    print("Ready descendants:")
    for item in items:
        line = f"- {item.get('id') or 'unknown-id'}"
        if item.get("title"):
            line += f": {item['title']}"
        print(line)
PY
  else
    printf 'Ready descendants JSON:\n%s\n' "${ready_json}"
  fi
else
  printf 'Ready descendants: skipped\n'
fi

if [[ -x "${agent_mail_script}" && -n "${python_cmd}" ]]; then
  mail_json="$("${agent_mail_script}" --repo "${repo_root}" status 2>/dev/null || true)"
  if [[ -n "${mail_json}" ]]; then
    MAIL_JSON="${mail_json}" "${python_cmd}" - <<'PY'
import json
import os

raw = os.environ.get("MAIL_JSON", "")
try:
    data = json.loads(raw)
except json.JSONDecodeError:
    print("Shared control plane: failed to parse")
    raise SystemExit(0)

if not data.get("ok"):
    print("Shared control plane: unavailable")
    raise SystemExit(0)

print(f"Shared control plane: {data.get('root') or 'unknown'}")
print(f"Git common dir: {data.get('git_common_dir') or 'unknown'}")
print(f"Agent Mail threads: {data.get('thread_count') or 0}")

locks = data.get("epic_locks") or []
if locks:
    print("Shared epic locks:")
    for item in locks:
        print(f"- epic={item.get('epic_id') or 'unknown'} owner={item.get('owner') or 'unknown'}")
else:
    print("Shared epic locks: none")

reservations = data.get("reservations") or []
if reservations:
    print("Shared reservations:")
    for item in reservations:
        line = f"- {item.get('path') or 'unknown-path'} owner={item.get('owner') or 'unknown'}"
        if item.get("bead_id"):
            line += f" bead={item['bead_id']}"
        print(line)
else:
    print("Shared reservations: none")
PY
  else
    printf 'Shared control plane: unavailable\n'
  fi
else
  printf 'Shared control plane: unavailable\n'
fi
