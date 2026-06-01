<h1 align="center">3wagent</h1>

<p align="center">
  <strong>Personal Cross-Border Policy Research Agent Workspace</strong><br>
  Claude Code subagents for issue routing, policy retrieval, citation checks and report archiving
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
| Issue routing | Identify jurisdictions, transaction type, payment character and primary domain |
| Document parsing | Use the built-in `liteparse` skill for PDF / Word / scanned materials |
| Subagent analysis | Split funds compliance, tax and commercial law into specialist agents |
| Policy retrieval | Start from `sources/`, then filter by US / HK / SG and funds / tax / commercial domains |
| Citation verification | Check whether conclusions match the cited jurisdiction and source |
| Report archive | Generate both `report.md` and `report.pdf` under `reports/` |

---

## What Claude Code Does

For a direct policy question:

```text
1. The Lead Policy Agent identifies jurisdiction, parties, transaction and payment character
2. It decides the primary domain: funds / tax / commercial
3. It delegates source retrieval to rag-retriever, starting from `sources/`
4. It calls the relevant specialist subagents
5. It runs citation-verifier
6. It writes the final answer
7. It saves reports/YYYYMMDD-topic/report.md
8. It converts the Markdown report to PDF
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

4. Specialist subagents analyze the issue
5. citation-verifier checks evidence
6. The final answer and report files are generated
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

| Level | Source Type |
|-------|-------------|
| S | Laws, statutes, regulations and official legal databases |
| A | Regulator guidance, tax authority guidance and official FAQs |
| B | Official circulars, announcements, cases and formal notices |
| C | Law firm, accounting firm, bank or professional institution briefings |
| D | Public account posts, media articles and individual commentary |

C and D sources are leads only. They must not be treated as final legal authority.

---

## Output Shape

```text
【问题识别】
【简要结论】
【资金流动 / 银行合规 / AML / 制裁分析】
【税务分析】
【民商法规分析】
【法规与政策索引】
【实务文件清单】
【风险提示】
【结论可靠性】
【报告文件】
```

---

## Layout

```text
.claude/
  CLAUDE.md                     Project rules and lead-agent constraints
  agents/                       Project subagents
  skills/                       Research, retrieval, citation and ingestion rules

.agents/
  skills/
    liteparse/                  Built-in third-party document parsing skill

docs/
  rag-mcp-design.md             RAG / MCP tool design draft

sources/
  README.md                     Source registry schema and reliability notes
  us.yaml                       United States official source index
  hk.yaml                       Hong Kong official source index
  sg.yaml                       Singapore official source index

templates/
  report.md                     Archived report template
  retrieval-task.md             rag-retriever task package template

tools/
  render_report.py              Generate report.md and try to convert report.pdf

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
