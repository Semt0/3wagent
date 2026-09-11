# Retrieval Task Package

Use this template when the Lead Policy Agent delegates retrieval to `rag-retriever`.

## Issue Profile

- User question:
- **Classification:** (funds-forex / funds-banking / tax / commercial / cross-domain)
- **Sub-domains:** (e.g., funds-forex, funds-AML, tax-withholding, securities-regulation)
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

## Case-Law Search Plan

For each relevant jurisdiction, search official case-law databases:

- **CN**: 中国裁判文书网 (`wenshu.court.gov.cn`) — search by keywords matching the transaction type and domain.
- **HK**: Hong Kong Legal Information Institute (`www.hklii.hk`) — search for analogous judgments.
- **SG**: Singapore Courts (`www.judiciary.gov.sg`) or LawNet — search for relevant cases.
- **US**: CourtListener (`www.courtlistener.com`) or Justia — search for federal or state court decisions.

For each case found, record: case number/name, court, jurisdiction, key holdings and **quoted excerpts** if the full text is accessible. If full text is not accessible, note the retrieval limitation.

## Search Plan

1. Start from S and A sources in the registry.
2. Fetch official laws, regulations, regulator guidance or tax authority pages.
3. Search official sites only if the registry does not identify a precise source.
4. **Search case-law databases** for analogous public judgments and retrievable answers.
5. Use C or D sources only as leads, not as final authority.
6. Record gaps where no official support is found.

## Required Output

Return a source pack, not a final report.

### For each regulatory source:

- `id` if it exists in `sources/`
- title
- authority
- URL
- jurisdiction
- domains / sub-domains
- reliability level
- source type
- publication date, effective date, amendment date, repeal or expiry date, retrieved date and status if available
- applicable point
- limits or manual-review notes

### For case-law sources:

- case number / name
- court
- jurisdiction
- domain relevance
- key holdings (2-3 sentences)
- quoted excerpt (if accessible)
- retrieval source URL
- access limitation notes

### Required additional outputs

1. **Involved currently-effective regulations list** — A numbered list of all currently effective laws, regulations and guidance that are relevant to the issue, with jurisdiction, domain and issuing authority. This is the priority output.
2. **Amendment lineage leads** — For each currently effective regulation, note any visible amendment, replacement or repeal relationship with a prior regulation (single-tier only).

## Prohibited Output

- Do not write final legal, tax or compliance conclusions.
- Do not rely on C or D sources as final authority.
- Do not omit jurisdiction or reliability metadata.
- Do not mix official support and commentary without labeling the difference.
