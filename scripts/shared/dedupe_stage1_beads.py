#!/usr/bin/env python3
"""Remove duplicate stage-1 follow-up beads from br JSONL state."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

STAGE1_TITLES = {
    "Configure target runtime for this repo",
    "Specialize build-and-test for this repo",
    "Populate action catalog for this repo",
}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Remove duplicate stage-1 beads from .beads/issues.jsonl")
    parser.add_argument("--repo", required=True, help="Repo root")
    args = parser.parse_args(argv)

    repo_root = Path(args.repo).resolve()
    issues_path = repo_root / ".beads" / "issues.jsonl"
    raw_lines = issues_path.read_text(encoding="utf-8").splitlines()

    entries: list[dict[str, object]] = []
    for index, line in enumerate(raw_lines, start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"invalid JSON on line {index}: {exc}")
        if isinstance(payload, dict):
            entries.append(payload)

    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for entry in entries:
        title = entry.get("title")
        if isinstance(title, str) and title in STAGE1_TITLES:
            grouped[title].append(entry)

    remove_ids: set[str] = set()
    for title, group in grouped.items():
        if len(group) < 2:
            continue
        authored = [entry for entry in group if str(entry.get("created_by") or "") != "unknown"]
        if not authored:
            continue
        for entry in group:
            issue_id = str(entry.get("id") or "")
            if issue_id and str(entry.get("created_by") or "") == "unknown":
                remove_ids.add(issue_id)

    if not remove_ids:
        print(json.dumps({"ok": True, "removed_ids": []}, indent=2, sort_keys=True))
        return 0

    kept_lines: list[str] = []
    for line in raw_lines:
        if not line.strip():
            continue
        payload = json.loads(line)
        if isinstance(payload, dict) and str(payload.get("id") or "") in remove_ids:
            continue
        kept_lines.append(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))

    issues_path.write_text("\n".join(kept_lines) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "removed_ids": sorted(remove_ids)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
