"""Jurisdiction-specific web-search policy loaded from the config layer."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import yaml

from src.tools.common import PROJECT_ROOT


@dataclass(frozen=True)
class JurisdictionSearchPolicy:
    jurisdiction: str
    engines: list[str]
    official_domains: list[str]


def load_jurisdiction_search_policy(
    jurisdiction: str | None,
    *,
    config_path: Path | None = None,
) -> JurisdictionSearchPolicy | None:
    if not jurisdiction:
        return None
    jurisdiction_id = jurisdiction.strip().upper()
    path = config_path or PROJECT_ROOT / "config" / "jurisdictions.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict) or not isinstance(data.get("jurisdictions"), list):
        raise TypeError("jurisdictions config has an invalid shape")
    for item in data.get("jurisdictions", []):
        if not isinstance(item, dict):
            continue
        if str(item.get("id", "")).upper() != jurisdiction_id:
            continue
        web_search = item.get("web_search") or {}
        return JurisdictionSearchPolicy(
            jurisdiction=jurisdiction_id,
            engines=[str(value).lower() for value in web_search.get("engines", [])],
            official_domains=[
                str(value).lower().rstrip(".") for value in web_search.get("official_domains", [])
            ],
        )
    return None


def is_official_url(url: str, official_domains: list[str]) -> bool:
    try:
        hostname = (urlparse(url).hostname or "").lower().rstrip(".")
    except ValueError:
        return False
    return any(hostname == domain or hostname.endswith(f".{domain}") for domain in official_domains)
