"""Tests for sources/*.yaml registry files — schema completeness and consistency."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SOURCES_DIR = ROOT / "sources"

VALID_DOMAINS = {"funds", "tax", "commercial"}
VALID_LEVELS = {"S", "A", "B", "C", "D"}
REQUIRED_FIELDS = ("id", "title", "authority", "url", "domains", "reliability", "source_type")


def load_yaml(path: Path) -> dict | list:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def all_registry_files() -> list[Path]:
    return sorted(SOURCES_DIR.glob("*.yaml"))


@pytest.fixture(params=all_registry_files())
def registry_path(request):
    return request.param


def test_all_registries_load():
    for path in all_registry_files():
        data = load_yaml(path)
        assert isinstance(data, dict)


def test_registry_has_jurisdiction(registry_path):
    data = load_yaml(registry_path)
    assert "jurisdiction" in data
    assert data["jurisdiction"] in ("CN", "US", "HK", "SG")


def test_registry_has_sources(registry_path):
    data = load_yaml(registry_path)
    sources = data.get("sources", [])
    assert len(sources) > 0


def test_required_fields_present(registry_path):
    data = load_yaml(registry_path)
    for src in data["sources"]:
        for field in REQUIRED_FIELDS:
            assert field in src, f"source '{src.get('id', '?')}' missing '{field}'"


def test_reliability_valid(registry_path):
    data = load_yaml(registry_path)
    for src in data["sources"]:
        assert src["reliability"] in VALID_LEVELS, (
            f"source '{src['id']}': invalid reliability '{src['reliability']}'"
        )


def test_domains_valid(registry_path):
    data = load_yaml(registry_path)
    for src in data["sources"]:
        domains = src["domains"]
        if isinstance(domains, list):
            for d in domains:
                assert d in VALID_DOMAINS, f"source '{src['id']}': invalid domain '{d}'"
        else:
            assert domains in VALID_DOMAINS


def test_ids_unique_within_registry(registry_path):
    data = load_yaml(registry_path)
    ids = [src["id"] for src in data["sources"]]
    assert len(ids) == len(set(ids)), f"Duplicate IDs in {registry_path.name}"


def test_urls_non_empty(registry_path):
    data = load_yaml(registry_path)
    for src in data["sources"]:
        url = src.get("url", "")
        assert url.strip(), f"source '{src['id']}': empty URL"
