#!/usr/bin/env python3
"""Validate config/ YAML files for schema completeness and consistency."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"

VALID_DOMAINS = {"funds", "tax", "commercial"}
VALID_LEVELS = {"S", "A", "B", "C", "D"}


def load_yaml(path: Path) -> dict | list:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def validate_routing() -> list[str]:
    """Validate config/routing.yaml."""
    errors: list[str] = []
    data = load_yaml(CONFIG_DIR / "routing.yaml")

    classifications = data.get("classifications", [])
    if not classifications:
        errors.append("routing.yaml: no classifications defined")
        return errors

    seen_ids: set[str] = set()
    seen_keywords: dict[str, str] = {}
    seen_agents: set[str] = set()

    for cls in classifications:
        cls_id = cls.get("id")
        if not cls_id:
            errors.append("routing.yaml: classification missing 'id'")
            continue
        if cls_id in seen_ids:
            errors.append(f"routing.yaml: duplicate classification id '{cls_id}'")
        seen_ids.add(cls_id)

        for field in ("label", "keywords", "agent"):
            if field not in cls:
                errors.append(f"routing.yaml: classification '{cls_id}' missing '{field}'")

        for kw in cls.get("keywords", []):
            if kw in seen_keywords:
                errors.append(
                    f"routing.yaml: keyword '{kw}' appears in both "
                    f"'{seen_keywords[kw]}' and '{cls_id}'"
                )
            seen_keywords[kw] = cls_id

        agent = cls.get("agent", "")
        if agent:
            seen_agents.add(agent)

    # Validate subdomains
    subdomains = data.get("subdomains", {})
    for domain, subs in subdomains.items():
        if domain not in VALID_DOMAINS:
            errors.append(f"routing.yaml: unknown subdomain parent domain '{domain}'")
        seen_sub_ids: set[str] = set()
        for sub in subs:
            sub_id = sub.get("id")
            if not sub_id:
                errors.append(f"routing.yaml: subdomain under '{domain}' missing 'id'")
                continue
            if sub_id in seen_sub_ids:
                errors.append(f"routing.yaml: duplicate subdomain id '{sub_id}' under '{domain}'")
            seen_sub_ids.add(sub_id)
            if "keywords" not in sub:
                errors.append(f"routing.yaml: subdomain '{sub_id}' missing 'keywords'")

    # Validate cross_domain_rules
    for rule in data.get("cross_domain_rules", []):
        for field in ("condition", "primary", "secondary"):
            if field not in rule:
                errors.append(f"routing.yaml: cross_domain_rule missing '{field}'")

    return errors


def validate_source_levels() -> list[str]:
    """Validate config/source-levels.yaml."""
    errors: list[str] = []
    data = load_yaml(CONFIG_DIR / "source-levels.yaml")

    levels = data.get("levels", [])
    if not levels:
        errors.append("source-levels.yaml: no levels defined")
        return errors

    seen_ids: set[str] = set()
    for level in levels:
        level_id = level.get("id")
        if not level_id:
            errors.append("source-levels.yaml: level missing 'id'")
            continue
        if level_id not in VALID_LEVELS:
            errors.append(f"source-levels.yaml: invalid level id '{level_id}'")
        if level_id in seen_ids:
            errors.append(f"source-levels.yaml: duplicate level id '{level_id}'")
        seen_ids.add(level_id)

        if "description_en" not in level and "description" not in level:
            errors.append(f"source-levels.yaml: level '{level_id}' missing description")
        if "can_support_final_conclusion" not in level:
            errors.append(f"source-levels.yaml: level '{level_id}' missing 'can_support_final_conclusion'")

    missing_levels = VALID_LEVELS - seen_ids
    if missing_levels:
        errors.append(f"source-levels.yaml: missing levels {sorted(missing_levels)}")

    return errors


def validate_jurisdictions() -> list[str]:
    """Validate config/jurisdictions.yaml."""
    errors: list[str] = []
    data = load_yaml(CONFIG_DIR / "jurisdictions.yaml")

    jurisdictions = data.get("jurisdictions", [])
    if not jurisdictions:
        errors.append("jurisdictions.yaml: no jurisdictions defined")
        return errors

    seen_ids: set[str] = set()

    for jur in jurisdictions:
        jur_id = jur.get("id")
        if not jur_id:
            errors.append("jurisdictions.yaml: jurisdiction missing 'id'")
            continue
        if jur_id in seen_ids:
            errors.append(f"jurisdictions.yaml: duplicate jurisdiction id '{jur_id}'")
        seen_ids.add(jur_id)

        for field in ("label_en", "label_zh", "registry"):
            if field not in jur:
                errors.append(f"jurisdictions.yaml: jurisdiction '{jur_id}' missing '{field}'")

        registry_path = ROOT / jur.get("registry", "")
        if jur.get("registry") and not registry_path.exists():
            errors.append(f"jurisdictions.yaml: registry path '{jur['registry']}' does not exist")

        case_dbs = jur.get("case_law_databases", [])
        if not case_dbs:
            errors.append(f"jurisdictions.yaml: jurisdiction '{jur_id}' has no case_law_databases")
        for db in case_dbs:
            for field in ("name", "url", "reliability"):
                if field not in db:
                    errors.append(
                        f"jurisdictions.yaml: case_law_database in '{jur_id}' missing '{field}'"
                    )
            if db.get("reliability") and db["reliability"] not in VALID_LEVELS:
                errors.append(
                    f"jurisdictions.yaml: invalid reliability '{db['reliability']}' in '{jur_id}'"
                )

    return errors


def validate_output_contract() -> list[str]:
    """Validate config/output-contract.yaml."""
    errors: list[str] = []
    data = load_yaml(CONFIG_DIR / "output-contract.yaml")

    required = data.get("required_sections", [])
    if not required:
        errors.append("output-contract.yaml: no required_sections defined")
        return errors

    seen_ids: set[str] = set()
    priorities: set[int] = set()
    priority_count = 0

    for section in required:
        section_id = section.get("id")
        if not section_id:
            errors.append("output-contract.yaml: required_section missing 'id'")
            continue
        if section_id in seen_ids:
            errors.append(f"output-contract.yaml: duplicate required_section id '{section_id}'")
        seen_ids.add(section_id)

        if "title" not in section:
            errors.append(f"output-contract.yaml: section '{section_id}' missing 'title'")
        if "priority" not in section:
            errors.append(f"output-contract.yaml: section '{section_id}' missing 'priority'")
        else:
            p = section["priority"]
            if p in priorities:
                errors.append(f"output-contract.yaml: duplicate priority {p}")
            priorities.add(p)

        if section.get("is_priority"):
            priority_count += 1

    if priority_count == 0:
        errors.append("output-contract.yaml: no required_section has is_priority: true")
    elif priority_count > 1:
        errors.append(f"output-contract.yaml: {priority_count} sections have is_priority: true (expected 1)")

    expected_priorities = set(range(1, len(required) + 1))
    if priorities != expected_priorities:
        errors.append(
            f"output-contract.yaml: priorities {sorted(priorities)} "
            f"don't match expected {sorted(expected_priorities)}"
        )

    # Validate supporting sections
    for section in data.get("supporting_sections", []):
        if "id" not in section:
            errors.append("output-contract.yaml: supporting_section missing 'id'")
        if "title" not in section:
            errors.append(f"output-contract.yaml: supporting_section '{section.get('id', '?')}' missing 'title'")

    return errors


def main() -> int:
    all_errors: list[str] = []

    validators = [
        ("routing.yaml", validate_routing),
        ("source-levels.yaml", validate_source_levels),
        ("jurisdictions.yaml", validate_jurisdictions),
        ("output-contract.yaml", validate_output_contract),
    ]

    for name, validator in validators:
        errors = validator()
        if errors:
            all_errors.extend(errors)
        else:
            print(f"  {name}: OK")

    if all_errors:
        print(f"\n{len(all_errors)} error(s) found:")
        for error in all_errors:
            print(f"  - {error}")
        return 1

    print("\nAll config files valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
