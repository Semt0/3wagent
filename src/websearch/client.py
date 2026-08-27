"""HTTP client for the open-websearch local daemon."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import OpenerDirector, ProxyHandler, Request, build_opener

from src.config.websearch import WebSearchSettings
from src.websearch.protocol import FetchResponse, SearchResponse, SearchResult

SUPPORTED_ENGINES = {
    "baidu",
    "bing",
    "brave",
    "csdn",
    "duckduckgo",
    "exa",
    "hackernews",
    "juejin",
    "sogou",
    "startpage",
}
MAX_RESPONSE_BYTES = 4 * 1024 * 1024


class OpenWebSearchError(RuntimeError):
    """A structured daemon, transport, validation, or protocol error."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        status_code: int | None = None,
        hint: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.status_code = status_code
        self.hint = hint

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
            "status_code": self.status_code,
            "hint": self.hint,
        }


Transport = Callable[[Request, float], tuple[int, bytes]]


class OpenWebSearchClient:
    """Small synchronous client suitable for qwen-agent's synchronous tools."""

    def __init__(
        self,
        settings: WebSearchSettings | None = None,
        *,
        transport: Transport | None = None,
        opener: OpenerDirector | None = None,
    ) -> None:
        self.settings = settings or WebSearchSettings.from_env()
        self._opener = opener or build_opener(ProxyHandler({}))
        self._transport = transport or self._default_transport

    def status(self) -> dict[str, Any]:
        data = self._request("GET", "/status")
        if not isinstance(data, dict):
            raise OpenWebSearchError("invalid_response", "status data must be an object")
        return data

    def search(
        self,
        query: str,
        *,
        limit: int | None = None,
        engines: list[str] | None = None,
        search_mode: str | None = None,
    ) -> SearchResponse:
        clean_query = query.strip()
        if not clean_query:
            raise OpenWebSearchError("invalid_request", "query must not be empty")

        effective_limit = min(max(1, limit or self.settings.max_results), self.settings.max_results)
        payload: dict[str, Any] = {"query": clean_query, "limit": effective_limit}
        if engines:
            normalized = [str(engine).strip().lower() for engine in engines]
            invalid = sorted(set(normalized) - SUPPORTED_ENGINES)
            if invalid:
                raise OpenWebSearchError(
                    "invalid_request", f"unsupported search engines: {', '.join(invalid)}"
                )
            payload["engines"] = list(dict.fromkeys(normalized))
        if search_mode is not None:
            if search_mode not in {"request", "auto", "playwright"}:
                raise OpenWebSearchError("invalid_request", "invalid search_mode")
            payload["searchMode"] = search_mode

        data = self._request("POST", "/search", payload)
        if not isinstance(data, dict) or not isinstance(data.get("results"), list):
            raise OpenWebSearchError("invalid_response", "search data has an invalid shape")

        results: list[SearchResult] = []
        for item in data["results"]:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            if not url:
                continue
            results.append(
                SearchResult(
                    title=str(item.get("title") or ""),
                    url=url,
                    snippet=str(item.get("description") or item.get("content") or ""),
                    engine=str(item.get("engine") or ""),
                    source=str(item.get("source") or ""),
                )
            )

        failures = data.get("partialFailures") or []
        return SearchResponse(
            query=str(data.get("query") or clean_query),
            engines=[str(item) for item in (data.get("engines") or payload.get("engines") or [])],
            results=results,
            partial_failures=[item for item in failures if isinstance(item, dict)],
        )

    def fetch(
        self,
        url: str,
        *,
        max_chars: int | None = None,
        render_mode: str = "auto",
        readability: bool = True,
        include_links: bool = True,
    ) -> FetchResponse:
        clean_url = _validate_public_url(url)
        if render_mode not in {"request", "auto", "browser"}:
            raise OpenWebSearchError("invalid_request", "invalid render_mode")
        effective_max_chars = min(
            max(1_000, max_chars or self.settings.max_fetch_chars),
            self.settings.max_fetch_chars,
        )
        data = self._request(
            "POST",
            "/fetch-web",
            {
                "url": clean_url,
                "maxChars": effective_max_chars,
                "renderMode": render_mode,
                "readability": readability,
                "includeLinks": include_links,
            },
        )
        if not isinstance(data, dict) or not isinstance(data.get("content"), str):
            raise OpenWebSearchError("invalid_response", "fetch data has an invalid shape")
        links = data.get("links") or []
        return FetchResponse(
            url=str(data.get("url") or clean_url),
            final_url=str(data.get("finalUrl") or clean_url),
            title=str(data.get("title") or ""),
            content_type=str(data.get("contentType") or ""),
            retrieval_method=str(data.get("retrievalMethod") or ""),
            truncated=bool(data.get("truncated")),
            content=data["content"],
            links=[item for item in links if isinstance(item, dict)],
        )

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(
            f"{self.settings.base_url}{path}",
            data=body,
            method=method,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        try:
            status_code, raw = self._transport(request, float(self.settings.timeout_seconds))
        except HTTPError as exc:
            raw = exc.read(MAX_RESPONSE_BYTES + 1)
            self._raise_response_error(raw, status_code=exc.code)
        except (URLError, TimeoutError) as exc:
            raise OpenWebSearchError(
                "service_unavailable",
                f"open-websearch request failed: {exc}",
                retryable=True,
            ) from exc
        except OSError as exc:
            raise OpenWebSearchError(
                "service_unavailable",
                f"open-websearch transport failed: {exc}",
                retryable=True,
            ) from exc

        if len(raw) > MAX_RESPONSE_BYTES:
            raise OpenWebSearchError("response_too_large", "open-websearch response is too large")
        try:
            envelope = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OpenWebSearchError(
                "invalid_response", "open-websearch returned invalid JSON"
            ) from exc
        if not isinstance(envelope, dict):
            raise OpenWebSearchError("invalid_response", "response envelope must be an object")
        if status_code >= 400 or envelope.get("status") != "ok":
            self._raise_envelope(envelope, status_code=status_code)
        return envelope.get("data")

    def _default_transport(self, request: Request, timeout: float) -> tuple[int, bytes]:
        with self._opener.open(request, timeout=timeout) as response:
            return response.status, response.read(MAX_RESPONSE_BYTES + 1)

    def _raise_response_error(self, raw: bytes, *, status_code: int) -> None:
        try:
            envelope = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise OpenWebSearchError(
                "http_error",
                f"open-websearch returned HTTP {status_code}",
                retryable=status_code >= 500,
                status_code=status_code,
            )
        self._raise_envelope(envelope, status_code=status_code)

    @staticmethod
    def _raise_envelope(envelope: Any, *, status_code: int) -> None:
        error = envelope.get("error") if isinstance(envelope, dict) else None
        error = error if isinstance(error, dict) else {}
        code = str(error.get("code") or "service_error")
        message = str(error.get("message") or f"open-websearch returned HTTP {status_code}")
        hint = envelope.get("hint") if isinstance(envelope, dict) else None
        raise OpenWebSearchError(
            code,
            message,
            retryable=status_code >= 500 or code in {"engine_error", "browser_unavailable"},
            status_code=status_code,
            hint=str(hint) if hint else None,
        )


def _validate_public_url(url: str) -> str:
    clean_url = url.strip()
    parsed = urlparse(clean_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise OpenWebSearchError("invalid_request", "url must be a public HTTP(S) URL")
    if parsed.username or parsed.password:
        raise OpenWebSearchError("invalid_request", "url must not contain credentials")
    hostname = parsed.hostname.lower()
    if hostname in {"localhost", "::1"} or hostname.endswith(".localhost"):
        raise OpenWebSearchError("invalid_request", "local URLs are not allowed")
    try:
        import ipaddress

        address = ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        if not address.is_global:
            raise OpenWebSearchError("invalid_request", "private or local URLs are not allowed")
    return clean_url
