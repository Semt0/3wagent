"""Load qwen-agent LLM settings from a provider-oriented YAML file."""

import copy
import os
from pathlib import Path
from typing import Any, Dict, Optional, Union

import yaml

# Register the strict OpenAI-compatible transport before Qwen-Agent resolves
# provider configs by model_type.
from src.llm.strict_oai import StrictOpenAICompatibleModel  # noqa: F401

DEFAULT_CONFIG_PATH = Path(__file__).with_name("llm.yaml")

# The provider config of the currently running agent, recorded at startup so
# tool-layer helpers (e.g. the search-result judge) can build an LLM on the
# same provider without threading the config through tool construction.
_active_llm_config: Optional[Dict[str, Any]] = None


def get_active_llm_config() -> Optional[Dict[str, Any]]:
    """The config most recently produced by ``load_llm_config`` (or None)."""
    return copy.deepcopy(_active_llm_config) if _active_llm_config else None


def _read_config(config_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    with path.open(encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file) or {}

    if not isinstance(config, dict) or not isinstance(config.get("providers"), dict):
        raise ValueError(f"Invalid LLM config: {path} must contain a providers mapping")
    return config


def available_providers(config_path: Optional[Union[str, Path]] = None) -> list[str]:
    """Return provider names available in the selected config file."""
    return list(_read_config(config_path)["providers"])


def load_llm_config(
    model_name: Optional[str] = None,
    provider: Optional[str] = None,
    config_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Build the qwen-agent config for one provider.

    ``provider`` and ``model_name`` override the YAML defaults.  API keys are
    resolved from ``api_key_env`` at runtime so they never need to be committed.
    ``LLM_PROVIDER`` is also accepted as a convenient environment override.
    """
    config = _read_config(config_path)
    selected_provider = provider or os.getenv("LLM_PROVIDER") or config.get("default_provider")
    providers = config["providers"]
    if not selected_provider:
        raise ValueError("No LLM provider selected and default_provider is not configured")
    if selected_provider not in providers:
        names = ", ".join(providers)
        raise ValueError(f"Unknown LLM provider '{selected_provider}'. Available: {names}")

    provider_config = copy.deepcopy(providers[selected_provider])
    if not isinstance(provider_config, dict):
        raise ValueError(f"Invalid configuration for LLM provider '{selected_provider}'")

    api_key_env = provider_config.pop("api_key_env", None)
    if api_key_env:
        api_key = os.getenv(api_key_env)
        if not api_key:
            raise RuntimeError(
                f"Missing API key for provider '{selected_provider}'. "
                f"Set the {api_key_env} environment variable."
            )
        provider_config["api_key"] = api_key
    elif not provider_config.get("api_key"):
        raise RuntimeError(
            f"Provider '{selected_provider}' must define api_key or api_key_env"
        )

    if model_name:
        provider_config["model"] = model_name
    if not provider_config.get("model") or not provider_config.get("model_server"):
        raise ValueError(
            f"Provider '{selected_provider}' must define both model and model_server"
        )
    global _active_llm_config
    _active_llm_config = copy.deepcopy(provider_config)
    return provider_config
