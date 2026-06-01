# Retrieval Task Package

Use this template when the Lead Policy Agent delegates retrieval to `rag-retriever`.

## Issue Profile

- User question:
- Extracted facts:
- Transaction type:
- Payment or asset character:
- Parties and roles:
- Time sensitivity:
- Relevant date or "as of" date:

## Jurisdiction Filters

- Primary jurisdictions:
- Secondary jurisdictions:
- Excluded jurisdictions:

## Domain Filters

- Primary domain:
- Secondary domains:
- Out-of-scope domains:

Allowed domains:

- `funds`
- `tax`
- `commercial`

When Mainland China is involved in a funds issue, include foreign exchange administration in the funds domain. Check SAFE rules for current-account payments, capital-account items, settlement and sale of foreign exchange, foreign debt, outbound investment, cross-border guarantees and registration or filing requirements.

## Registry First Pass

Read the matching files under `sources/` before broad web search:

- `sources/cn.yaml`
- `sources/us.yaml`
- `sources/hk.yaml`
- `sources/sg.yaml`

Select candidate sources by:

- jurisdiction match
- domain match
- reliability level
- authority relevance
- whether the source can support the exact claim

## Search Plan

1. Start from S and A sources in the registry.
2. Fetch official laws, regulations, regulator guidance or tax authority pages.
3. Search official sites only if the registry does not identify a precise source.
4. Use C or D sources only as leads, not as final authority.
5. Record gaps where no official support is found.

## Required Output

Return a source pack, not a final report.

For each source:

- `id` if it exists in `sources/`
- title
- authority
- URL
- jurisdiction
- domains
- reliability level
- source type
- publication date, effective date, amendment date, repeal or expiry date, retrieved date and status if available
- applicable point
- limits or manual-review notes

## Prohibited Output

- Do not write final legal, tax or compliance conclusions.
- Do not rely on C or D sources as final authority.
- Do not omit jurisdiction or reliability metadata.
- Do not mix official support and commentary without labeling the difference.
