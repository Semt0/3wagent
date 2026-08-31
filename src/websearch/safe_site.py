"""Bounded retrieval helpers for the official SAFE website.

SAFE's search and policy-list pages are rendered in the original HTML, but the
generic readability extractor used by open-websearch can mistake the shared
footer for the page body.  This module only talks to fixed SAFE endpoints and
extracts compact discovery records; article pages still go through
``WebFetchTool`` and open-websearch.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from src.websearch.protocol import SearchResult

SAFE_ORIGIN = "https://www.safe.gov.cn"
SAFE_SEARCH_URL = f"{SAFE_ORIGIN}/internet_app/search"
SAFE_LISTING_PATHS = {
    "/safe/zcfg/index.html",
    "/safe/xzgfxwj/index.html",
    "/safe/wsfw/",
}
MAX_SAFE_RESPONSE_BYTES = 3 * 1024 * 1024
MAX_SAFE_SNIPPET_CHARS = 600


class SafeSiteError(RuntimeError):
    """The bounded SAFE request or parser failed."""


@dataclass(frozen=True)
class SafeListing:
    title: str
    content: str
    links: list[dict[str, str]]
    truncated: bool


class _SafeRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _require_safe_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class SafeOfficialSiteClient:
    """Fetch only SAFE's fixed search endpoint and allow-listed index pages."""

    def __init__(self, *, timeout_seconds: int = 30) -> None:
        self.timeout_seconds = timeout_seconds
        # Do not inherit a stale HTTP(S)_PROXY intended for the local daemon.
        self._opener = build_opener(ProxyHandler({}), _SafeRedirectHandler())

    def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        clean_query = query.strip()
        if not clean_query:
            return []
        raw, _ = self._get(f"{SAFE_SEARCH_URL}?{urlencode({'q': clean_query})}")
        parser = _SafeSearchParser()
        parser.feed(_decode_html(raw))
        return [
            SearchResult(
                title=item["title"],
                url=item["url"],
                snippet=item["snippet"][:MAX_SAFE_SNIPPET_CHARS],
                engine="safe_site",
                source="official_site_search",
            )
            for item in parser.results[: max(1, limit)]
        ]

    def fetch_listing(self, url: str, *, max_chars: int) -> SafeListing:
        canonical_url = _canonical_listing_url(url)
        raw, _ = self._get(canonical_url)
        parser = _SafeListingParser()
        parser.feed(_decode_html(raw))
        if not parser.items:
            raise SafeSiteError("SAFE listing page contained no policy links")

        lines: list[str] = []
        links: list[dict[str, str]] = []
        for item in parser.items:
            prefix = f"[{item['date']}] " if item["date"] else ""
            lines.append(f"{prefix}{item['title']}\n{item['url']}")
            links.append({"text": item["title"], "href": item["url"]})
        content = "\n\n".join(lines)
        truncated = len(content) > max_chars
        return SafeListing(
            title=parser.title or "国家外汇管理局",
            content=content[:max_chars],
            links=links,
            truncated=truncated,
        )

    def _get(self, url: str) -> tuple[bytes, str]:
        _require_safe_url(url)
        request = Request(
            url,
            headers={
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Encoding": "identity",
                "User-Agent": "3WAgent/1.0 SAFE official-source retrieval",
            },
        )
        try:
            with self._opener.open(request, timeout=self.timeout_seconds) as response:
                final_url = response.geturl()
                _require_safe_url(final_url)
                raw = response.read(MAX_SAFE_RESPONSE_BYTES + 1)
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
            raise SafeSiteError(f"SAFE official-site request failed: {exc}") from exc
        if len(raw) > MAX_SAFE_RESPONSE_BYTES:
            raise SafeSiteError("SAFE official-site response is too large")
        return raw, final_url

def is_safe_search_query(query: str, jurisdiction: str | None) -> bool:
    """Use SAFE search only for clearly relevant mainland-China queries."""

    if jurisdiction != "CN":
        return False
    normalized = query.casefold()
    return any(
        marker in normalized
        for marker in (
            "safe",
            "外汇",
            "汇发",
            "跨境贸易",
            "资本项目",
            "经常项目",
        )
    )


def should_replace_safe_listing(url: str, content: str, links: list[dict[str, Any]]) -> bool:
    """Detect the known footer-only extraction failure on SAFE index pages."""

    try:
        _canonical_listing_url(url)
    except SafeSiteError:
        return False
    return len(content.strip()) < 500 or len(links) < 8


def _canonical_listing_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or (parsed.hostname or "").lower() != "www.safe.gov.cn":
        raise SafeSiteError("not an allow-listed SAFE index URL")
    path = parsed.path
    if path not in SAFE_LISTING_PATHS:
        raise SafeSiteError("not an allow-listed SAFE index URL")
    return f"{SAFE_ORIGIN}{path}"


def _require_safe_url(url: str) -> None:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or hostname not in {"safe.gov.cn", "www.safe.gov.cn"}:
        raise SafeSiteError("SAFE helper refused a non-official URL")
    if parsed.username or parsed.password:
        raise SafeSiteError("SAFE helper refused URL credentials")


def _safe_result_url(href: str) -> str | None:
    candidate = urljoin(f"{SAFE_ORIGIN}/", href.strip())
    parsed = urlparse(candidate)
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or not (
        hostname == "safe.gov.cn" or hostname.endswith(".safe.gov.cn")
    ):
        return None
    # Search-result paths work on the canonical HTTPS host, including regional
    # branches, and this keeps provenance stable across runs.
    return f"{SAFE_ORIGIN}{parsed.path}" + (f"?{parsed.query}" if parsed.query else "")


def _decode_html(raw: bytes) -> str:
    for encoding in ("utf-8", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _clean_text(parts: list[str]) -> str:
    return re.sub(r"\s+", " ", "".join(parts)).strip()


class _SafeSearchParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.results: list[dict[str, str]] = []
        self._in_result = False
        self._in_title_link = False
        self._in_snippet = False
        self._href = ""
        self._title_parts: list[str] = []
        self._snippet_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        classes = set((values.get("class") or "").split())
        if tag == "li" and "ssjg" in classes:
            self._in_result = True
            self._href = ""
            self._title_parts = []
            self._snippet_parts = []
        elif self._in_result and tag == "a" and not self._href:
            self._href = values.get("href") or ""
            self._in_title_link = True
        elif self._in_result and tag == "span" and "ft" in classes:
            self._in_snippet = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "a":
            self._in_title_link = False
        elif tag == "span":
            self._in_snippet = False
        elif tag == "li" and self._in_result:
            url = _safe_result_url(self._href)
            title = _clean_text(self._title_parts)
            if url and title:
                self.results.append(
                    {"title": title, "url": url, "snippet": _clean_text(self._snippet_parts)}
                )
            self._in_result = False

    def handle_data(self, data: str) -> None:
        if self._in_title_link:
            self._title_parts.append(data)
        elif self._in_snippet:
            self._snippet_parts.append(data)


class _SafeListingParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.items: list[dict[str, str]] = []
        self._title_depth = 0
        self._title_parts: list[str] = []
        self._listing_depth = 0
        self._in_item = False
        self._in_link = False
        self._in_date = False
        self._href = ""
        self._link_title = ""
        self._text_parts: list[str] = []
        self._date_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        classes = set((values.get("class") or "").split())
        if tag == "title":
            self._title_depth += 1
        if self._listing_depth:
            self._listing_depth += 1
        elif "list_conr" in classes:
            self._listing_depth = 1
        if not self._listing_depth:
            return
        if tag == "li":
            self._in_item = True
            self._href = ""
            self._link_title = ""
            self._text_parts = []
            self._date_parts = []
        elif self._in_item and tag == "a" and not self._href:
            self._href = values.get("href") or ""
            self._link_title = values.get("title") or ""
            self._in_link = True
        elif self._in_item and tag == "dd":
            self._in_date = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "title" and self._title_depth:
            self._title_depth -= 1
            self.title = _clean_text(self._title_parts)
        if self._listing_depth:
            if tag == "a":
                self._in_link = False
            elif tag == "dd":
                self._in_date = False
            elif tag == "li" and self._in_item:
                url = _safe_result_url(self._href)
                title = self._link_title.strip() or _clean_text(self._text_parts)
                if url and title:
                    self.items.append(
                        {"title": title, "url": url, "date": _clean_text(self._date_parts)}
                    )
                self._in_item = False
            self._listing_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._title_depth:
            self._title_parts.append(data)
        if self._in_link:
            self._text_parts.append(data)
        elif self._in_date:
            self._date_parts.append(data)
