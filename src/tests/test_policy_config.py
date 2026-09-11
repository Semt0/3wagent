"""Regression tests for policy taxonomy and official-source coverage."""

from pathlib import Path

import yaml
from src.websearch.policy import is_official_url, load_jurisdiction_search_policy

SRC_ROOT = Path(__file__).parents[1]


def _yaml(relative_path: str):
    return yaml.safe_load((SRC_ROOT / relative_path).read_text(encoding="utf-8"))


def test_cn_policy_recognizes_csrc_and_its_filing_subdomain():
    policy = load_jurisdiction_search_policy("CN")

    assert "csrc.gov.cn" in policy.official_domains
    assert is_official_url("https://www.csrc.gov.cn/csrc/rule", policy.official_domains)
    assert is_official_url("https://neris.csrc.gov.cn/", policy.official_domains)
    assert not is_official_url("https://csrc.gov.cn.example.com/", policy.official_domains)


def test_overseas_listing_has_a_commercial_securities_taxonomy():
    routing = _yaml("config/routing.yaml")
    commercial = next(item for item in routing["classifications"] if item["id"] == "commercial")
    securities = next(
        item
        for item in routing["subdomains"]["commercial"]
        if item["id"] == "securities-regulation"
    )

    assert commercial["agent"] == "commercial-law-analyst"
    assert {"境外发行", "境外上市", "中国证监会"}.issubset(commercial["keywords"])
    assert {"上市备案", "间接境外发行上市", "CSRC"}.issubset(securities["keywords"])


def test_cn_registry_distinguishes_rule_release_notice_and_service():
    registry = _yaml("sources/cn.yaml")
    sources = {source["id"]: source for source in registry["sources"]}
    expected = {
        "cn-csrc-overseas-listing-trial-measures": "S",
        "cn-csrc-overseas-listing-trial-measures-text": "S",
        "cn-csrc-overseas-listing-trial-measures-explanation": "A",
        "cn-csrc-overseas-listing-rules-release": "A",
        "cn-csrc-overseas-listing-filing-arrangements": "A",
        "cn-csrc-overseas-listing-filing-system": "A",
    }

    for source_id, reliability in expected.items():
        source = sources[source_id]
        assert source["reliability"] == reliability
        assert source["domains"] == ["commercial"]
        assert source["subdomains"] == ["securities-regulation"]
        assert source["url"].startswith("https://")

    assert "Attachment 1" in sources["cn-csrc-overseas-listing-trial-measures"]["notes"]
    assert sources["cn-csrc-overseas-listing-trial-measures-text"]["source_type"] == (
        "departmental rule text"
    )
    assert sources["cn-csrc-overseas-listing-trial-measures-explanation"]["source_type"] == (
        "official explanatory material"
    )
    assert "substitute" in sources["cn-csrc-overseas-listing-rules-release"]["notes"]
