#!/usr/bin/env python3
"""Validate sources/*.yaml registry files for schema completeness and consistency."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SOURCES_DIR = ROOT / "sources"
CONFIG_DIR = ROOT / "config"

VALID_DOMAINS = {"funds", "tax", "commercial"}
VALID_LEVELS = {"S", "A", "B", "C", "D"}
VALID_STATUSES = {"effective", "repealed", "replaced", "amended", "historical", "unknown"}

REQUIRED_FIELDS = ("id", "title", "authority", "url", "domains", "reliability", "source_type")


def load_yaml(path: Path) -> dict | list:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_valid_subdomains() -> set[str]:
    """Load valid subdomain IDs from config/routing.yaml."""
    routing = load_yaml(CONFIG_DIR / "routing.yaml")
    subdomain_ids: set[str] = set()
    for _domain, subs in routing.get("subdomains", {}).items():
        for sub in subs:
            if "id" in sub:
                subdomain_ids.add(sub["id"])
    return subdomain_ids


def validate_registry(path: Path) -> list[str]:
    """Validate a single registry YAML file."""
    errors: list[str] = []
    data = load_yaml(path)
    jur = data.get("jurisdiction", "?")
    sources = data.get("sources", [])

    if not sources:
        errors.append(f"[{jur}]: no sources defined")
        return errors

    seen_ids: set[str] = set()
    valid_subdomains = get_valid_subdomains()

    for src in sources:
        src_id = src.get("id", "?")

        # Check required fields
        for field in REQUIRED_FIELDS:
            if field not in src or not src[field]:
                errors.append(f"[{jur}] source '{src_id}': missing or empty '{field}'")

        # Check ID uniqueness
        if src_id in seen_ids:
            errors.append(f"[{jur}]: duplicate source id '{src_id}'")
        seen_ids.add(src_id)

        # Check reliability
        rel = src.get("reliability")
        if rel and rel not in VALID_LEVELS:
            errors.append(f"[{jur}] source '{src_id}': invalid reliability '{rel}'")

        # Check domains
        domains = src.get("domains", [])
        if isinstance(domains, list):
            for d in domains:
                if d not in VALID_DOMAINS:
                    errors.append(f"[{jur}] source '{src_id}': invalid domain '{d}'")
        elif isinstance(domains, str):
            if domains not in VALID_DOMAINS:
                errors.append(f"[{jur}] source '{src_id}': invalid domain '{domains}'")

        # Check subdomains
        subdomains = src.get("subdomains", [])
        if isinstance(subdomains, list):
            for sd in subdomains:
                if sd not in valid_subdomains:
                    errors.append(f"[{jur}] source '{src_id}': unknown subdomain '{sd}'")

        # Check URL non-empty
        url = src.get("url", "")
        if isinstance(url, str) and not url.strip():
            errors.append(f"[{jur}] source '{src_id}': empty URL")

        # Check status if present
        status = src.get("status")
        if status and status not in VALID_STATUSES:
            errors.append(f"[{jur}] source '{src_id}': invalid status '{status}'")

    return errors


def main() -> int:
    all_errors: list[str] = []
    registry_files = sorted(SOURCES_DIR.glob("*.yaml"))

    if not registry_files:
        print("No registry YAML files found in sources/")
        return 1

    for path in registry_files:
        errors = validate_registry(path)
        if errors:
            all_errors.extend(errors)
        else:
            jur = load_yaml(path).get("jurisdiction", "?")
            print(f"  {path.name} ({jur}): OK")

    if all_errors:
        print(f"\n{len(all_errors)} error(s) found:")
        for error in all_errors:
            print(f"  - {error}")
        return 1

    print("\nAll registry files valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
