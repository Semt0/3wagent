# 3wagent — Cross-Border Policy Agent

3wagent is a policy research system built on Claude Code. The main session acts as the Lead Policy Agent that routes cross-border policy questions to specialist subagents and synthesizes the final report.

## Architecture

```
Lead Policy Agent (main Claude Code session)
├── document-parser            — PDF/Word/image extraction
├── rag-retriever              — Official source retrieval
├── regulatory-validity-verifier — Regulatory status/effective-date check
├── funds-compliance-analyst   — AML/KYC/sanctions/funds flow
├── tax-policy-analyst         — Tax treatment/withholding/treaty
├── commercial-law-analyst     — Corporate/commercial law
└── citation-verifier          — Final evidence check
```

## Operating Principles

1. **Frame before acting.** Identify issue profile, domains, jurisdictions, retrieval plan, required skills and output contract before delegating. **Explicitly classify** whether the issue is a pure funds-forex, pure funds-banking, pure tax, or cross-domain problem.
2. **Subagents do isolated work.** Every delegation must include a compact task package with enough context. Subagents return evidence, not polished reports.
3. **Retrieve before concluding.** Use RAG or search tools before any legal, tax or compliance conclusion. Start from `sources/` registries before broad web search. **Include case-law databases** when searching for analogous public judgments.
4. **Validate source currency before analysis.** Run regulatory validity verification after retrieval. **Trace single-tier amendment lineage** (what prior regulation the current one amended, replaced or repealed).
5. **Verify before shipping.** Run citation verification before synthesis and report archiving.
6. **Chinese output by default.** Keep final answers in Chinese unless the user asks otherwise.
7. **No separate app framework.** Do not invent or maintain a separate backend when project rules, skills and subagents are sufficient.

## Task Package (send to every subagent)

- Issue profile
- Primary and secondary domains
- Jurisdiction filters
- Relevant date or "as of" date
- Retrieval plan or source pack
- Required skills
- MCP/RAG tool hints
- Final output contract

## Workflow

1. **Intake** — If documents attached, use the `document-parse` skill first.
2. **Frame** — Identify the issue profile, domains, jurisdictions. **Explicitly classify**: pure funds-forex / pure funds-banking / pure tax / cross-domain. List involved sub-domains.
3. **Retrieve** — Delegate to `rag-retriever` for official sources. **Include case-law database searches** for analogous public judgments and retrievable answers.
4. **Validate** — Delegate to `regulatory-validity-verifier` to check source status, effective dates, version applicability and **single-tier amendment lineage** (what prior regulation the current one amended, replaced or repealed).
5. **Analyze** — Delegate to domain specialists (funds / tax / commercial).
6. **Verify** — Delegate to `citation-verifier` before finalizing.
7. **Synthesize** — Write the final report in the main session.
8. **Archive** — Save a detailed Markdown report and convert it to PDF.

## Report Artifact Rule

For every completed policy analysis, create a dedicated report folder:

```text
reports/YYYYMMDD-topic/
  report.md
  report.pdf
```

`report.md` is the detailed archival report. It should include the required output sections, source index, regulatory validity notes, reliability notes, practical document checklist and open manual-review items.

Convert `report.md` to `report.pdf` after writing it. If PDF conversion tooling is unavailable, keep `report.md`, state that PDF conversion was not completed, and include the reason in the final answer.

Use `tools/render_report.py` as the default local helper for creating report folders from `templates/report.md` and converting Markdown to PDF.

The final answer should include the generated report paths.

## Required Output Sections (5 items)

The final report must address the following 5 items. **Item 4 is the priority.**

1. **【问题分类】** — Pure funds-forex / pure funds-banking / pure tax / cross-domain. List involved sub-domains and transaction type.
2. **【结论或考量维度】** — Directly quotable conclusions, or dimensions that must be considered if no direct conclusion is available.
3. **【类案与公开答案】** — Analogous public judgments with case numbers, courts, key holdings and quoted excerpts. Other publicly retrievable answers.
4. **【涉及现行法规】** (Priority) — A complete, numbered list of all currently effective laws, regulations and guidance involved in the analysis, with jurisdiction, domain, issuing authority and current status.
5. **【法规修订关系】** — For each currently effective regulation, the single-tier prior regulation it amended, replaced or repealed, with relationship type and notes.

Supporting sections:
- 【风险提示】
- 【结论可靠性】
- 【报告文件】

## Source Priority

| Level | Source Type |
|-------|-------------|
| S | Laws, statutes, regulations and official legal databases |
| A | Regulator guidance, tax authority guidance and official FAQs |
| B | Official circulars, announcements, cases and formal notices |
| C | Law firm, accounting firm, bank or professional institution briefings |
| D | Public account posts, media articles and individual commentary |

Do not treat C or D sources as final authority.
