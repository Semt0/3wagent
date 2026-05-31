# 3wagent

语言：[English](README.md) | 简体中文

3wagent 是一个个人使用的跨境政策研究 Agent。它接收用户问题或 PDF/Word 文档，自动判断资金合规、税务、公司与民商法等分析主线，检索政策依据，并输出带引用和可靠性说明的纯文本报告。

第一阶段覆盖：

- 美国
- 香港
- 新加坡

系统优先使用官方法律、法规和监管机构指引。专业文章和公众号内容只作为辅助线索。

## 核心架构

项目前期要保持轻，后期沿稳定边界自然扩展：

```text
Streamlit UI
  -> FastAPI API
  -> 文档解析
  -> 问题路由
  -> 检索接口
  -> LangChain 专家 Chains
       - 资金 / AML / 制裁
       - 税务
       - 公司与民商法
  -> 证据校验
  -> 纯文本报告生成
```

核心取舍：

- LangChain 是 LLM、prompt 和 chain 的核心层。
- Python workflow 负责 MVP 阶段的业务编排。
- 检索先做成可替换接口，后期自然升级为 RAG。
- LangGraph 等流程分支和状态管理复杂后再引入。
- 前端 MVP 先用 Streamlit，后期可以切 Next.js，不影响后端分析接口。

## 当前目录

```text
app/
  main.py                       FastAPI 入口

  core/
    config.py                   运行配置
    schemas.py                  共享 Pydantic 模型

  intake/
    document_intake.py          上传文档文本抽取
    pdf_parser.py               PDF 解析
    word_parser.py              Word 解析

  router/
    rules.py                    路由关键词和规则
    issue_router.py             问题分类

  retrieval/
    retriever.py                当前 mock，后期升级 RAG

  llm/
    client.py                   LangChain 模型 provider 工厂
    chains.py                   LangChain chain 辅助

  tools/
    skills/
      registry.py               运行时 prompt 注册表
      loader.py                 prompt 模板加载器
      templates/                LangChain system prompts
    mcp/                        后续可选 MCP 客户端适配层

  agents/
    funds_agent.py
    tax_agent.py
    commercial_agent.py
    evidence_verifier.py
    answer_writer.py
    source_context.py

  graph/
    policy_graph.py             MVP Python workflow；后期 LangGraph 入口

scripts/
  ingest_documents.py
  crawl_sources.py

tests/
```

## 演进路线

架构按阶段扩展，不推翻重来：

```text
Phase 1: MVP
FastAPI + LangChain + Python workflow + mock retriever + Streamlit

Phase 2: 可用 RAG
PostgreSQL + pgvector + 全文检索 + source metadata + hybrid retrieval

Phase 3: 稳定工作流
用 LangGraph 拆 intake、router、retrieval、专家分析、证据校验、报告生成节点

Phase 4: 产品化 UI
Next.js / React 前端、流式对话、文件管理、政策来源看板
```

成熟版本一定需要 RAG，但应通过 `retrieval/` 自然接入，而不是一开始重写主流程。后期 RAG 需要支持：

- 法域过滤：US / HK / SG
- 领域过滤：funds / tax / commercial
- 来源等级：S / A / B / C / D
- pgvector 向量检索
- PostgreSQL 全文检索
- 引用 metadata 和检索日期
- 最终输出前的证据校验

## 路由规则

涉及跨境付款、汇款、银行 KYC、AML/CFT、资金来源、OFAC、制裁、账户、投资款或分红汇出时，优先走资金 / AML / 制裁分析。

涉及预提税、利得税、企业所得税、GST/VAT、股息、利息、特许权使用费、服务费、资本利得、税收居民、常设机构或税收协定时，优先走税务分析。

涉及公司设立、董事、股东、股权转让、合同、商业登记、牌照或投资准入时，优先走公司与民商法分析。

如果税务和资金问题同时出现，且核心是付款性质判断，则税务可以作为主分析，资金合规作为辅助分析。

## 来源可靠性

```text
S：法律原文、法规、条例和官方法律数据库
A：监管机构指引、税局指引和官方 FAQ
B：官方通函、公告、判例和正式通知
C：律所、会计师事务所、银行或专业机构简报
D：公众号、媒体文章和个人评论
```

最终结论应区分：

- 已由官方来源支持
- 高度可能，但需要人工复核
- 仅为二级资料线索
- 未找到可靠依据

## 技术栈

MVP：

```text
Python 3.11+
uv + pyproject.toml + uv.lock
FastAPI + Uvicorn
Pydantic v2
LangChain + 可配置 LLM provider
PyMuPDF + python-docx
Streamlit
pytest + ruff
Docker + Docker Compose
```

后续：

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

MCP 不作为 MVP 核心能力。后续如果确实出现外部工具边界，再通过 `app/tools/mcp/` 接入。

## 本地开发

安装依赖：

```bash
uv venv
source .venv/bin/activate
uv sync --extra dev
```

创建本地环境变量：

```bash
cp .env.example .env
```

需要调用远程模型时设置 `LLM_API_KEY`。如果没有配置模型 provider，MVP 会使用确定性的 fallback 分析，方便本地先跑通路由和 API smoke test。

默认 provider：

```text
LLM_PROVIDER=openai
LLM_MODEL=gpt5.5
LLM_API_KEY=...
```

OpenAI-compatible API 可以继续使用 LangChain 的 OpenAI adapter，并配置自定义 base URL：

```text
LLM_PROVIDER=openai_compatible
LLM_MODEL=your-model
LLM_API_KEY=...
LLM_BASE_URL=https://your-provider.example.com/v1
```

其他 provider 可以在 `app/llm/client.py` 里按同样的 provider factory 模式继续扩展。

运行 API：

```bash
uv run uvicorn app.main:app --reload
```

本地接口：

```text
GET  http://127.0.0.1:8000/health
POST http://127.0.0.1:8000/analyze
GET  http://127.0.0.1:8000/docs
```

示例：

```bash
curl -X POST http://127.0.0.1:8000/analyze \
  -F "question=香港公司向新加坡公司支付服务费，需要关注哪些税务和银行合规问题？"
```

运行测试：

```bash
uv run pytest
```

## Streamlit Demo

计划中的 MVP 流程：

```text
终端 1：
  uv run uvicorn app.main:app --reload
  -> FastAPI 后端运行在 http://127.0.0.1:8000

终端 2：
  uv run streamlit run frontend/streamlit_app.py
  -> Streamlit 页面运行在 http://127.0.0.1:8501
```

用户流程：

```text
1. 输入政策问题
2. 按需上传 PDF 或 Word
3. 可选选择 US / 香港 / 新加坡
4. 点击 Analyze
5. Streamlit 调用 POST /analyze
6. 后端返回纯文本政策报告
```

`frontend/streamlit_app.py` 还未实现。

## 输出结构

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
