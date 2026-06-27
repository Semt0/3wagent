"""Tests for the lightweight SQLite RAG index."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp_server.rag_index import SourceMetadata, connect, read_source, search_documents, upsert_document


def test_rag_index_search_with_metadata_filters(tmp_path):
    index_path = tmp_path / "index.sqlite"
    metadata = SourceMetadata(
        source_id="cn-safe-test",
        title="SAFE Current Account Foreign Exchange Guidance",
        authority="State Administration of Foreign Exchange",
        url="https://example.test/safe",
        jurisdiction="CN",
        domains=("funds",),
        subdomains=("forex-administration",),
        reliability="A",
        source_type="regulator guidance",
    )
    text = (
        "# Current Account Payments\n\n"
        "Banks review service fee remittance documents for current account foreign exchange "
        "settlement and cross-border payment processing."
    )

    with connect(index_path) as conn:
        assert upsert_document(conn, metadata, text) == 1
        results = search_documents(
            conn,
            "service fee foreign exchange",
            jurisdictions=["CN"],
            domains=["funds"],
            reliability=["A"],
        )

    assert len(results) == 1
    assert results[0]["source_id"] == "cn-safe-test"
    assert results[0]["jurisdiction"] == "CN"
    assert results[0]["domains"] == ["funds"]
    assert "service fee" in results[0]["text_excerpt"]


def test_rag_index_read_source_reassembles_chunks(tmp_path):
    index_path = tmp_path / "index.sqlite"
    metadata = SourceMetadata(
        source_id="sg-tax-test",
        title="IRAS Withholding Tax Guide",
        authority="Inland Revenue Authority of Singapore",
        jurisdiction="SG",
        domains=("tax",),
        reliability="A",
    )

    with connect(index_path) as conn:
        upsert_document(conn, metadata, "Withholding tax may apply to certain payments.\n\n" * 80)
        result = read_source(conn, "sg-tax-test")

    assert result is not None
    assert result["source_id"] == "sg-tax-test"
    assert result["chunks"] >= 1
    assert "Withholding tax" in result["text"]
