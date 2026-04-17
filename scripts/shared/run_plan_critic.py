"""Run a provider-specific plan critic in a fresh isolated session."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REQUIRED_HANDOFF_KEYS = (
    "goal",
    "success_criteria",
    "constraints",
    "locked_decisions",
    "assumptions",
    "open_risks",
    "swarm_intent",
    "plan_text",
)

OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "status",
        "blocking_findings",
        "advisory_findings",
        "required_questions",
    ],
    "properties": {
        "status": {"type": "string", "enum": ["approved", "blocking"]},
        "blocking_findings": {"type": "array", "items": {"type": "string"}},
        "advisory_findings": {"type": "array", "items": {"type": "string"}},
        "required_questions": {"type": "array", "items": {"type": "string"}},
        "strengths": {"type": "array", "items": {"type": "string"}},
    },
}


@dataclass(frozen=True)
class BackendCommand:
    backend: str
    argv: list[str]
    output_path: str | None = None


def load_handoff(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    missing = [key for key in REQUIRED_HANDOFF_KEYS if key not in data]
    if missing:
        raise ValueError(f"handoff is missing required keys: {', '.join(missing)}")
    return data


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def skill_path_for_backend(root: Path, backend: str) -> Path:
    if backend == "codex":
        candidates = (
            root / ".codex" / "skills" / "plan-critic",
            root / "templates" / ".codex" / "skills" / "plan-critic",
        )
    elif backend == "claude":
        candidates = (
            root / ".claude" / "skills" / "plan-critic",
            root / "templates" / ".claude" / "skills" / "plan-critic",
        )
    else:
        raise ValueError(f"unsupported backend: {backend}")

    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"could not find plan-critic skill for backend {backend}")


def available_backends() -> set[str]:
    available: set[str] = set()
    if shutil.which("codex"):
        available.add("codex")
    if shutil.which("claude"):
        available.add("claude")
    return available


def select_backend(planner_backend: str, critic_backend: str, available: set[str]) -> str:
    if critic_backend != "auto":
        if critic_backend not in available:
            raise RuntimeError(f"requested critic backend '{critic_backend}' is not available")
        return critic_backend

    if planner_backend == "codex" and "claude" in available:
        return "claude"
    if planner_backend == "claude" and "codex" in available:
        return "codex"
    if planner_backend in available:
        return planner_backend
    for candidate in ("codex", "claude"):
        if candidate in available:
            return candidate
    raise RuntimeError("no plan critic backend is available")


def build_prompt(root: Path, backend: str, handoff: dict[str, Any]) -> str:
    skill_dir = skill_path_for_backend(root, backend)
    handoff_json = json.dumps(handoff, indent=2, ensure_ascii=True)
    if backend == "codex":
        skill_hint = f"Use $plan-critic at {skill_dir}."
    else:
        skill_hint = f"Use /plan-critic from {skill_dir} if available."

    return (
        f"{skill_hint}\n"
        "Act as an adversarial plan critic in a fresh isolated session.\n"
        "Treat the structured handoff below as the full source of truth.\n"
        "If a key detail is missing from the handoff, treat it as missing.\n"
        "Do not implement code. Do not create Beads. Return only JSON matching the required schema.\n\n"
        "<plan_handoff>\n"
        f"{handoff_json}\n"
        "</plan_handoff>\n"
    )


def make_command(root: Path, backend: str, handoff: dict[str, Any], tmpdir: Path) -> BackendCommand:
    prompt = build_prompt(root, backend, handoff)
    if backend == "codex":
        schema_path = tmpdir / "schema.json"
        output_path = tmpdir / "codex-last-message.json"
        schema_path.write_text(json.dumps(OUTPUT_SCHEMA), encoding="utf-8")
        argv = [
            "codex",
            "exec",
            "--ephemeral",
            "--sandbox",
            "read-only",
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(output_path),
            "-C",
            str(root),
            prompt,
        ]
        return BackendCommand(backend=backend, argv=argv, output_path=str(output_path))

    if backend == "claude":
        argv = [
            "claude",
            "-p",
            "--output-format",
            "json",
            "--permission-mode",
            "plan",
            "--tools",
            "",
            "--no-session-persistence",
            "--json-schema",
            json.dumps(OUTPUT_SCHEMA),
            prompt,
        ]
        return BackendCommand(backend=backend, argv=argv)

    raise ValueError(f"unsupported backend: {backend}")


def run_backend(command: BackendCommand, root: Path) -> dict[str, Any]:
    if command.backend == "codex":
        completed = subprocess.run(
            command.argv,
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"codex critic failed with exit code {completed.returncode}: {completed.stderr.strip() or completed.stdout.strip()}"
            )
        if not command.output_path:
            raise RuntimeError("codex critic did not provide an output path")
        output_path = Path(command.output_path)
        raw = output_path.read_text(encoding="utf-8").strip()
        return json.loads(raw)

    if command.backend == "claude":
        completed = subprocess.run(
            command.argv,
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"claude critic failed with exit code {completed.returncode}: {completed.stderr.strip() or completed.stdout.strip()}"
            )
        raw = completed.stdout.strip()
        parsed = json.loads(raw)
        if isinstance(parsed, dict) and "result" in parsed:
            result = parsed["result"]
            if isinstance(result, dict):
                return result
            if isinstance(result, str):
                return json.loads(result)
        if isinstance(parsed, dict):
            return parsed
        raise RuntimeError("claude critic returned an unexpected payload shape")

    raise ValueError(f"unsupported backend: {command.backend}")


def validate_result(result: dict[str, Any]) -> None:
    missing = [key for key in OUTPUT_SCHEMA["required"] if key not in result]
    if missing:
        raise RuntimeError(f"critic output is missing required fields: {', '.join(missing)}")
    if result["status"] not in {"approved", "blocking"}:
        raise RuntimeError("critic output has invalid status")
    for key in ("blocking_findings", "advisory_findings", "required_questions", "strengths"):
        if key in result and not isinstance(result[key], list):
            raise RuntimeError(f"critic output field '{key}' must be a list")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a plan critic in a fresh isolated session")
    parser.add_argument("--planner-backend", choices=("codex", "claude", "unknown"), required=True)
    parser.add_argument("--critic-backend", choices=("auto", "codex", "claude"), default="auto")
    parser.add_argument("--handoff", required=True, help="Path to a JSON handoff file")
    parser.add_argument("--dry-run", action="store_true", help="Show selected backend and command without running it")
    args = parser.parse_args()

    root = repo_root()
    handoff = load_handoff(Path(args.handoff))
    backends = available_backends()
    backend = select_backend(args.planner_backend, args.critic_backend, backends)

    with tempfile.TemporaryDirectory(prefix="plan-critic-") as tmp:
        tmpdir = Path(tmp)
        command = make_command(root, backend, handoff, tmpdir)
        if args.dry_run:
            print(
                json.dumps(
                    {
                        "selected_backend": backend,
                        "command": command.argv,
                    },
                    indent=2,
                )
            )
            return 0

        result = run_backend(command, root)
        validate_result(result)
        payload = {
            "selected_backend": backend,
            "status": result["status"],
            "blocking_findings": result.get("blocking_findings", []),
            "advisory_findings": result.get("advisory_findings", []),
            "required_questions": result.get("required_questions", []),
            "strengths": result.get("strengths", []),
        }
        print(json.dumps(payload, indent=2))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
