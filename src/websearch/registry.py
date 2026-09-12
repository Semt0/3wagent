"""Query-aware access to curated source registries."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

from src.tools.common import PROJECT_ROOT
from src.websearch.relevance import normalize_search_text, relevance_score, strip_site_operators


@dataclass(frozen=True)
class RegistryMatch:
    source_id: str
    title: str
    url: str
    authority: str
    reliability: str
    source_type: str
    score: float

    def to_search_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": f"{self.authority}; {self.source_type}; reliability {self.reliability}",
            "engine": "source_registry",
            "source": self.source_id,
            "relevance_score": self.score,
        }


def load_registry_matches(
    query: str,
    jurisdiction: str | None,
    *,
    minimum_score: float = 0.46,
    limit: int = 5,
    registry_path: Path | None = None,
) -> list[RegistryMatch]:
    if len(normalize_search_text(strip_site_operators(query))) < 3:
        return []
    matches: list[RegistryMatch] = []
    for entry in _load_registry_entries(jurisdiction, registry_path=registry_path):
        title = str(entry.get("title") or "")
        url = str(entry.get("url") or "")
        if not title or not url:
            continue
        context = " ".join(
            str(value)
            for value in (
                entry.get("authority") or "",
                entry.get("notes") or "",
                " ".join(str(item) for item in entry.get("domains") or []),
                " ".join(str(item) for item in entry.get("subdomains") or []),
            )
        )
        score = relevance_score(query, title, context)
        if score < minimum_score:
            continue
        matches.append(
            RegistryMatch(
                source_id=str(entry.get("id") or "source_registry"),
                title=title,
                url=url,
                authority=str(entry.get("authority") or ""),
                reliability=str(entry.get("reliability") or ""),
                source_type=str(entry.get("source_type") or ""),
                score=score,
            )
        )
    matches.sort(key=lambda item: (item.score, item.reliability in {"S", "A"}), reverse=True)
    return matches[:limit]


def infer_official_domains(query: str, jurisdiction: str | None, *, limit: int = 2) -> list[str]:
    """Infer likely authority hosts from related registry entries."""

    ranked: list[tuple[float, str]] = []
    for entry in _load_registry_entries(jurisdiction):
        hostname = (urlparse(str(entry.get("url") or "")).hostname or "").lower()
        if not hostname:
            continue
        title = str(entry.get("title") or "")
        context = f"{entry.get('authority') or ''} {entry.get('notes') or ''}"
        score = relevance_score(query, title, context)
        if score >= 0.2:
            ranked.append((score, hostname.removeprefix("www.")))
    ranked.sort(reverse=True)
    domains: list[str] = []
    for _, domain in ranked:
        if domain not in domains:
            domains.append(domain)
        if len(domains) >= limit:
            break
    return domains


def _load_registry_entries(
    jurisdiction: str | None, *, registry_path: Path | None = None
) -> list[dict[str, Any]]:
    if not jurisdiction and registry_path is None:
        return []
    path = registry_path or PROJECT_ROOT / "sources" / f"{jurisdiction.lower()}.yaml"
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, TypeError, ValueError, yaml.YAMLError):
        return []
    sources = data.get("sources") if isinstance(data, dict) else None
    if not isinstance(sources, list):
        return []
    return [entry for entry in sources if isinstance(entry, dict)]
