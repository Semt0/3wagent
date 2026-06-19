"""Tests for config/ YAML files — schema completeness and consistency."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"

VALID_LEVELS = {"S", "A", "B", "C", "D"}


def load_yaml(path: Path) -> dict | list:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


class TestRouting:
    def test_loads_successfully(self):
        data = load_yaml(CONFIG_DIR / "routing.yaml")
        assert isinstance(data, dict)

    def test_has_classifications(self):
        data = load_yaml(CONFIG_DIR / "routing.yaml")
        classifications = data["classifications"]
        assert len(classifications) >= 4  # funds-forex, funds-banking, tax, commercial

    def test_classification_fields(self):
        data = load_yaml(CONFIG_DIR / "routing.yaml")
        for cls in data["classifications"]:
            assert "id" in cls
            assert "label" in cls
            assert "keywords" in cls
            assert isinstance(cls["keywords"], list)
            assert len(cls["keywords"]) > 0
            assert "agent" in cls

    def test_no_duplicate_classification_ids(self):
        data = load_yaml(CONFIG_DIR / "routing.yaml")
        ids = [cls["id"] for cls in data["classifications"]]
        assert len(ids) == len(set(ids))

    def test_has_subdomains(self):
        data = load_yaml(CONFIG_DIR / "routing.yaml")
        subdomains = data["subdomains"]
        assert "funds" in subdomains
        funds_subs = subdomains["funds"]
        sub_ids = [s["id"] for s in funds_subs]
        assert "forex-administration" in sub_ids
        assert "aml-kyc" in sub_ids


class TestSourceLevels:
    def test_loads_successfully(self):
        data = load_yaml(CONFIG_DIR / "source-levels.yaml")
        assert isinstance(data, dict)

    def test_all_levels_present(self):
        data = load_yaml(CONFIG_DIR / "source-levels.yaml")
        level_ids = {level["id"] for level in data["levels"]}
        assert level_ids == VALID_LEVELS

    def test_c_and_d_cannot_support(self):
        data = load_yaml(CONFIG_DIR / "source-levels.yaml")
        for level in data["levels"]:
            if level["id"] in ("C", "D"):
                assert level["can_support_final_conclusion"] is False
            else:
                assert level["can_support_final_conclusion"] is True

    def test_exactly_one_priority_section(self):
        data = load_yaml(CONFIG_DIR / "output-contract.yaml")
        priority_count = sum(
            1 for s in data["required_sections"] if s.get("is_priority")
        )
        assert priority_count == 1


class TestJurisdictions:
    def test_loads_successfully(self):
        data = load_yaml(CONFIG_DIR / "jurisdictions.yaml")
        assert isinstance(data, dict)

    def test_four_jurisdictions(self):
        data = load_yaml(CONFIG_DIR / "jurisdictions.yaml")
        ids = [j["id"] for j in data["jurisdictions"]]
        assert set(ids) == {"CN", "US", "HK", "SG"}

    def test_each_has_case_law_database(self):
        data = load_yaml(CONFIG_DIR / "jurisdictions.yaml")
        for jur in data["jurisdictions"]:
            assert len(jur["case_law_databases"]) >= 1

    def test_registry_paths_exist(self):
        data = load_yaml(CONFIG_DIR / "jurisdictions.yaml")
        for jur in data["jurisdictions"]:
            registry_path = ROOT / jur["registry"]
            assert registry_path.exists(), f"Missing registry: {jur['registry']}"


class TestOutputContract:
    def test_loads_successfully(self):
        data = load_yaml(CONFIG_DIR / "output-contract.yaml")
        assert isinstance(data, dict)

    def test_five_required_sections(self):
        data = load_yaml(CONFIG_DIR / "output-contract.yaml")
        assert len(data["required_sections"]) == 5

    def test_priorities_are_1_to_5(self):
        data = load_yaml(CONFIG_DIR / "output-contract.yaml")
        priorities = [s["priority"] for s in data["required_sections"]]
        assert sorted(priorities) == [1, 2, 3, 4, 5]

    def test_current_regulations_is_priority(self):
        data = load_yaml(CONFIG_DIR / "output-contract.yaml")
        priority_sections = [s for s in data["required_sections"] if s.get("is_priority")]
        assert len(priority_sections) == 1
        assert priority_sections[0]["id"] == "current_regulations"

    def test_has_supporting_sections(self):
        data = load_yaml(CONFIG_DIR / "output-contract.yaml")
        assert len(data["supporting_sections"]) >= 3
