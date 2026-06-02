# rag-retrieval

Retrieve policy sources with jurisdiction, domain and reliability metadata.

## When to use

- Before writing any legal, tax or compliance conclusion.
- When the user question references a specific jurisdiction or domain.
- After the `source-ingestion` skill when building a source pack.

## Steps

1. Apply jurisdiction filters first (US, Mainland China, Hong Kong, Singapore).
2. Apply domain filters second (funds, tax, commercial). **Distinguish sub-domains:**
   - Funds-forex: SAFE, 外汇管理局, 结售汇, 经常项目, 资本项目, 跨境收支
   - Funds-banking: AML, KYC, 反洗钱, 制裁, sanctions, OFAC, 支付牌照
3. Read matching registry files under `sources/`:
   - `sources/cn.yaml`
   - `sources/us.yaml`
   - `sources/hk.yaml`
   - `sources/sg.yaml`
4. Use `templates/retrieval-task.md` to normalize incomplete retrieval requests.
5. Query with the user's issue profile.
6. Score and filter by reliability:
   - Prefer S and A sources.
   - Use B sources as supporting evidence.
   - Use C and D sources only as leads.
7. **Search case-law databases** for analogous judgments per jurisdiction:
   - CN: 中国裁判文书网 (`wenshu.court.gov.cn`)
   - HK: HKLII (`www.hklii.hk`)
   - SG: Singapore Courts (`www.judiciary.gov.sg`)
   - US: CourtListener (`www.courtlistener.com`)
   For each case: record case number/name, court, key holdings, quoted excerpt if accessible, and access limitations.
8. Record for each regulatory result: source id, title, authority, URL, jurisdiction, domain, sub-domain, reliability level, applicable point and available date/status metadata.
9. **Build a numbered list of all involved currently-effective regulations** with jurisdiction, domain, issuing authority and current status. This is the priority output.
10. Note visible amendment, replacement or repeal relationships (single-tier only) as leads for the validity verifier.
11. If official support is missing, flag the conclusion as preliminary.

## Output

Concise source packs with metadata. Include:
- Regulatory source pack (with sub-domain labels where applicable)
- Case-law search results (with quoted excerpts or access limitations)
- **Numbered list of involved currently-effective regulations (priority)**
- Amendment lineage leads (single-tier)

Do not write the final report.
