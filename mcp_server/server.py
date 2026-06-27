"""3wagent MCP server — access to reports, sources, routing config and analysis queue."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml
from mcp.server.fastmcp import FastMCP

from mcp_server.rag_index import RELIABILITY_RANK, connect, read_source, search_documents

ROOT = Path(__file__).resolve().parents[1]
REPORTS_ROOT = ROOT / "reports"
CONFIG_ROOT = ROOT / "config"
SOURCES_ROOT = ROOT / "sources"
SOURCE_INDEX_PATH = SOURCES_ROOT / "index.sqlite"

mcp = FastMCP("3wagent", instructions="MCP bridge for the 3wagent policy research workspace.")


def _report_id(report_dir: Path) -> str:
    return report_dir.name


def _list_report_dirs() -> list[Path]:
    if not REPORTS_ROOT.exists():
        return []
    return sorted(
        (d for d in REPORTS_ROOT.iterdir() if d.is_dir() and (d / "report.md").exists()),
        reverse=True,
    )


def _safe_report_dir(report_id: str) -> Path | None:
    if not report_id or Path(report_id).name != report_id or report_id in {".", ".."}:
        return None
    report_dir = REPORTS_ROOT / report_id
    try:
        report_dir.resolve().relative_to(REPORTS_ROOT.resolve())
    except ValueError:
        return None
    return report_dir


@mcp.tool()
async def report_artifact_list() -> str:
    """List all archived reports under reports/.

    Returns a JSON array of objects with id, date, topic and available files.
    """
    reports: list[dict[str, Any]] = []
    for report_dir in _list_report_dirs():
        report_id = _report_id(report_dir)
        # report_id format is YYYYMMDD-topic
        date_match = re.match(r"^(\d{8})-(.+)$", report_id)
        date = date_match.group(1) if date_match else ""
        topic = date_match.group(2) if date_match else report_id
        reports.append(
            {
                "id": report_id,
                "date": date,
                "topic": topic,
                "markdown": str(report_dir / "report.md"),
                "pdf": str(report_dir / "report.pdf") if (report_dir / "report.pdf").exists() else None,
            }
        )
    return json.dumps(reports, ensure_ascii=False, indent=2)


@mcp.tool()
async def report_artifact_read(report_id: str) -> str:
    """Read the Markdown content of a report by its report_id.

    Args:
        report_id: The report directory name, e.g. "20260620-hk-sg-service-fee".
    """
    report_dir = _safe_report_dir(report_id)
    if report_dir is None:
        return json.dumps({"error": f"Invalid report id: {report_id}"}, ensure_ascii=False)
    if not report_dir.exists():
        return json.dumps({"error": f"Report not found: {report_id}"}, ensure_ascii=False)
    markdown_path = report_dir / "report.md"
    if not markdown_path.exists():
        return json.dumps({"error": f"No report.md in {report_id}"}, ensure_ascii=False)
    return markdown_path.read_text(encoding="utf-8")


@mcp.tool()
async def source_registry_search(
    jurisdictions: list[str] | None = None,
    domains: list[str] | None = None,
    query: str | None = None,
    reliability: list[str] | None = None,
    limit: int = 20,
) -> str:
    """Search the curated source registries by jurisdiction and/or domain.

    Args:
        jurisdictions: Optional list of jurisdiction codes, e.g. ["CN", "HK"].
        domains: Optional list of domains, e.g. ["funds", "tax"].
        query: Optional issue or keyword query for lightweight scoring.
        reliability: Optional reliability levels, e.g. ["S", "A", "B"].
        limit: Maximum number of registry entries to return.
    """
    jurisdictions = [j.upper() for j in (jurisdictions or [])]
    domains = [d.lower() for d in (domains or [])]
    reliability = [r.upper() for r in (reliability or [])]
    query_terms = _query_terms(query or "")

    results: list[dict[str, Any]] = []
    if not SOURCES_ROOT.exists():
        return json.dumps(results, ensure_ascii=False, indent=2)

    for source_file in sorted(SOURCES_ROOT.glob("*.yaml")):
        data = yaml.safe_load(source_file.read_text(encoding="utf-8")) or {}
        jurisdiction = data.get("jurisdiction", "")
        if jurisdictions and jurisdiction.upper() not in jurisdictions:
            continue
        for source in data.get("sources", []):
            source_domains = {d.lower() for d in source.get("domains", [])}
            if domains and not source_domains.intersection(domains):
                continue
            source_reliability = str(source.get("reliability", "")).upper()
            if reliability and source_reliability not in reliability:
                continue
            entry = dict(source)
            entry["jurisdiction"] = jurisdiction
            entry["score"] = _registry_score(entry, query_terms)
            entry["applicable_point"] = _applicable_point(entry, query_terms)
            results.append(entry)

    results.sort(
        key=lambda item: (
            item.get("score", 0),
            RELIABILITY_RANK.get(str(item.get("reliability", "")), 0),
        ),
        reverse=True,
    )
    results = results[: max(1, min(limit, 100))]
    return json.dumps(results, ensure_ascii=False, indent=2)


@mcp.tool()
async def source_document_search(
    query: str,
    jurisdictions: list[str] | None = None,
    domains: list[str] | None = None,
    reliability: list[str] | None = None,
    limit: int = 10,
) -> str:
    """Search the local SQLite RAG index of source snapshots.

    Args:
        query: Keyword or issue query to search in indexed source chunks.
        jurisdictions: Optional jurisdiction filters, e.g. ["CN", "SG"].
        domains: Optional domain filters, e.g. ["tax"].
        reliability: Optional reliability levels, e.g. ["S", "A", "B"].
        limit: Maximum number of source chunks to return.
    """
    if not SOURCE_INDEX_PATH.exists():
        return json.dumps(
            {
                "error": "source index not found",
                "index_path": str(SOURCE_INDEX_PATH),
                "hint": "Run tools/ingest_sources.py to create sources/index.sqlite.",
            },
            ensure_ascii=False,
            indent=2,
        )
    with connect(SOURCE_INDEX_PATH) as conn:
        results = search_documents(
            conn,
            query,
            jurisdictions=jurisdictions,
            domains=domains,
            reliability=reliability,
            limit=limit,
        )
    return json.dumps(results, ensure_ascii=False, indent=2)


@mcp.tool()
async def source_document_read(source_id: str) -> str:
    """Read all indexed chunks for one source_id from the local RAG index.

    Args:
        source_id: Stable source id from sources/*.yaml.
    """
    if not SOURCE_INDEX_PATH.exists():
        return json.dumps(
            {"error": "source index not found", "index_path": str(SOURCE_INDEX_PATH)},
            ensure_ascii=False,
            indent=2,
        )
    with connect(SOURCE_INDEX_PATH) as conn:
        result = read_source(conn, source_id)
    if result is None:
        return json.dumps({"error": f"source not indexed: {source_id}"}, ensure_ascii=False, indent=2)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def routing_classify(question: str) -> str:
    """Pre-classify a policy question using the routing config keyword rules.

    Args:
        question: The user's policy question in Chinese or English.
    """
    routing_path = CONFIG_ROOT / "routing.yaml"
    if not routing_path.exists():
        return json.dumps({"error": "routing.yaml not found"}, ensure_ascii=False)

    routing = yaml.safe_load(routing_path.read_text(encoding="utf-8")) or {}
    question_lower = question.lower()
    matches: list[dict[str, Any]] = []

    for classification in routing.get("classifications", []):
        keywords = [kw.lower() for kw in classification.get("keywords", [])]
        if any(kw in question_lower for kw in keywords):
            matches.append(
                {
                    "id": classification.get("id"),
                    "label": classification.get("label"),
                    "agent": classification.get("agent"),
                    "matched_keywords": [kw for kw in keywords if kw in question_lower],
                }
            )

    # Simple subdomain matching
    subdomain_matches: list[dict[str, Any]] = []
    for domain, subdomains in routing.get("subdomains", {}).items():
        for subdomain in subdomains:
            keywords = [kw.lower() for kw in subdomain.get("keywords", [])]
            if any(kw in question_lower for kw in keywords):
                subdomain_matches.append(
                    {
                        "domain": domain,
                        "id": subdomain.get("id"),
                        "label": subdomain.get("label"),
                        "matched_keywords": [kw for kw in keywords if kw in question_lower],
                    }
                )

    return json.dumps(
        {
            "classifications": matches,
            "subdomains": subdomain_matches,
            "primary_agent": matches[0].get("agent") if matches else None,
        },
        ensure_ascii=False,
        indent=2,
    )


def _query_terms(query: str) -> list[str]:
    return [term.lower() for term in re.findall(r"[\w\u4e00-\u9fff]+", query) if term.strip()]


def _registry_score(source: dict[str, Any], query_terms: list[str]) -> int:
    score = RELIABILITY_RANK.get(str(source.get("reliability", "")), 0) * 10
    if not query_terms:
        return score
    haystacks = {
        "title": str(source.get("title", "")).lower(),
        "authority": str(source.get("authority", "")).lower(),
        "notes": str(source.get("notes", "")).lower(),
        "source_type": str(source.get("source_type", "")).lower(),
        "domains": " ".join(source.get("domains", [])).lower(),
        "subdomains": " ".join(source.get("subdomains", [])).lower(),
    }
    for term in query_terms:
        score += haystacks["title"].count(term) * 8
        score += haystacks["authority"].count(term) * 4
        score += haystacks["domains"].count(term) * 3
        score += haystacks["subdomains"].count(term) * 3
        score += haystacks["notes"].count(term) * 2
        score += haystacks["source_type"].count(term)
    return score


def _applicable_point(source: dict[str, Any], query_terms: list[str]) -> str:
    notes = str(source.get("notes", "")).strip()
    if notes:
        return notes
    domains = ", ".join(source.get("domains", []))
    query = ", ".join(query_terms[:5])
    if query:
        return f"Potential {domains or 'policy'} source for query terms: {query}."
    return f"Potential {domains or 'policy'} source from the curated registry."


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
