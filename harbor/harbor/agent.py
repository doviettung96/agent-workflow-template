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
      - "file_ref": type `@<absolute-prompt-path>` then Enter (claude REPL).
      - "send_keys": paste the prompt body verbatim via `tmux send-keys -l` then Enter.
      - "prompt_arg": the prompt is passed as part of the launch command line —
        `launch_template` is required and must include `{prompt_path}`. Harbor
        skips the post-launch inject step entirely. Required for codex's TUI,
        which submits on Enter and so cannot accept a multi-line paste.
      - "stdin": legacy non-interactive path — the prompt goes on the agent's
        stdin via `harbor-bead-runner`. Not used by the interactive orchestrator.

    `launch_template`, if non-empty, is a literal shell command line typed into
    the pane via `send-keys` (single-line). It supports `{model}`, `{effort}`,
    and `{prompt_path}` placeholders and bypasses the argv-style command +
    args_template. This is how we get codex to accept a multi-line prompt: by
    relying on the pane's shell to substitute the prompt file contents inline,
    e.g. `codex -m {model} ... (Get-Content -Raw '{prompt_path}')` on
    PowerShell, or `codex -m {model} ... "$(cat '{prompt_path}')"` on bash.
    """

    name: str
    agent_kind: str  # "codex" | "claude" | <custom>
    command: list[str]
    args_template: list[str]
    model: str = ""
    effort: str = ""
    env: dict[str, str] = field(default_factory=dict)
    prompt_injection: str = "file_ref"
    launch_template: str = ""

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
    # Optional path to the shell tmux should use for harbor panes. On Windows
    # this defaults (auto-detected) to Git Bash so launch_templates can rely on
    # POSIX-style command substitution (`"$(cat 'path')"`) without fighting
    # PowerShell's native-arg-pass quirks. None means "use tmux's default".
    default_shell: str | None = None

    def get(self, name: str | None) -> AgentProfile:
        key = name or self.default_profile
        if key not in self.profiles:
            available = ", ".join(sorted(self.profiles))
            raise KeyError(f"unknown profile {key!r}; available: {available}")
        return self.profiles[key]


def _auto_detect_default_shell() -> str | None:
    """On Windows, prefer Git Bash so launch_templates use POSIX shell semantics.

    Returns the absolute path to bash.exe if it can be found, else None. The
    path is normalized to forward slashes — tmux (a POSIX tool ported to
    Windows) accepts forward-slash paths and silently ignores set-option calls
    that pass native backslash paths.
    """
    if os.name != "nt":
        return None
    candidates = [
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files (x86)\Git\bin\bash.exe",
    ]
    for c in candidates:
        if Path(c).exists():
            return c.replace("\\", "/")
    return None


def _profile_from_dict(name: str, raw: dict[str, Any]) -> AgentProfile:
    injection = raw.get("prompt_injection", "file_ref")
    if injection not in {"file_ref", "send_keys", "prompt_arg", "stdin"}:
        raise ValueError(
            f"profile {name!r}: prompt_injection must be one of "
            f"'file_ref', 'send_keys', 'prompt_arg', 'stdin'; got {injection!r}"
        )
    launch_template = raw.get("launch_template", "")
    if injection == "prompt_arg" and "{prompt_path}" not in launch_template:
        raise ValueError(
            f"profile {name!r}: prompt_injection='prompt_arg' requires "
            "launch_template to contain a {prompt_path} placeholder"
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
        launch_template=launch_template,
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
        return Config(
            profiles=profiles,
            default_profile="balanced",
            default_shell=_auto_detect_default_shell(),
        )

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
    # Top-level default_shell: explicit user override beats auto-detection.
    default_shell = data.get("default_shell")
    if default_shell is None:
        default_shell = _auto_detect_default_shell()
    return Config(
        profiles=profiles,
        default_profile=default,
        default_shell=default_shell,
    )


def load_issue_prefix(repo_root: str | os.PathLike[str]) -> str | None:
    """Read Beads' local issue_prefix from .beads/config.yaml if configured."""
    path = Path(repo_root) / ".beads" / "config.yaml"
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    prefix = data.get("issue_prefix") if isinstance(data, dict) else None
    if prefix is None:
        return None
    prefix_s = str(prefix).strip()
    return prefix_s or None
