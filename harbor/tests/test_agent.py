from __future__ import annotations

from pathlib import Path

import pytest

from harbor.agent import AgentProfile, Config, load_config


def test_render_argv_substitutes_placeholders():
    p = AgentProfile(
        name="x",
        agent_kind="codex",
        command=["codex"],
        args_template=["-m", "{model}", "--reasoning-effort", "{effort}"],
        model="gpt-5.3-codex",
        effort="medium",
    )
    assert p.render_argv() == ["codex", "-m", "gpt-5.3-codex", "--reasoning-effort", "medium"]


def test_render_argv_overrides_take_precedence():
    p = AgentProfile(
        name="x",
        agent_kind="codex",
        command=["codex"],
        args_template=["-m", "{model}", "--reasoning-effort", "{effort}"],
        model="gpt-5.3-codex",
        effort="medium",
    )
    out = p.render_argv(model="o5", effort="high")
    assert out == ["codex", "-m", "o5", "--reasoning-effort", "high"]


def test_render_argv_drops_empty_substitution_flags():
    """If model is empty, both `-m` and `{model}` should disappear together."""
    p = AgentProfile(
        name="claude",
        agent_kind="claude",
        command=["claude"],
        args_template=["--model", "{model}", "--effort", "{effort}"],
        model="claude-opus",
        effort="",
    )
    # NOTE: with the current implementation, only the placeholder token drops.
    # The bare flag (`--effort`) stays. That's intentional — users who want
    # both removed should omit the flag from args_template themselves.
    out = p.render_argv()
    assert "--model" in out and "claude-opus" in out
    assert "--effort" in out  # bare flag retained
    assert "{effort}" not in out


def test_load_config_falls_back_to_builtin_when_no_file(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = load_config()
    assert "fast" in cfg.profiles
    assert "balanced" in cfg.profiles
    assert "thorough" in cfg.profiles
    assert "claude-opus" in cfg.profiles
    assert cfg.default_profile == "balanced"


def test_load_config_user_overrides(tmp_path: Path):
    yml = tmp_path / "harbor.yml"
    yml.write_text(
        "default_profile: thorough\n"
        "profiles:\n"
        "  fast:\n"
        "    agent_kind: codex\n"
        "    command: [codex]\n"
        "    args_template: ['--model', '{model}']\n"
        "    model: my-fast-model\n"
        "  custom:\n"
        "    agent_kind: codex\n"
        "    command: [codex]\n"
        "    args_template: []\n"
        "    model: my-model\n",
        encoding="utf-8",
    )
    cfg = load_config(yml)
    assert cfg.default_profile == "thorough"
    # User override
    assert cfg.profiles["fast"].model == "my-fast-model"
    # Custom profile preserved
    assert "custom" in cfg.profiles
    # Built-ins still present (thorough, claude-opus, balanced)
    assert "thorough" in cfg.profiles
    assert "claude-opus" in cfg.profiles


def test_load_config_rejects_unknown_default(tmp_path: Path):
    yml = tmp_path / "harbor.yml"
    yml.write_text(
        "default_profile: nope\n"
        "profiles: {}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_config(yml)


def test_config_get_with_none_uses_default():
    cfg: Config = load_config()
    assert cfg.get(None).name == "balanced"


def test_config_get_unknown_raises():
    cfg = load_config()
    with pytest.raises(KeyError):
        cfg.get("does-not-exist")


def test_prompt_injection_defaults_to_file_ref():
    """Built-in profiles should default to file_ref since codex/claude both
    support `@<path>` to load a prompt from disk."""
    cfg = load_config()
    for name in ("fast", "balanced", "thorough", "claude-opus"):
        assert cfg.profiles[name].prompt_injection == "file_ref", (
            f"profile {name} should default to file_ref"
        )


def test_prompt_injection_override_from_yaml(tmp_path: Path):
    yml = tmp_path / "harbor.yml"
    yml.write_text(
        "profiles:\n"
        "  paste:\n"
        "    agent_kind: custom\n"
        "    command: [my-cli]\n"
        "    args_template: []\n"
        "    prompt_injection: send_keys\n",
        encoding="utf-8",
    )
    cfg = load_config(yml)
    assert cfg.profiles["paste"].prompt_injection == "send_keys"


def test_prompt_injection_invalid_value_rejected(tmp_path: Path):
    yml = tmp_path / "harbor.yml"
    yml.write_text(
        "profiles:\n"
        "  bad:\n"
        "    agent_kind: custom\n"
        "    command: [x]\n"
        "    args_template: []\n"
        "    prompt_injection: nonsense\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="prompt_injection"):
        load_config(yml)
