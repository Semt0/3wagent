# policy-research

Answer cross-border policy questions for the United States, Mainland China, Hong Kong or Singapore.

## When to use

- The user asks a cross-border policy question.
- Multiple domains (funds, tax, commercial) may be involved.
- A structured policy report is required.

## Steps

1. **Frame** — Write down the issue profile, domains, jurisdictions, retrieval plan, required skills and output contract.
2. **Parse** — If documents are attached, use `document-parse` first and preserve page/location markers.
3. **Identify** — Determine jurisdiction, parties, transaction type and payment character.
4. **Route** — Decide which domains to analyze:
   - Funds → `funds-compliance-analyst`
   - Tax → `tax-policy-analyst`
   - Commercial → `commercial-law-analyst`
   - Combined → multiple analysts in parallel
5. **Retrieve** — Run `rag-retrieval` before writing any conclusion.
6. **Analyze** — Delegate to specialist subagents with full task packages.
7. **Verify** — Run `citation-verification` before finalizing.
8. **Synthesize** — Write the final report in the main session.

## Domain notes

- Funds issues mean AML, KYC, sanctions, source-of-funds, China SAFE / foreign exchange administration when Mainland China is involved, and bank practice.
- Do not assume China-style FX approval applies outside Mainland China. When Mainland China is involved, explicitly check SAFE, current-account, capital-account, settlement, sale and payment rules.
- Tax issues depend on payment characterization and tax residency.
- Commercial law issues include company formation, contracts, share transfers, registration and licenses.
