# 3wagent

Language: English | [简体中文](README.zh-CN.md)

3wagent is a private cross-border policy research agent. It accepts a question or PDF/Word document, routes the issue across funds compliance, tax and corporate/commercial law, retrieves supporting policy sources, and returns a plain-text analysis with citations and reliability notes.

Initial jurisdictions:

- United States
- Hong Kong
- Singapore

The system prioritizes official laws, regulations and regulator guidance. Professional articles and public account posts are secondary leads only.

## Core Architecture

The project should stay small at the beginning and expand along stable boundaries:

```text
Streamlit UI
  -> FastAPI API
  -> Document Intake
  -> Issue Router
  -> Retrieval Interface
  -> LangChain Specialist Chains
       - Funds / AML / Sanctions
       - Tax
       - Corporate & Commercial Law
  -> Evidence Verifier
  -> Plain-text Report Writer
```

Key design choices:

- LangChain is the core LLM, prompt and chain layer.
- Python workflow coordinates the MVP business flow.
- Retrieval starts as a replaceable interface and later becomes RAG.
- LangGraph is introduced later only when workflow branching and state become complex.
- Streamlit is the MVP frontend; Next.js can replace it later without changing the backend analysis contract.

## Current Layout

```text
app/
  main.py                       FastAPI entrypoint

  core/
    config.py                   Runtime configuration
    schemas.py                  Shared Pydantic models

  intake/
    document_intake.py          Upload text extraction
    pdf_parser.py               PDF parsing
    word_parser.py              Word parsing

  router/
    rules.py                    Routing keywords and rules
    issue_router.py             Issue classification

  retrieval/
    retriever.py                Mock retrieval now, RAG later

  llm/
    client.py                   LangChain model provider factory
    chains.py                   LangChain chain helpers

  tools/
    skills/
      registry.py               Runtime prompt registry
      loader.py                 Prompt template loader
      templates/                LangChain system prompts
    mcp/                        Optional future MCP client adapters

  agents/
    funds_agent.py
    tax_agent.py
    commercial_agent.py
    evidence_verifier.py
    answer_writer.py
    source_context.py

  graph/
    policy_graph.py             MVP Python workflow; future LangGraph home

scripts/
  ingest_documents.py
  crawl_sources.py

tests/
```

## Evolution Path

The architecture should grow in phases without being rewritten.

```text
Phase 1: MVP
FastAPI + LangChain + Python workflow + mock retriever + Streamlit

Phase 2: Usable RAG
PostgreSQL + pgvector + full-text search + source metadata + hybrid retrieval

Phase 3: Stable workflow
LangGraph nodes for intake, routing, retrieval, specialist analysis, verification and writing

Phase 4: Product UI
Next.js / React frontend, streaming chat, file management and source dashboard
```

RAG is required for the mature product, but it should enter through `retrieval/` rather than forcing an early rewrite. The future RAG layer should support:

- Jurisdiction filters: US / HK / SG
- Domain filters: funds / tax / commercial
- Source reliability: S / A / B / C / D
- Vector search with pgvector
- Keyword search with PostgreSQL full-text search
- Citation metadata and retrieved dates
- Evidence verification before final output

## Routing Rules

Funds / AML / sanctions is preferred when the question involves cross-border payments, remittance, bank KYC, AML/CFT, source-of-funds checks, OFAC, sanctions, accounts, investment funds or dividend remittance.

Tax is preferred when the question involves withholding tax, profits tax, corporate income tax, GST/VAT, dividends, interest, royalties, service fees, capital gains, tax residency, permanent establishment or tax treaties.

Corporate and commercial law is preferred when the question involves company formation, directors, shareholders, share transfers, contracts, commercial registration, licenses or investment access.

When tax and funds issues both appear, tax can be primary if the payment characterization is the main question, with funds compliance as a secondary track.

## Source Reliability

```text
S: Laws, statutes, regulations and official legal databases
A: Regulator guidance, tax authority guidance and official FAQs
B: Official circulars, announcements, cases and formal notices
C: Law firm, accounting firm, bank or professional institution briefings
D: Public account posts, media articles and individual commentary
```

Final answers should distinguish:

- Supported by official authority
- Likely but requiring manual review
- Secondary-source lead only
- No reliable source found

## Tech Stack

MVP:

```text
Python 3.11+
uv + pyproject.toml + uv.lock
FastAPI + Uvicorn
Pydantic v2
LangChain + configurable LLM provider
PyMuPDF + python-docx
Streamlit
pytest + ruff
Docker + Docker Compose
```

Later:

```text
PostgreSQL + pgvector
PostgreSQL full-text search
Alembic
Scrapy / Playwright
BeautifulSoup / trafilatura
Tesseract / PaddleOCR
LangGraph
Celery + Redis
Next.js / React + Tailwind CSS + shadcn/ui
```

MCP is not part of the core MVP. If a real external tool boundary appears later, app-side adapters can live under `app/tools/mcp/`.

## Local Development

Install dependencies:

```bash
uv venv
source .venv/bin/activate
uv sync --extra dev
```

Create local environment variables:

```bash
cp .env.example .env
```

Set `LLM_API_KEY` when you want LangChain to call a remote model. Without a configured provider, the MVP uses deterministic fallback analysis so routing and API smoke tests still run locally.

Default provider:

```text
LLM_PROVIDER=openai
LLM_MODEL=gpt5.5
LLM_API_KEY=...
```

OpenAI-compatible APIs can use the same LangChain OpenAI adapter with a custom base URL:

```text
LLM_PROVIDER=openai_compatible
LLM_MODEL=your-model
LLM_API_KEY=...
LLM_BASE_URL=https://your-provider.example.com/v1
```

Other providers can be added in `app/llm/client.py` through the same provider factory pattern.

Run the API:

```bash
uv run uvicorn app.main:app --reload
```

Local endpoints:

```text
GET  http://127.0.0.1:8000/health
POST http://127.0.0.1:8000/analyze
GET  http://127.0.0.1:8000/docs
```

Example:

```bash
curl -X POST http://127.0.0.1:8000/analyze \
  -F "question=香港公司向新加坡公司支付服务费，需要关注哪些税务和银行合规问题？"
```

Run tests:

```bash
uv run pytest
```

## Streamlit Demo

Planned MVP flow:

```text
Terminal 1:
  uv run uvicorn app.main:app --reload
  -> FastAPI backend at http://127.0.0.1:8000

Terminal 2:
  uv run streamlit run frontend/streamlit_app.py
  -> Streamlit UI at http://127.0.0.1:8501
```

User flow:

```text
1. Enter a policy question
2. Upload PDF or Word when needed
3. Optionally select US / Hong Kong / Singapore
4. Click Analyze
5. Streamlit calls POST /analyze
6. The backend returns a plain-text policy report
```

`frontend/streamlit_app.py` is planned but not implemented yet.

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
```
