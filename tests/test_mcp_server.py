"""Tests for mcp_server tools. Skipped unless the mcp extra is installed."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest

pytest.importorskip("mcp")

# Ensure project root and tools/ are importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from mcp_server.server import (
    report_artifact_list,
    report_artifact_read,
    routing_classify,
    source_document_read,
    source_document_search,
    source_registry_search,
)
from mcp_server.rag_index import SourceMetadata, connect, upsert_document


@pytest.fixture
def sample_report(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        report_dir = root / "reports" / "20260601-test-report"
        report_dir.mkdir(parents=True)
        (report_dir / "report.md").write_text("# Test Report\nHello", encoding="utf-8")

        import mcp_server.server as server_module

        monkeypatch.setattr(server_module, "REPORTS_ROOT", root / "reports")
        monkeypatch.setattr(server_module, "SOURCES_ROOT", root / "sources")
        monkeypatch.setattr(server_module, "CONFIG_ROOT", root / "config")
        monkeypatch.setattr(server_module, "SOURCE_INDEX_PATH", root / "sources" / "index.sqlite")
        yield root


@pytest.mark.anyio
async def test_report_artifact_list(sample_report):
    result = json.loads(await report_artifact_list())
    assert len(result) == 1
    assert result[0]["id"] == "20260601-test-report"
    assert result[0]["date"] == "20260601"
    assert result[0]["topic"] == "test-report"
    assert result[0]["pdf"] is None


@pytest.mark.anyio
async def test_report_artifact_read(sample_report):
    result = await report_artifact_read("20260601-test-report")
    assert "# Test Report" in result
    assert "Hello" in result


@pytest.mark.anyio
async def test_report_artifact_read_not_found(sample_report):
    result = await report_artifact_read("missing")
    data = json.loads(result)
    assert "error" in data


@pytest.mark.anyio
async def test_report_artifact_read_rejects_invalid_id(sample_report):
    result = await report_artifact_read("..")
    data = json.loads(result)
    assert data["error"].startswith("Invalid report id")


@pytest.mark.anyio
async def test_source_registry_search(sample_report):
    sources_root = sample_report / "sources"
    sources_root.mkdir(parents=True)
    (sources_root / "cn.yaml").write_text(
        "jurisdiction: CN\n"
        "sources:\n"
        "  - id: cn-test\n"
        "    title: Test Source\n"
        "    domains: [funds]\n"
        "    reliability: S\n",
        encoding="utf-8",
    )
    result = json.loads(await source_registry_search(["CN"], ["funds"]))
    assert len(result) == 1
    assert result[0]["id"] == "cn-test"


@pytest.mark.anyio
async def test_source_registry_search_query_and_reliability(sample_report):
    sources_root = sample_report / "sources"
    sources_root.mkdir(parents=True)
    (sources_root / "cn.yaml").write_text(
        "jurisdiction: CN\n"
        "sources:\n"
        "  - id: cn-tax\n"
        "    title: Tax Service Fee Guidance\n"
        "    authority: State Taxation Administration\n"
        "    domains: [tax]\n"
        "    reliability: A\n"
        "    source_type: tax authority guidance\n"
        "    notes: Service fee tax policy.\n"
        "  - id: cn-commentary\n"
        "    title: Public Commentary\n"
        "    authority: Example\n"
        "    domains: [tax]\n"
        "    reliability: D\n"
        "    source_type: public commentary\n",
        encoding="utf-8",
    )
    result = json.loads(
        await source_registry_search(["CN"], ["tax"], query="service fee tax", reliability=["A"])
    )
    assert [item["id"] for item in result] == ["cn-tax"]
    assert result[0]["applicable_point"] == "Service fee tax policy."


@pytest.mark.anyio
async def test_source_document_search_and_read(sample_report):
    sources_root = sample_report / "sources"
    sources_root.mkdir(parents=True)
    index_path = sources_root / "index.sqlite"
    metadata = SourceMetadata(
        source_id="hk-tax-test",
        title="Hong Kong Profits Tax Practice Note",
        authority="Inland Revenue Department",
        jurisdiction="HK",
        domains=("tax",),
        reliability="A",
    )
    with connect(index_path) as conn:
        upsert_document(
            conn,
            metadata,
            "Service fee income characterization may affect Hong Kong profits tax analysis.",
        )

    search_result = json.loads(await source_document_search("service fee profits tax", ["HK"], ["tax"]))
    assert len(search_result) == 1
    assert search_result[0]["source_id"] == "hk-tax-test"

    read_result = json.loads(await source_document_read("hk-tax-test"))
    assert read_result["source_id"] == "hk-tax-test"
    assert "Service fee income" in read_result["text"]


@pytest.mark.anyio
async def test_routing_classify(sample_report):
    config_root = sample_report / "config"
    config_root.mkdir(parents=True)
    (config_root / "routing.yaml").write_text(
        "classifications:\n"
        "  - id: tax\n"
        "    label: 税务\n"
        "    keywords: [预提税, 服务费]\n"
        "    agent: tax-policy-analyst\n"
        "subdomains:\n"
        "  funds: []\n",
        encoding="utf-8",
    )
    result = json.loads(await routing_classify("香港公司支付服务费涉及预提税"))
    assert result["primary_agent"] == "tax-policy-analyst"
    assert any(c["id"] == "tax" for c in result["classifications"])
