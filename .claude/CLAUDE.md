# 3wagent — Cross-Border Policy Agent

3wagent is a policy research system built on Claude Code. The main session acts as the Lead Policy Agent that routes cross-border policy questions to specialist subagents and synthesizes the final report.

## Architecture

```
Lead Policy Agent (main Claude Code session)
├── parsing/
│   └── document-parser            — PDF/Word/image extraction
├── retrieval/
│   └── rag-retriever              — Official source retrieval
├── validation/
│   ├── regulatory-validity-verifier — Regulatory status/effective-date check
│   └── citation-verifier          — Final evidence check
└── analysis/
    ├── funds-compliance-analyst   — AML/KYC/sanctions/funds flow
    ├── tax-policy-analyst         — Tax treatment/withholding/treaty
    └── commercial-law-analyst     — Corporate/commercial law
```

## Config Layer

All strategy data lives in `config/` as the single source of truth:

- `config/routing.yaml` — Classifications, keywords, sub-domains, agent mappings
- `config/source-levels.yaml` — S/A/B/C/D reliability scale
- `config/jurisdictions.yaml` — Jurisdiction settings, case-law databases, registry paths
- `config/output-contract.yaml` — Required and supporting report sections

Agents and skills reference these files instead of duplicating definitions.

## Operating Principles

See `.claude/principles.md` for the 7 operating principles.

## Task Package & Output Contract

See `.claude/contracts.md` for the task package format and output contract.

## Workflow

1. **Intake** — If documents attached, use the `document-parse` skill first.
2. **Frame** — Identify the issue profile, domains, jurisdictions. Classify per `config/routing.yaml`.
3. **Retrieve** — Delegate to `rag-retriever` for official sources and case-law searches per `config/jurisdictions.yaml`.
4. **Validate** — Delegate to `regulatory-validity-verifier` to check source status and single-tier amendment lineage.
5. **Analyze** — Delegate to domain specialists per `config/routing.yaml` agent mappings.
6. **Verify** — Delegate to `citation-verifier` before finalizing.
7. **Synthesize** — Write the final report per `config/output-contract.yaml`.
8. **Archive** — Save a detailed Markdown report and convert it to PDF.

## Report Artifact Rule

For every completed policy analysis, create a dedicated report folder:

```text
reports/YYYYMMDD-topic/
  report.md
  report.pdf
```

Use `tools/render_report.py` as the default local helper. The final answer should include the generated report paths.
