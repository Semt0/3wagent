"""Configuration for the local web-search service.

The agent normally starts and manages a localhost-only open-websearch daemon.
Configuration is loaded when a tool/client is constructed rather than at module
import time so tests and alternate deployments can inject their own settings.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse

_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _env_bool(environ: dict[str, str], name: str, default: bool = False) -> bool:
    value = environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(
    environ: dict[str, str],
    name: str,
    default: int,
    *,
    minimum: int,
    maximum: int,
) -> int:
    raw = environ.get(name)
    try:
        value = int(raw) if raw is not None else default
    except ValueError:
        value = default
    return max(minimum, min(value, maximum))


@dataclass(frozen=True)
class WebSearchSettings:
    """Runtime settings for the open-websearch adapter."""

    base_url: str = "http://127.0.0.1:3210"
    timeout_seconds: int = 30
    max_results: int = 10
    max_fetch_chars: int = 8_000
    fallback_to_searxng: bool = False
    allow_remote_service: bool = False
    auto_start: bool = True
    startup_timeout_seconds: int = 15

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> WebSearchSettings:
        env = dict(os.environ if environ is None else environ)
        allow_remote = _env_bool(env, "OPEN_WEBSEARCH_ALLOW_REMOTE", False)
        base_url = env.get("OPEN_WEBSEARCH_URL", cls.base_url).strip().rstrip("/")
        _validate_base_url(base_url, allow_remote=allow_remote)
        return cls(
            base_url=base_url,
            timeout_seconds=_env_int(
                env, "WEBSEARCH_TIMEOUT_SECONDS", cls.timeout_seconds, minimum=1, maximum=120
            ),
            max_results=_env_int(
                env, "WEBSEARCH_MAX_RESULTS", cls.max_results, minimum=1, maximum=50
            ),
            max_fetch_chars=_env_int(
                env,
                "WEBFETCH_MAX_CHARS",
                cls.max_fetch_chars,
                minimum=1_000,
                maximum=8_000,
            ),
            fallback_to_searxng=_env_bool(env, "WEBSEARCH_FALLBACK_TO_SEARXNG", False),
            allow_remote_service=allow_remote,
            auto_start=_env_bool(env, "OPEN_WEBSEARCH_AUTOSTART", True),
            startup_timeout_seconds=_env_int(
                env,
                "OPEN_WEBSEARCH_STARTUP_TIMEOUT_SECONDS",
                cls.startup_timeout_seconds,
                minimum=1,
                maximum=120,
            ),
        )


def _validate_base_url(base_url: str, *, allow_remote: bool) -> None:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("OPEN_WEBSEARCH_URL must be an HTTP(S) URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("OPEN_WEBSEARCH_URL must not contain credentials, query, or fragment")
    if not allow_remote and parsed.hostname.lower() not in _LOCAL_HOSTS:
        raise ValueError(
            "OPEN_WEBSEARCH_URL must point to localhost unless OPEN_WEBSEARCH_ALLOW_REMOTE=true"
        )
