"""Tests for provider-based LLM configuration."""

from pathlib import Path

import pytest

from src.config.llm import available_providers, load_llm_config


CONFIG_PATH = Path(__file__).parents[1] / "src" / "config" / "llm.yaml"


def test_builtin_providers_are_available():
    assert available_providers(CONFIG_PATH) == ["deepseek", "kimi", "local"]


def test_default_provider_is_local():
    config = load_llm_config(config_path=CONFIG_PATH)
    assert config["model"] == "finance-27b"
    assert config["api_key"] == "EMPTY"


def test_local_provider_uses_yaml_defaults():
    config = load_llm_config(provider="local", config_path=CONFIG_PATH)
    assert config["model"] == "finance-27b"
    assert config["model_server"] == "http://127.0.0.1:11434/v1"
    assert config["api_key"] == "EMPTY"


def test_provider_model_can_be_overridden(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    config = load_llm_config(
        provider="deepseek", model_name="custom-model", config_path=CONFIG_PATH
    )
    assert config["model"] == "custom-model"
    assert config["api_key"] == "test-key"
    assert "api_key_env" not in config


def test_external_provider_requires_api_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
        load_llm_config(provider="deepseek", config_path=CONFIG_PATH)
