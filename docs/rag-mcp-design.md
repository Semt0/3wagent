# RAG and MCP Tool Design

This document defines the next engineering layer for 3wagent without requiring a separate app runtime today. The current implementation remains agent-native: Claude Code or Codex reads project rules, source registries and templates directly.

## Goals

- Make retrieval start from curated official sources before open web search.
- Preserve jurisdiction, domain and reliability metadata with every source.
- Keep citation verification separate from specialist analysis.
- Provide a clear migration path to MCP tools when repeated manual steps become frequent.

## Current Assets

- `sources/us.yaml`
- `sources/hk.yaml`
- `sources/sg.yaml`
- `templates/retrieval-task.md`
- `.claude/agents/rag-retriever.md`
- `.claude/skills/rag-retrieval.md`
- `.claude/skills/source-ingestion.md`
- `.claude/skills/citation-verification.md`

## Source Entry Contract

Every source entry should preserve:

```yaml
id: stable-source-id
title: Source title
authority: Issuing authority or official database
url: Canonical URL
domains: [funds, tax, commercial]
reliability: S
source_type: official legal database
notes: Retrieval notes and known limits
```

The retrieval layer should never strip metadata. Final analysis needs the metadata to check whether a conclusion is supported by the correct jurisdiction, domain and reliability level.

## Retrieval Flow

1. Identify jurisdictions and domains from the user's issue profile.
2. Read the matching registry files under `sources/`.
3. Select likely official sources by `domains` and `reliability`.
4. Fetch or search within official sources first.
5. Use broad web search only when the registry does not cover the issue.
6. Label each result with source metadata and a short applicable point.
7. Flag any conclusion that lacks `S`, `A` or `B` support.

## Proposed MCP Tools

### `source_registry.search`

Input:

```json
{
  "jurisdictions": ["HK", "SG"],
  "domains": ["tax", "funds"],
  "query": "service fee withholding tax and cross-border payment"
}
```

Output:

```json
{
  "sources": [
    {
      "id": "sg-iras-withholding-tax",
      "title": "Withholding Tax",
      "authority": "Inland Revenue Authority of Singapore",
      "url": "https://www.iras.gov.sg/taxes/withholding-tax",
      "jurisdiction": "SG",
      "domains": ["tax"],
      "reliability": "A",
      "applicable_point": "Singapore withholding tax entry point"
    }
  ]
}
```

### `official_site.fetch`

Input:

```json
{
  "url": "https://www.ird.gov.hk/eng/ppr/dipn.htm",
  "expected_authority": "Inland Revenue Department"
}
```

Output:

```json
{
  "url": "https://www.ird.gov.hk/eng/ppr/dipn.htm",
  "retrieved_at": "2026-06-01T00:00:00+08:00",
  "title": "Departmental Interpretation and Practice Notes",
  "text_excerpt": "...",
  "snapshot_path": "sources/snapshots/..."
}
```

### `official_site.search`

Input:

```json
{
  "authority": "Internal Revenue Service",
  "site": "irs.gov",
  "query": "withholding foreign entity service fee"
}
```

Output should include candidate URLs, titles, authority match notes and whether the result is official.

### `citation_checker.verify`

Input:

```json
{
  "claim": "Singapore service fees may require withholding analysis depending on the income character.",
  "jurisdiction": "SG",
  "domain": "tax",
  "source_ids": ["sg-iras-withholding-tax"]
}
```

Output should classify the claim as:

- Supported by official authority
- Likely but requiring manual review
- Secondary-source lead only
- No reliable source found

### `report_artifact.write`

Wraps `tools/render_report.py`.

Input:

```json
{
  "title": "HK to SG Service Fee Policy Analysis",
  "topic": "hk-sg-service-fee",
  "markdown": "..."
}
```

Output:

```json
{
  "report_dir": "reports/20260601-hk-sg-service-fee",
  "markdown": "reports/20260601-hk-sg-service-fee/report.md",
  "pdf": "reports/20260601-hk-sg-service-fee/report.pdf",
  "pdf_status": "generated"
}
```

## Non-Goals For Now

- No persistent vector database until source volume justifies it.
- No separate FastAPI or LangChain runtime for the MVP.
- No automated legal conclusion without citation verification.
- No C or D source promotion to final authority.

## Implementation Order

1. Keep registries human-readable and agent-readable.
2. Add lightweight validation only when registry churn increases.
3. Build MCP wrappers around stable repeated workflows.
4. Add vector or full-text indexes only after the curated registry is no longer enough.
