# policy-research

Answer cross-border policy questions for the United States, Mainland China, Hong Kong or Singapore.

## When to use

- The user asks a cross-border policy question.
- Multiple domains (funds, tax, commercial) may be involved.
- A structured policy report is required.

## Steps

1. **Frame** — Write down the issue profile, domains, jurisdictions, retrieval plan, required skills and output contract.
2. **Parse** — If documents are attached, use `document-parse` first and preserve page/location markers. (Input is text-only by default.)
3. **Classify** — Determine the nature of the problem:
   - Pure funds-forex (e.g., SAFE rules, settlement/sale, current/capital account)
   - Pure funds-banking (e.g., AML, KYC, sanctions, payment licensing)
   - Pure tax (e.g., withholding, profits tax, GST, treaty)
   - Cross-domain (list all involved sub-domains)
   Also identify transaction type (goods trade, services, investment, lending, etc.).
4. **Identify** — Determine jurisdiction, parties, transaction type and payment character. Distinguish funds-forex from funds-banking using keywords: SAFE, 外汇管理局, 结售汇, 资本项目 → forex; AML, KYC, 制裁, sanctions, OFAC → banking.
5. **Route** — Decide which domains to analyze:
   - Funds → `funds-compliance-analyst`
   - Tax → `tax-policy-analyst`
   - Commercial → `commercial-law-analyst`
   - Combined → multiple analysts in parallel
6. **Retrieve** — Run `rag-retrieval` before writing any conclusion. Include case-law database searches for analogous judgments.
7. **Validate** — Run `regulatory-validity-verification` on source packs. Trace single-tier amendment lineage.
8. **Analyze** — Delegate to specialist subagents with full task packages.
9. **Verify** — Run `citation-verification` before finalizing.
10. **Synthesize** — Write the final report in the main session. Address all 5 required output items.

## Domain notes

- **Funds-forex** (外汇管理) — SAFE rules, foreign exchange administration, settlement and sale of foreign exchange, current-account and capital-account controls, cross-border payment filing. Keywords: 外汇管理局, SAFE, 结售汇, 资本项目, 经常项目.
- **Funds-banking** (银行合规/AML/制裁) — AML, KYC, sanctions (OFAC, UN), source-of-funds, payment licensing, bank practice. Keywords: AML, KYC, 反洗钱, 制裁, sanctions, OFAC.
- Do not assume China-style FX approval applies outside Mainland China. When Mainland China is involved, explicitly check SAFE, current-account, capital-account, settlement, sale and payment rules.
- Tax issues depend on payment characterization and tax residency.
- Commercial law issues include company formation, contracts, share transfers, registration and licenses.

## Output contract

The final report must contain exactly these 5 items (Chinese by default):

1. **【问题分类】** — Problem classification and sub-domains.
2. **【结论或考量维度】** — Direct conclusions or dimensions to consider.
3. **【类案与公开答案】** — Analogous public judgments with quoted excerpts.
4. **【涉及现行法规】** (Priority) — Complete numbered list of currently effective regulations.
5. **【法规修订关系】** — Single-tier amendment lineage for each effective regulation.
