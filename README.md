<h1 align="center">3wagent</h1>

<p align="center">
  <strong>Personal Cross-Border Policy Research Agent Workspace</strong><br>
  Claude Code subagents for issue routing, policy retrieval, regulatory validity checks and report archiving
</p>

<p align="center">
  <a href="README.zh-CN.md">简体中文</a>
  ·
  <a href="CHANGELOG.md">CHANGELOG</a>
</p>

---

## Quick Start

Clone the repository locally:

```bash
git clone git@github.com:Semt0/3wagent.git
cd 3wagent
```

If you use Claude Code, open it in the repository directory. `.claude/CLAUDE.md` is loaded automatically as project memory.

If you use Codex, explicitly ask it to read the project rules:

```text
Read .claude/CLAUDE.md and analyze my question using the 3wagent workflow.
```

Then ask a policy question directly:

```text
What tax and banking compliance issues should a Hong Kong company consider when paying service fees to a Singapore company?
```

Or attach a PDF / Word document and ask for an analysis:

```text
Analyze the cross-border payment, tax and corporate law risks in this agreement.
```

The agent should produce:

```text
1. A plain-text answer in the conversation
2. reports/YYYYMMDD-topic/report.md
3. reports/YYYYMMDD-topic/report.pdf
```

---

## Motivation

3wagent is not trying to become a heavy legal-tech application first. It is a personal research workspace for cross-border policy analysis.

The current jurisdiction scope covers Mainland China, the United States, Hong Kong and Singapore.

At this stage, the valuable part is the decision boundary:

- when funds flow, banking compliance, AML and sanctions should lead
- when tax analysis should stand alone
- when corporate and commercial law should be added
- which sources can support conclusions
- how to produce a stable source index and risk summary

The project therefore does not maintain its own FastAPI / LangChain / LangGraph runtime for the MVP. Instead, it keeps the reusable domain logic in Claude Code rules, skills and project subagents.

---

## Features

| Feature | Description |
|---------|-------------|
| Issue routing & classification | Identify jurisdictions, transaction type, payment character and primary domain; classify as pure funds-forex / pure funds-banking / pure tax / cross-domain |
| Document parsing | Use the built-in `liteparse` skill for PDF / Word / scanned materials |
| Subagent analysis | Split funds compliance (forex vs banking/AML), tax and commercial law into specialist agents |
| Policy retrieval | Start from `sources/`, then filter by CN / US / HK / SG and funds / tax / commercial domains |
| Case-law retrieval | Search official case databases (wenshu, HKLII, Singapore Courts, CourtListener) for analogous judgments |
| Regulatory validity | Check whether laws, notices, guidance and official cases are current, replaced, repealed or time-limited; trace single-tier amendment lineage |
| Citation verification | Check whether conclusions match the cited jurisdiction and source; verify case citations and amendment lineage |
| Report archive | Generate both `report.md` and `report.pdf` under `reports/` |

---

## What Claude Code Does

For a direct policy question:

```text
1. The Lead Policy Agent identifies jurisdiction, parties, transaction and payment character
2. It classifies the issue: pure funds-forex / pure funds-banking / pure tax / cross-domain
3. It delegates source retrieval to rag-retriever, starting from `sources/`
4. It runs regulatory-validity-verifier for source status, effective dates, version applicability and single-tier amendment lineage
5. It calls the relevant specialist subagents
6. It runs citation-verifier (including case-law citations and amendment lineage)
7. It writes the final answer with 5 required output items
8. It saves reports/YYYYMMDD-topic/report.md
9. It converts the Markdown report to PDF
```

For an attached document:

```text
1. document-parser extracts the file
   └─ prefers liteparse
   └─ preserves page markers, headings, tables, footnotes and OCR uncertainty

2. The Lead Policy Agent extracts transaction facts
   └─ parties, amount, currency, payment path, contract type and income type

3. rag-retriever checks the `sources/` registry and gathers source packs
   └─ official laws and regulator guidance first
   └─ professional commentary and public account posts as leads only

4. regulatory-validity-verifier checks status, effective dates and replacement notes
5. Specialist subagents analyze the issue
6. citation-verifier checks evidence
7. The final answer and report files are generated
```

---

## Agent Team

```text
Lead Policy Agent (main session)
│
├── document-parser
│   └── PDF / Word / image / table extraction, no legal analysis
│
├── rag-retriever
│   └── Official policy, law, regulator guidance and secondary source retrieval
│
├── regulatory-validity-verifier
│   └── Source status, effective-date and version-applicability checks
│
├── funds-compliance-analyst
│   └── Funds flow, bank KYC, AML/CFT, OFAC, sanctions and payment licensing
│
├── tax-policy-analyst
│   └── Withholding, profits tax, income tax, GST/VAT, treaty analysis
│
├── commercial-law-analyst
│   └── Formation, share transfer, contracts, director duties, licenses
│
└── citation-verifier
    └── Citation support, jurisdiction match, source level and reliability
```

The main session handles orchestration, conflict resolution and final writing. Subagents handle self-contained specialist work.

---

## Workflow

```text
User question or PDF / Word input
  ↓
Lead Policy Agent frames issue, jurisdictions and domains
  ↓
If files are attached, document-parser uses liteparse
  ↓
Lead Policy Agent creates task packages and chooses subagents
  ↓
rag-retriever checks `sources/`, then gathers official and secondary sources
  ↓
regulatory-validity-verifier checks source status, versions and applicable dates
  ↓
Specialist subagents analyze
  ├── funds-compliance-analyst
  ├── tax-policy-analyst
  └── commercial-law-analyst
  ↓
citation-verifier checks support and reliability
  ↓
Lead Policy Agent writes the final answer
  ↓
reports/YYYYMMDD-topic/report.md is created
  ↓
report.md is converted to report.pdf
```

---

## Source Levels

Defined in `config/source-levels.yaml` (single source of truth).

| Level | Source Type |
|-------|-------------|
| S | Laws, statutes, regulations and official legal databases |
| A | Regulator guidance, tax authority guidance and official FAQs |
| B | Official circulars, announcements, cases and formal notices |
| C | Law firm, accounting firm, bank or professional institution briefings |
| D | Public account posts, media articles and individual commentary |

C and D sources are leads only. They must not be treated as final legal authority.

---

## Output Shape (5 required items)

Defined in `config/output-contract.yaml` (single source of truth).

```text
【问题分类】
【结论或考量维度】
【类案与公开答案】
【涉及现行法规】          ← priority
【法规修订关系】
【风险提示】
【结论可靠性】
【报告文件】
```

---

## Layout

```text
.claude/
  CLAUDE.md                     Project rules and lead-agent constraints
  principles.md                 7 operating principles
  contracts.md                  Task package format and output contract
  agents/                       Project subagents (organized by concern)
    retrieval/rag-retriever.md
    validation/regulatory-validity-verifier.md
    validation/citation-verifier.md
    analysis/funds-compliance-analyst.md
    analysis/tax-policy-analyst.md
    analysis/commercial-law-analyst.md
    parsing/document-parser.md
  skills/                       Reusable skill procedures (organized by concern)
    retrieval/rag-retrieval.md
    retrieval/source-ingestion.md
    validation/regulatory-validity-verification.md
    validation/citation-verification.md
    analysis/policy-research.md
    parsing/document-parse.md

.agents/
  skills/
    liteparse/                  Built-in third-party document parsing skill

config/                         Strategy data — single source of truth
  routing.yaml                  Classifications, keywords, sub-domains, agent mappings
  source-levels.yaml            S/A/B/C/D reliability scale
  jurisdictions.yaml            Jurisdiction settings, case-law databases, registry paths
  output-contract.yaml          Required and supporting report sections

docs/
  rag-mcp-design.md             RAG / MCP tool design draft

sources/
  README.md                     Source registry schema, reliability notes and sub-domain taxonomy
  cn.yaml                       Mainland China official source index (includes wenshu case database)
  us.yaml                       United States official source index (includes CourtListener case database)
  hk.yaml                       Hong Kong official source index (includes HKLII case database)
  sg.yaml                       Singapore official source index (includes Singapore Courts case database)

templates/
  report.md                     Archived report template
  retrieval-task.md             rag-retriever task package template

tools/
  render_report.py              Thin CLI orchestration for report generation
  build_markdown.py             Markdown generation utilities
  convert_pdf.py                PDF conversion (pandoc / weasyprint / reportlab)
  validate_config.py            Config YAML schema and consistency validation
  validate_registry.py          Source registry validation

tests/
  test_config.py                Config YAML tests
  test_registry.py              Source registry tests
  test_render.py                Markdown generation and PDF fallback tests

reports/
  .gitkeep                      Report directory placeholder
  YYYYMMDD-topic/
    report.md                   Generated Markdown report
    report.pdf                  Generated PDF report

CHANGELOG.md
README.md
README.zh-CN.md
pyproject.toml
uv.lock
skills-lock.json
```

---

## Local Setup

Install the minimal local tool environment:

```bash
uv venv
source .venv/bin/activate
uv sync --extra dev
```

`liteparse` is already included in the repository. Run this only when refreshing or reinstalling the skill:

```bash
npx skills add run-llama/llamaparse-agent-skills --skill liteparse
```

Check config files:

```bash
uv run ruff check .
```

Generate a local report from the template:

```bash
uv run python tools/render_report.py --title "Sample Policy Report" --topic sample --overwrite
```

---

## Discussion

The current version focuses on validating the agent-native workflow. Heavier engineering layers should be added only when the need is proven: persistent RAG indexes, shared source databases, Web UI, file management, audit logs, MCP tools or backend services.

Until then, 3wagent keeps the project code small and uses Claude Code / Codex as the execution layer.
