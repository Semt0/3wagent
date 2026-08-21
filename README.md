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

The project therefore does not maintain its own FastAPI / LangChain / LangGraph analysis runtime for the MVP. Instead, it keeps the reusable domain logic in Claude Code rules, skills and project subagents. A thin optional FastAPI dashboard only reads local run logs and report artifacts.

---

## Experimental qwen-agent Runtime (`src/`)

An experimental refactored runtime lives under `src/`, based on [qwen-agent](https://github.com/QwenLM/qwen-agent) instead of LangChain. It is an early scaffold that runs alongside the Claude Code architecture described above:

- `MainAgent(FnCallAgent)` with qwen-agent's built-in Gradio WebUI
- OpenAI-compatible local model endpoint (llama-server via SSH tunnel, model selectable with `-m`)
- Native `@register_tool` function calling (currently markdown / YAML file readers)
- The domain rules from `.claude/CLAUDE.md` and `config/*.yaml` are reused as-is

The planned multi-agent pipeline (parsing → routing → RAG → validity → analysis → citation verification → report writing) is not implemented yet. See [src/README.md](src/README.md) for details and run instructions.

---

## Features

| Feature | Description |
|---------|-------------|
| Issue routing & classification | Identify jurisdictions, transaction type, payment character and primary domain; classify as pure funds-forex / pure funds-banking / pure tax / cross-domain |
| Document parsing | Use the built-in `liteparse` skill for PDF / Word / scanned materials |
| Subagent analysis | Split funds compliance (forex vs banking/AML), tax and commercial law into specialist agents |
| Policy retrieval | Start from `sources/`, then filter by CN / US / HK / SG and funds / tax / commercial domains |
| Local RAG index | Optional SQLite FTS index at `sources/index.sqlite` for repeatable source snapshot search with jurisdiction, domain and reliability metadata |
| Case-law retrieval | Search official case databases (wenshu, HKLII, Singapore Courts, CourtListener) for analogous judgments |
| Regulatory validity | Check whether laws, notices, guidance and official cases are current, replaced, repealed or time-limited; trace single-tier amendment lineage |
| Citation verification | Check whether conclusions match the cited jurisdiction and source; verify case citations and amendment lineage |
| Report archive | Generate both `report.md` and `report.pdf` under `reports/` |
| Local dashboard | Optional static viewer plus thin FastAPI bridge for run progress, subagent status and final report preview |

---

## What Claude Code Does

For a direct policy question:

```text
1. The Lead Policy Agent identifies jurisdiction, parties, transaction and payment character
2. It classifies the issue: pure funds-forex / pure funds-banking / pure tax / cross-domain
3. It delegates source retrieval to rag-retriever, starting from `sources/` and the optional local RAG index
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

3. rag-retriever checks the `sources/` registry and optional local RAG index, then gathers source packs
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
rag-retriever checks `sources/` and the optional local RAG index, then gathers official and secondary sources
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
    parsing/liteparse.md        Built-in third-party document parsing skill

config/                         Strategy data — single source of truth
  routing.yaml                  Classifications, keywords, sub-domains, agent mappings
  source-levels.yaml            S/A/B/C/D reliability scale
  jurisdictions.yaml            Jurisdiction settings, case-law databases, registry paths
  output-contract.yaml          Required and supporting report sections

docs/
  architecture.md               Design rationale and human / agent division of labor
  rag-mcp-design.md             RAG / MCP tool design draft
  course-report/                Course write-up (LaTeX source + compiled PDF)

src/                            Experimental qwen-agent runtime (see src/README.md)
  main.py                       CLI entry: model selection, DEBUG logging, WebUI launch
  agent/main_agent.py           MainAgent(FnCallAgent) and run_3wagent()
  config/                       LLM endpoint, WebUI chatbot and logger settings
  prompts/prompts.py            Main system prompt (ported from .claude/CLAUDE.md)
  tools/                        qwen-agent @register_tool file readers

mcp_server/
  server.py                     MCP bridge for reports, registries, routing and local RAG search
  rag_index.py                  SQLite FTS source snapshot index

server/
  app.py                        Thin FastAPI dashboard backend and report API

sources/
  README.md                     Source registry schema, reliability notes and sub-domain taxonomy
  cn.yaml                       Mainland China official source index (includes wenshu case database)
  us.yaml                       United States official source index (includes CourtListener case database)
  hk.yaml                       Hong Kong official source index (includes HKLII case database)
  sg.yaml                       Singapore official source index (includes Singapore Courts case database)
  snapshots/                    Optional saved source snapshots for local indexing
  index.sqlite                  Optional generated local RAG index

templates/
  report.md                     Archived report template
  retrieval-task.md             rag-retriever task package template

tools/
  open_dashboard.py             Start the local dashboard backend and open a browser
  progress.py                   Write run status and progress events under runs/
  ingest_sources.py             Build/update the local SQLite RAG index
  render_report.py              Thin CLI orchestration for report generation
  build_markdown.py             Markdown generation utilities
  convert_pdf.py                PDF conversion (pandoc / weasyprint / reportlab)
  validate_config.py            Config YAML schema and consistency validation
  validate_registry.py          Source registry validation

tests/
  test_config.py                Config YAML tests
  test_mcp_server.py            MCP tool tests
  test_open_dashboard.py        Dashboard launcher tests
  test_progress.py              Run progress log tests
  test_rag_index.py             Local RAG index tests
  test_registry.py              Source registry tests
  test_render.py                Markdown generation and PDF fallback tests
  test_server.py                Dashboard API tests

reports/
  .gitkeep                      Report directory placeholder
  YYYYMMDD-topic/
    report.md                   Generated Markdown report
    report.pdf                  Generated PDF report

runs/
  .gitkeep                      Run progress directory placeholder
  YYYYMMDD-topic/
    status.json                 Current run status for the dashboard
    progress.jsonl              Step-by-step run event log

viewer/
  index.html                    Static dashboard shell
  app.js                        Dashboard polling and rendering logic
  style.css                     Dashboard styles

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

Install MCP support when using the local MCP bridge:

```bash
uv sync --extra dev --extra mcp
```

Install dashboard support when using the local viewer:

```bash
uv sync --extra dev --extra server
```

`liteparse` is included as a built-in skill at `.claude/skills/parsing/liteparse.md`. The skill still requires the LiteParse CLI (Node 18+) to be installed globally:

```bash
npm i -g @llamaindex/liteparse
```

Check config files:

```bash
uv run ruff check .
```

Generate a local report from the template:

```bash
uv run python tools/render_report.py --title "Sample Policy Report" --topic sample --overwrite
```

Build the optional local RAG index from saved source snapshots:

```bash
uv run python tools/ingest_sources.py --all-snapshots
```

Bootstrap one registry source into the index using metadata only:

```bash
uv run python tools/ingest_sources.py --source-id cn-safe-policy-regulations --metadata-only
```

Start the local dashboard:

```bash
uv run python tools/open_dashboard.py
```

The dashboard reads `runs/*/status.json`, `runs/*/progress.jsonl` and archived reports. It exposes:

```text
GET /api/runs
GET /api/runs/{run_id}/progress
GET /api/reports
GET /api/reports/{report_id}
GET /api/reports/{report_id}/markdown
DELETE /api/reports/{report_id}
```

The MCP bridge exposes:

```text
source_registry_search
source_document_search
source_document_read
routing_classify
report_artifact_list
report_artifact_read
```

---

## Discussion

The current version includes a lightweight optional RAG layer: curated registries plus a local SQLite FTS index for saved source snapshots. Heavier engineering layers should still be added only when the need is proven: vector databases, shared source services, Web UI, file management, audit logs or a separate backend runtime.

Until then, 3wagent keeps the project code small and uses Claude Code / Codex as the execution layer.
