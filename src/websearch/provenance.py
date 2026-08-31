"""Run-scoped provenance and failure tracking for web URLs."""

from __future__ import annotations

import html
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import yaml

from src.config.runtime import get_run_id
from src.tools.common import PROJECT_ROOT

MAX_TRACKED_RUNS = 32
# Parentheses are allowed inside the match so URLs like Wikipedia titles
# (".../Value-added_tax_(China)") survive intact; a trailing ")" that only
# closes surrounding prose or Markdown link syntax is removed afterwards by
# _trim_trailing_url_punctuation based on paren balance.
_HTTP_URL_PATTERN = re.compile(r"https?://[^\s<>\[\]\"']+", re.IGNORECASE)
_TRAILING_URL_PUNCTUATION = "]},.;:，。；：！？!?"


@dataclass
class _RunUrlState:
    discovered: dict[str, str] = field(default_factory=dict)
    failed: dict[str, dict[str, Any]] = field(default_factory=dict)


_run_states: dict[str, _RunUrlState] = {}


def canonicalize_url(url: str) -> str | None:
    """Return a stable HTTP(S) identity, ignoring fragments and default ports."""
    try:
        parsed = urlsplit(url.strip())
        hostname = (parsed.hostname or "").lower()
        port = parsed.port
    except (TypeError, ValueError):
        return None
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"} or not hostname:
        return None
    default_port = (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    host_display = f"[{hostname}]" if ":" in hostname else hostname
    netloc = host_display if port is None or default_port else f"{host_display}:{port}"
    return urlunsplit((scheme, netloc, parsed.path or "/", parsed.query, ""))


def register_discovered_urls(
    urls: Iterable[str], *, source: str, run_id: str | None = None
) -> None:
    state = _get_state(run_id)
    for url in urls:
        canonical = canonicalize_url(url)
        if canonical:
            state.discovered.setdefault(canonical, source)


def register_user_provided_urls(text: str, *, run_id: str | None = None) -> list[str]:
    """Register exact HTTP(S) URLs from the current user message."""

    decoded = html.unescape(text)
    urls = [_trim_trailing_url_punctuation(match) for match in _HTTP_URL_PATTERN.findall(decoded)]
    unique_urls = list(dict.fromkeys(url for url in urls if canonicalize_url(url)))
    register_discovered_urls(unique_urls, source="user_provided_url", run_id=run_id)
    return unique_urls


def _trim_trailing_url_punctuation(url: str) -> str:
    """Strip sentence-final punctuation without breaking in-URL parentheses.

    A trailing ")" is removed only while parentheses are unbalanced, which
    drops the closing paren of `[text](url)` Markdown and prose wrapping but
    keeps balanced pairs that are part of the URL itself.
    """
    url = url.rstrip(_TRAILING_URL_PUNCTUATION)
    while url.endswith(")") and url.count(")") > url.count("("):
        url = url[:-1]
    return url


def get_url_provenance(url: str, *, run_id: str | None = None) -> str | None:
    canonical = canonicalize_url(url)
    if canonical is None:
        return None
    if canonical in _registry_urls():
        return "sources_registry"
    return _get_state(run_id).discovered.get(canonical)


def record_fetch_failure(
    url: str,
    *,
    code: str,
    message: str,
    retryable: bool = False,
    run_id: str | None = None,
) -> dict[str, Any] | None:
    canonical = canonicalize_url(url)
    if canonical:
        state = _get_state(run_id)
        previous = state.failed.get(canonical)
        attempts = int(previous.get("attempts", 0)) + 1 if previous else 1
        failure = {
            "code": code,
            "message": message,
            "retryable": retryable,
            "attempts": attempts,
        }
        state.failed[canonical] = failure
        return failure
    return None


def get_fetch_failure(url: str, *, run_id: str | None = None) -> dict[str, Any] | None:
    canonical = canonicalize_url(url)
    if canonical is None:
        return None
    return _get_state(run_id).failed.get(canonical)


def clear_fetch_failure(url: str, *, run_id: str | None = None) -> None:
    """Forget a stale failure after the URL gains a trusted provenance."""
    canonical = canonicalize_url(url)
    if canonical:
        _get_state(run_id).failed.pop(canonical, None)


def reset_provenance_state() -> None:
    """Clear process-local state. Intended for tests and controlled restarts."""
    _run_states.clear()
    _registry_urls.cache_clear()


def _get_state(run_id: str | None) -> _RunUrlState:
    effective_run_id = run_id or get_run_id()
    if effective_run_id not in _run_states:
        while len(_run_states) >= MAX_TRACKED_RUNS:
            _run_states.pop(next(iter(_run_states)))
        _run_states[effective_run_id] = _RunUrlState()
    return _run_states[effective_run_id]


@lru_cache(maxsize=1)
def _registry_urls() -> frozenset[str]:
    urls: set[str] = set()
    for path in sorted((PROJECT_ROOT / "sources").glob("*.yaml")):
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, yaml.YAMLError):
            continue
        for url in _walk_urls(document):
            canonical = canonicalize_url(url)
            if canonical:
                urls.add(canonical)
    return frozenset(urls)


def _walk_urls(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "url" and isinstance(item, str):
                yield item
            else:
                yield from _walk_urls(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_urls(item)
