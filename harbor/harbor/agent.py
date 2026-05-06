"""Agent profiles: which CLI to launch with which model + reasoning effort.

Loaded from `harbor.yml` if present, else falls back to a small set of built-in
profiles. The single point of model/effort selection that the user can override
per-bead in the webview.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class AgentProfile:
    """One named profile in harbor.yml. Maps a {profile-name} -> agent CLI invocation.

    `args_template` may contain `{model}` and `{effort}` placeholders. Anything
    else stays literal. Empty values render as empty strings — caller filters
    them out so optional flags can drop cleanly.

    `prompt_injection` controls how harbor pushes the worker prompt into the
    interactive pane after launching the agent CLI:
      - "file_ref": type `@<absolute-prompt-path>` then Enter (codex/claude REPL).
      - "send_keys": paste the prompt body verbatim via `tmux send-keys -l` then Enter.
      - "stdin": legacy non-interactive path — the prompt goes on the agent's
        stdin via `harbor-bead-runner`. Not used by the interactive orchestrator.
    """

    name: str
    agent_kind: str  # "codex" | "claude" | <custom>
    command: list[str]
    args_template: list[str]
    model: str = ""
    effort: str = ""
    env: dict[str, str] = field(default_factory=dict)
    prompt_injection: str = "file_ref"

    def render_argv(self, *, model: str | None = None, effort: str | None = None) -> list[str]:
        """Return the full argv to exec, with model/effort substituted."""
        m = model if model is not None else self.model
        e = effort if effort is not None else self.effort
        rendered: list[str] = []
        for tok in self.args_template:
            sub = tok.format(model=m, effort=e)
            if "{" in tok and not sub:
                # Placeholder resolved to empty — drop the flag.
                continue
            rendered.append(sub)
        return [*self.command, *rendered]


# Built-in defaults so harbor works before the user creates a harbor.yml.
# Args reflect the most common codex/claude CLI shapes; users override via
# harbor.yml when their CLIs disagree.
_BUILTIN: dict[str, dict[str, Any]] = {
    "fast": {
        "agent_kind": "codex",
        "command": ["codex"],
        "args_template": ["-m", "{model}", "--reasoning-effort", "{effort}"],
        "model": "gpt-5.3-codex",
        "effort": "low",
    },
    "balanced": {
        "agent_kind": "codex",
        "command": ["codex"],
        "args_template": ["-m", "{model}", "--reasoning-effort", "{effort}"],
        "model": "gpt-5.3-codex",
        "effort": "medium",
    },
    "thorough": {
        "agent_kind": "codex",
        "command": ["codex"],
        "args_template": ["-m", "{model}", "--reasoning-effort", "{effort}"],
        "model": "gpt-5.3-codex",
        "effort": "high",
    },
    "claude-opus": {
        "agent_kind": "claude",
        "command": ["claude"],
        "args_template": ["--model", "{model}", "--dangerously-skip-permissions"],
        "model": "claude-opus-4-7",
        "effort": "",
    },
}


@dataclass(frozen=True)
class Config:
    profiles: dict[str, AgentProfile]
    default_profile: str

    def get(self, name: str | None) -> AgentProfile:
        key = name or self.default_profile
        if key not in self.profiles:
            available = ", ".join(sorted(self.profiles))
            raise KeyError(f"unknown profile {key!r}; available: {available}")
        return self.profiles[key]


def _profile_from_dict(name: str, raw: dict[str, Any]) -> AgentProfile:
    injection = raw.get("prompt_injection", "file_ref")
    if injection not in {"file_ref", "send_keys", "stdin"}:
        raise ValueError(
            f"profile {name!r}: prompt_injection must be one of "
            "'file_ref', 'send_keys', 'stdin'; got {injection!r}"
        )
    return AgentProfile(
        name=name,
        agent_kind=raw.get("agent_kind") or raw.get("agent") or "codex",
        command=list(raw["command"]),
        args_template=list(raw.get("args_template", [])),
        model=raw.get("model", ""),
        effort=raw.get("effort", ""),
        env=dict(raw.get("env", {})),
        prompt_injection=injection,
    )


def load_config(path: str | os.PathLike[str] | None = None) -> Config:
    """Load harbor.yml from `path`, else look for ./harbor.yml, else use built-ins."""
    if path is not None:
        p = Path(path)
    else:
        candidate = Path.cwd() / "harbor.yml"
        p = candidate if candidate.exists() else None  # type: ignore[assignment]

    if p is None:
        # Pure built-in defaults.
        profiles = {name: _profile_from_dict(name, raw) for name, raw in _BUILTIN.items()}
        return Config(profiles=profiles, default_profile="balanced")

    with open(p, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}

    raw_profiles = data.get("profiles") or {}
    profiles: dict[str, AgentProfile] = {
        name: _profile_from_dict(name, raw) for name, raw in raw_profiles.items()
    }
    # Fill in any built-ins the user didn't override (so `fast` etc. always exist).
    for name, raw in _BUILTIN.items():
        profiles.setdefault(name, _profile_from_dict(name, raw))

    default = data.get("default_profile") or "balanced"
    if default not in profiles:
        raise ValueError(
            f"default_profile {default!r} not found among profiles {sorted(profiles)}"
        )
    return Config(profiles=profiles, default_profile=default)
