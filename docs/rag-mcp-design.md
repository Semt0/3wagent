# RAG and MCP Tool Design

This document defines the next engineering layer for 3wagent without requiring a separate app runtime today. The current implementation remains agent-native: Claude Code or Codex reads project rules, source registries and templates directly.

## Goals

- Make retrieval start from curated official sources before open web search.
- Preserve jurisdiction, domain and reliability metadata with every source.
- Verify regulatory validity, effective dates and version applicability before analysis.
- Keep citation verification separate from specialist analysis.
- Provide a clear migration path to MCP tools when repeated manual steps become frequent.

## Current Assets

- `sources/cn.yaml`
- `sources/us.yaml`
- `sources/hk.yaml`
- `sources/sg.yaml`
- `templates/retrieval-task.md`
- `.claude/agents/rag-retriever.md`
- `.claude/agents/regulatory-validity-verifier.md`
- `.claude/skills/rag-retrieval.md`
- `.claude/skills/regulatory-validity-verification.md`
- `.claude/skills/source-ingestion.md`
- `.claude/skills/citation-verification.md`

## Source Entry Contract

Every source registry should preserve the jurisdiction at the top level and source metadata on each entry:

```yaml
jurisdiction: CN
sources:
  - id: stable-source-id
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
7. Run regulatory validity verification for source status, effective dates, replacements and applicable versions.
8. Flag any conclusion that lacks `S`, `A` or `B` support.

## Proposed MCP Tools

### `source_registry.search`

Input:

```json
{
  "jurisdictions": ["CN", "HK"],
  "domains": ["funds", "tax"],
  "query": "Mainland China foreign exchange settlement cross-border service fee payment"
}
```

For Mainland China funds questions, use `CN` and include foreign exchange terms such as SAFE, current account, capital account, settlement and sale of foreign exchange, foreign debt, outbound investment or cross-border guarantee.

Output:

```json
{
  "sources": [
    {
      "id": "cn-safe-policy-regulations",
      "title": "Policy and Regulation Index",
      "authority": "State Administration of Foreign Exchange",
      "url": "https://www.safe.gov.cn/safe/zcfg/index.html",
      "jurisdiction": "CN",
      "domains": ["funds"],
      "reliability": "A",
      "applicable_point": "SAFE official policy and regulation index for foreign exchange administration"
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

### `regulatory_validity.verify`

Input:

```json
{
  "relevant_date": "2026-06-01",
  "sources": [
    {
      "id": "cn-foreign-exchange-regulations",
      "title": "Regulations of the People's Republic of China on Foreign Exchange Administration",
      "authority": "State Council of the People's Republic of China",
      "url": "https://www.gov.cn/zwgk/2008-08/06/content_1065910.htm",
      "jurisdiction": "CN",
      "domains": ["funds"],
      "reliability": "S"
    }
  ]
}
```

Output:

```json
{
  "validity_findings": [
    {
      "source_id": "cn-foreign-exchange-regulations",
      "publication_date": "2008-08-05",
      "effective_date": "2008-08-05",
      "current_status": "Currently effective",
      "applicable_to_relevant_date": true,
      "replacement_or_amendment": null,
      "notes": "Verify against the official legal database or State Council page before final citation."
    }
  ]
}
```

Validity labels:

- Currently effective
- Likely effective but requiring manual review
- Historical version / replaced
- Repealed / should not be relied on
- Unable to confirm validity

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
