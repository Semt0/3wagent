"""Stable internal response types for web search and content retrieval."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str
    engine: str
    source: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SearchResponse:
    query: str
    engines: list[str]
    results: list[SearchResult]
    partial_failures: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "engines": self.engines,
            "total_results": len(self.results),
            "results": [item.to_dict() for item in self.results],
            "partial_failures": self.partial_failures,
        }


@dataclass(frozen=True)
class FetchResponse:
    url: str
    final_url: str
    title: str
    content_type: str
    retrieval_method: str
    truncated: bool
    content: str
    links: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
