# policy-research

Answer cross-border policy questions for the United States, Mainland China, Hong Kong or Singapore.

## When to use

- The user asks a cross-border policy question.
- Multiple domains (funds, tax, commercial) may be involved.
- A structured policy report is required.

## Steps

1. **Frame** — Write down the issue profile, domains, jurisdictions, retrieval plan, required skills and output contract.
2. **Parse** — If documents are attached, use `document-parse` first and preserve page/location markers. (Input is text-only by default.)
3. **Classify** — Determine the nature of the problem per `config/routing.yaml`:
   - Pure funds-forex, pure funds-banking, pure tax, or cross-domain.
   - Use the keyword lists in `config/routing.yaml` to distinguish.
   - Also identify transaction type (goods trade, services, investment, lending, etc.).
4. **Identify** — Determine jurisdiction, parties, transaction type and payment character. Sub-domain keywords are in `config/routing.yaml`.
5. **Route** — Decide which domains to analyze per `config/routing.yaml` agent mappings:
   - Funds → `funds-compliance-analyst`
   - Tax → `tax-policy-analyst`
   - Commercial → `commercial-law-analyst`
   - Combined → multiple analysts in parallel
6. **Retrieve** — Run `rag-retrieval` before writing any conclusion. Include case-law database searches for analogous judgments.
7. **Validate** — Run `regulatory-validity-verification` on source packs. Trace single-tier amendment lineage.
8. **Analyze** — Delegate to specialist subagents with full task packages.
9. **Verify** — Run `citation-verification` before finalizing.
10. **Synthesize** — Write the final report in the main session. Address all required output sections per `config/output-contract.yaml`.

## Domain notes

- Do not assume China-style FX approval applies outside Mainland China. When Mainland China is involved, explicitly check SAFE, current-account, capital-account, settlement, sale and payment rules.
- Tax issues depend on payment characterization and tax residency.
- Commercial law issues include company formation, contracts, share transfers, registration and licenses.

## Output contract

The final report must contain the required sections defined in `config/output-contract.yaml` — 5 required sections (Chinese by default) plus 3 supporting sections. Section 4 (涉及现行法规) is the priority.
