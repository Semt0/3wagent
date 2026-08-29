# SQLite FTS RAG 实施计划

## 1. 文档目的

本文档定义 3wagent 本地法规知识库与 SQLite FTS 检索层的实施方案，作为后续开发、测试和验收的统一依据。

本方案的目标是实现一套：

- 本地运行、依赖较轻的法规 RAG 检索层；
- 支持 CN、US、HK、SG 四法域；
- 支持资金合规、税务和民商法规三个领域；
- 支持中文、英文、法规名称、文号和条款检索；
- 支持法规快照、历史版本、有效期和更新审计；
- 能够向 Validate、领域分析和 Citation Verifier 提供可定位的证据；
- 后续可以平滑增加 Elasticsearch、Chroma 或其他 Dense Retriever，而无需改造上层 pipeline。

本文档只规划 SQLite FTS 方案，不包含具体业务法规的采集清单，也不在第一阶段引入向量数据库。

## 2. 背景与现状

当前专业问题处理流程已经包含：

1. Attachment Parsing
2. Routing
3. RAG
4. Validate
5. Domain Analysis
6. Citation Verification
7. Report Writing

RAG 已位于 Routing 与 Validate 之间，但目前主要依靠：

- `sources/*.yaml` 来源注册表；
- `WebSearchTool` 搜索候选页面；
- `WebFetchTool` 抓取网页正文；
- RAG 子代理用自然语言组织 source pack。

当前缺少：

- 可重复查询的本地法规正文索引；
- 不可变法规快照和历史版本；
- chunk 级稳定引用标识；
- 结构化 RetrievalRequest 和 EvidencePack；
- 定时增量更新、失败回退和更新审计；
- 可量化的检索评测集。

仓库旧提交 `43e608d` 曾实现过一版 SQLite FTS5 索引、ingestion CLI 和测试。新方案可以复用其基本思路，但不直接原样迁移，主要需要改进：

1. 中文默认 tokenizer 的召回问题；
2. 普通表和 FTS 表手工同步的一致性风险；
3. 缺少 `source -> snapshot -> chunk` 法规版本模型；
4. 缺少结构化证据契约和端到端评测。

## 3. 核心决策

### 3.1 第一阶段使用 Lexical RAG

第一阶段检索方式为：

```text
Metadata Filter + SQLite FTS5/BM25 + Registry + Web Fallback
```

不把向量数据库作为 MVP 的必要依赖。原因包括：

- 当前来源数量和快照规模有限；
- 法规检索高度依赖名称、文号、机关、术语和条款；
- 法域、领域、来源等级和有效期需要硬过滤；
- 本地单机部署优先考虑简单性和可审计性；
- 应先建立 BM25 基线，再通过评测决定是否增加 Dense Retrieval。

### 3.2 SQLite 不是唯一事实源

三类数据职责如下：

```text
sources/*.yaml
  └─ 人工维护的来源身份、权威性和更新配置

sources/snapshots/
  └─ 官方网页、PDF和标准化正文的不可变历史快照

sources/index.sqlite
  └─ 可从 YAML 和 snapshots 重建的运行时元数据库与检索索引
```

SQLite 数据库损坏或删除后，必须能够从 registry 和 snapshot manifest 重建。

### 3.3 RAG 只负责检索证据

RAG 不负责：

- 判断法规是否当前有效；
- 生成最终法律、税务或合规结论；
- 把网页变化自动认定为法规修订；
- 把 C/D 级来源提升为正式依据。

职责边界：

```text
RAG        找到候选证据和版本线索
Validate   判断时效、版本和修订关系
Analyst    基于已验证证据分析
Citation   核对结论与具体 chunk 的支撑关系
```

## 4. 目标架构

```text
Routing
  │
  │ RetrievalRequest
  ▼
RAG Retriever
  ├─ Registry metadata search
  ├─ SQLite CJK FTS search
  ├─ SQLite word FTS search
  ├─ RRF fusion and deduplication
  ├─ Coverage evaluation
  └─ Official web fallback for uncovered claims
  │
  │ EvidencePack
  ▼
Validate
  │ ValidatedEvidencePack
  ▼
Domain Analysts
  │ Claim and citation mapping
  ▼
Citation Verifier
  │ Verification findings
  ▼
Report Writer
```

## 5. 建议目录结构

```text
src/
├── rag/
│   ├── __init__.py
│   ├── models.py
│   ├── database.py
│   ├── schema.sql
│   ├── registry.py
│   ├── snapshots.py
│   ├── parsers.py
│   ├── chunking.py
│   ├── indexing.py
│   ├── query.py
│   ├── ranking.py
│   ├── ingestion.py
│   ├── updater.py
│   └── cli.py
├── tools/
│   ├── source_registry_search.py
│   ├── local_rag_search.py
│   └── local_source_read.py
├── config/
│   └── rag.yaml
├── evals/
│   └── rag/
│       ├── golden_queries.jsonl
│       └── README.md
└── sources/
    ├── snapshots/
    ├── index.sqlite
    └── *.yaml
```

运行时生成的 `index.sqlite` 和 staging 文件不提交 Git。snapshot 是否提交应根据体积、版权和交付方式单独决定；无论是否提交，都必须保留 manifest 和 content hash。

## 6. 数据契约

### 6.1 RetrievalRequest

Routing 阶段除了 Markdown 调试产物，还应输出结构化请求：

```json
{
  "question": "境内企业向香港支付技术服务费需要关注什么？",
  "as_of_date": "2026-08-29",
  "jurisdictions": ["CN", "HK"],
  "domains": ["funds", "tax"],
  "subdomains": ["forex-administration"],
  "transaction_type": "cross_border_service_fee",
  "parties": [
    {"role": "payer", "jurisdiction": "CN"},
    {"role": "payee", "jurisdiction": "HK"}
  ],
  "required_claims": [
    {
      "claim_id": "C1",
      "question": "服务贸易付汇需要哪些材料或审核？",
      "query_variants": [
        "服务贸易 外汇支付 银行审核",
        "技术服务费 经常项目 付汇"
      ]
    },
    {
      "claim_id": "C2",
      "question": "该付款是否涉及预提税？",
      "query_variants": [
        "技术服务费 预提税",
        "technical service fee withholding tax"
      ]
    }
  ]
}
```

Routing 的结构化结果是下游过滤条件的唯一来源。RAG 不应重新从完整对话猜测法域和领域。

### 6.2 EvidencePack

RAG 输出：

```text
workspace/<run_id>/rag/evidence_pack.json
workspace/<run_id>/rag/evidence_pack.md
```

JSON 是机器接口，Markdown 只用于人工调试。

每条证据至少包含：

```json
{
  "claim_id": "C1",
  "chunk_uid": "cn-safe-xxx@b93c812f#article-12",
  "source_id": "cn-safe-xxx",
  "snapshot_id": "b93c812f...",
  "title": "国家外汇管理局关于……",
  "document_number": "汇发〔2024〕XX号",
  "authority": "国家外汇管理局",
  "url": "https://www.safe.gov.cn/...",
  "jurisdiction": "CN",
  "domains": ["funds"],
  "subdomains": ["forex-administration"],
  "reliability": "A",
  "regulatory_status": "current",
  "publication_date": "2024-01-10",
  "effective_date": "2024-03-01",
  "retrieved_at": "2026-08-29T02:00:00Z",
  "locator": "article:12",
  "excerpt": "银行办理服务贸易外汇收支业务时……",
  "retrieval": {
    "query": "服务贸易 外汇支付 银行审核",
    "retriever": "fts_cjk",
    "rank": 2,
    "rrf_score": 0.0317
  }
}
```

EvidencePack 还应包含 coverage 和 gaps：

```json
{
  "coverage": {
    "C1:CN:funds": "covered",
    "C2:HK:tax": "insufficient"
  },
  "gaps": [
    {
      "claim_id": "C2",
      "jurisdiction": "HK",
      "domain": "tax",
      "reason": "本地库未命中具体官方指引",
      "web_search_required": true
    }
  ]
}
```

## 7. SQLite 数据模型

### 7.1 sources

保存稳定来源身份和更新配置：

```sql
CREATE TABLE sources (
    source_id              TEXT PRIMARY KEY,
    title                  TEXT NOT NULL,
    authority              TEXT NOT NULL,
    canonical_url          TEXT NOT NULL,
    jurisdiction           TEXT NOT NULL,
    reliability            TEXT NOT NULL,
    source_type            TEXT NOT NULL,
    enabled                INTEGER NOT NULL DEFAULT 1,
    update_interval        TEXT,
    require_manual_review  INTEGER NOT NULL DEFAULT 0,
    active_snapshot_id     TEXT,
    created_at             TEXT NOT NULL,
    updated_at             TEXT NOT NULL
);
```

`source_id` 永远稳定。URL、标题或机关名称发生调整时，不应创建新的 source identity。

多值领域使用关系表：

```sql
CREATE TABLE source_domains (
    source_id TEXT NOT NULL,
    domain    TEXT NOT NULL,
    PRIMARY KEY (source_id, domain),
    FOREIGN KEY (source_id) REFERENCES sources(source_id)
);

CREATE TABLE source_subdomains (
    source_id TEXT NOT NULL,
    subdomain TEXT NOT NULL,
    PRIMARY KEY (source_id, subdomain),
    FOREIGN KEY (source_id) REFERENCES sources(source_id)
);
```

### 7.2 snapshots

每次实质内容变化产生不可变 snapshot：

```sql
CREATE TABLE snapshots (
    snapshot_id            TEXT PRIMARY KEY,
    source_id              TEXT NOT NULL,
    content_sha256         TEXT NOT NULL,
    raw_path               TEXT NOT NULL,
    normalized_path        TEXT NOT NULL,
    fetched_url            TEXT,
    final_url              TEXT,
    content_type           TEXT,
    etag                   TEXT,
    last_modified          TEXT,
    fetched_at             TEXT NOT NULL,
    parser_name            TEXT NOT NULL,
    parser_version         TEXT NOT NULL,
    publication_date       TEXT,
    effective_date         TEXT,
    amendment_date         TEXT,
    repeal_or_expiry_date  TEXT,
    approval_status        TEXT NOT NULL,
    regulatory_status      TEXT NOT NULL,
    supersedes_snapshot_id TEXT,
    quality_score          REAL,
    review_notes           TEXT,
    FOREIGN KEY (source_id) REFERENCES sources(source_id),
    UNIQUE (source_id, content_sha256)
);
```

两个状态必须分开：

- `approval_status`: `pending / approved / rejected`
- `regulatory_status`: `current / historical / repealed / unknown`

抓取成功不等于法规当前有效。

### 7.3 chunks

每个 chunk 必须可独立检索、读取和引用：

```sql
CREATE TABLE chunks (
    id                 INTEGER PRIMARY KEY,
    chunk_uid          TEXT NOT NULL UNIQUE,
    snapshot_id        TEXT NOT NULL,
    source_id          TEXT NOT NULL,
    ordinal            INTEGER NOT NULL,
    locator            TEXT NOT NULL,
    page_number        INTEGER,
    title              TEXT NOT NULL,
    document_number    TEXT,
    heading            TEXT,
    heading_path       TEXT,
    body               TEXT NOT NULL,
    body_sha256        TEXT NOT NULL,
    char_count         INTEGER NOT NULL,
    token_estimate     INTEGER,
    jurisdiction       TEXT NOT NULL,
    reliability        TEXT NOT NULL,
    regulatory_status  TEXT NOT NULL,
    FOREIGN KEY (snapshot_id) REFERENCES snapshots(snapshot_id),
    FOREIGN KEY (source_id) REFERENCES sources(source_id)
);
```

`chunk_uid` 格式：

```text
<source_id>@<snapshot-hash>#<locator>
```

报告和下游 agent 应引用 `chunk_uid`，不能只引用易变化的 URL。

### 7.4 更新记录

建议增加：

```sql
CREATE TABLE update_runs (
    run_id          TEXT PRIMARY KEY,
    started_at      TEXT NOT NULL,
    finished_at     TEXT,
    trigger_type    TEXT NOT NULL,
    checked_count   INTEGER NOT NULL DEFAULT 0,
    changed_count   INTEGER NOT NULL DEFAULT 0,
    activated_count INTEGER NOT NULL DEFAULT 0,
    pending_count   INTEGER NOT NULL DEFAULT 0,
    failed_count    INTEGER NOT NULL DEFAULT 0,
    status          TEXT NOT NULL,
    summary_json    TEXT
);

CREATE TABLE update_events (
    id             INTEGER PRIMARY KEY,
    run_id         TEXT NOT NULL,
    source_id      TEXT NOT NULL,
    event_type     TEXT NOT NULL,
    status         TEXT NOT NULL,
    message        TEXT,
    details_json   TEXT,
    created_at     TEXT NOT NULL
);
```

## 8. FTS 索引设计

### 8.1 双 FTS 索引

建立两套索引：

```text
chunk_fts_cjk   中文和中英混合的 trigram 检索
chunk_fts_word  英文单词、缩写和词形检索
```

中文索引：

```sql
CREATE VIRTUAL TABLE chunk_fts_cjk USING fts5(
    title,
    document_number,
    heading,
    body,
    content='chunks',
    content_rowid='id',
    tokenize='trigram'
);
```

英文索引：

```sql
CREATE VIRTUAL TABLE chunk_fts_word USING fts5(
    title,
    document_number,
    heading,
    body,
    content='chunks',
    content_rowid='id',
    tokenize='porter unicode61 remove_diacritics 2'
);
```

本地运行环境已验证 SQLite 3.51.1、FTS5 和 trigram tokenizer 可用。

### 8.2 同步机制

必须通过触发器维护 external-content FTS，不允许业务代码分别写普通表和 FTS 表。

```sql
CREATE TRIGGER chunks_ai AFTER INSERT ON chunks BEGIN
    INSERT INTO chunk_fts_cjk(
        rowid, title, document_number, heading, body
    ) VALUES (
        new.id, new.title, new.document_number, new.heading, new.body
    );

    INSERT INTO chunk_fts_word(
        rowid, title, document_number, heading, body
    ) VALUES (
        new.id, new.title, new.document_number, new.heading, new.body
    );
END;
```

Update 和 Delete 必须建立对应触发器。每周执行 FTS integrity check，批量更新后执行 optimize。

## 9. 分块策略

法规文档按结构优先切分：

1. 章；
2. 节；
3. 条、款、项；
4. 官方网页标题层级；
5. PDF 页码和段落；
6. 字符数兜底切分。

推荐配置：

```yaml
chunking:
  preferred_chars: 1000
  max_chars: 1800
  fallback_overlap_chars: 150
  preserve_article_boundary: true
  preserve_page_locator: true
```

具体规则：

- 单条法规条文小于上限时完整保留；
- 不跨条文制造 overlap；
- 超长条文按款、项或句子切分；
- 表格独立成 chunk；
- chunk 继承完整 heading path；
- PDF 保留页码；
- 脚注保留并标记类型；
- 移除导航、版权、推荐阅读和页面噪音。

## 10. Registry 与快照摄取

### 10.1 Registry 同步规则

```text
YAML 新增来源       -> INSERT source
YAML 元数据变化     -> UPDATE source metadata
YAML 删除来源       -> enabled = 0
已有 snapshots      -> 永不级联删除
```

### 10.2 条件抓取

优先使用：

- ETag / `If-None-Match`
- Last-Modified / `If-Modified-Since`
- HTTP 304

无变化时只更新检查时间和下一次调度时间，不重复解析和写入 chunk。

### 10.3 标准化与 hash

抓取内容先进入 staging：

```text
sources/snapshots/.staging/<run_id>/
```

随后执行：

1. 保存原始 HTML/PDF；
2. 提取正文；
3. 统一字符编码、空白和换行；
4. 清除网页噪音；
5. 生成 normalized Markdown；
6. 对 normalized 内容计算 SHA-256；
7. 与该来源最新 snapshot 比较；
8. 只有实质变化才创建新 snapshot。

### 10.4 质量门禁

以下情况进入 `rejected` 或 `pending`：

- 抓到验证码、登录页或错误页；
- 标题、机关或域名不匹配；
- 正文短于最低阈值；
- 正文长度突然大幅下降；
- PDF 页数异常变化；
- 内容主要是导航链接；
- 编码错误或大量乱码；
- 出现废止、失效、替代等高风险变化；
- 新旧正文差异超过人工审核阈值。

### 10.5 原子写入

一个来源的激活过程必须位于同一事务：

```text
INSERT snapshot
INSERT chunks
FTS triggers update indexes
UPDATE sources.active_snapshot_id
COMMIT
```

任意一步失败则全部回滚，并继续使用上一版 active snapshot。

## 11. 查询方案

### 11.1 工具输入

`LocalRagSearchTool` 输入示例：

```json
{
  "query": "境内企业向香港支付技术服务费的外汇要求",
  "jurisdictions": ["CN", "HK"],
  "domains": ["funds", "tax"],
  "subdomains": ["forex-administration"],
  "reliability": ["S", "A", "B"],
  "as_of_date": "2026-08-29",
  "version_scope": "current",
  "limit": 12
}
```

版本范围：

```text
current  只检索当前 active snapshot
as_of    根据日期字段尝试选择历史适用版本
all      供 Validate 和版本调查使用
```

日期不完整时不得自行断言版本适用，应返回 `needs_validation`。

### 11.2 QueryPlan

禁止把用户原始文本直接作为任意 FTS MATCH 表达式。先生成受控 QueryPlan：

```json
{
  "exact_queries": [
    "技术服务费",
    "服务贸易外汇支付"
  ],
  "expanded_queries": [
    "服务费 经常项目 付汇",
    "银行 审核材料 服务贸易"
  ],
  "document_numbers": [],
  "english_queries": [
    "technical service fee foreign exchange payment"
  ]
}
```

查询扩展来源优先级：

1. `routing.yaml` 领域关键词；
2. 人工维护的法规同义词；
3. 文号、机关和实体名称；
4. LLM 生成的有限 query variants。

必须限制：

```yaml
query:
  max_variants: 5
  max_terms_per_query: 12
  max_query_chars: 500
```

Query builder 负责处理双引号、括号、星号、冒号和 FTS 布尔操作符。SQL 参数绑定可以防止 SQL 注入，但不能防止非法 MATCH 语法。

### 11.3 检索 SQL

示意查询：

```sql
SELECT
    c.id,
    c.chunk_uid,
    c.source_id,
    c.snapshot_id,
    c.title,
    c.document_number,
    c.heading,
    c.locator,
    c.body,
    c.jurisdiction,
    c.reliability,
    bm25(chunk_fts_cjk, 8.0, 10.0, 4.0, 1.0) AS lexical_rank
FROM chunk_fts_cjk
JOIN chunks c
  ON c.id = chunk_fts_cjk.rowid
JOIN snapshots sn
  ON sn.snapshot_id = c.snapshot_id
JOIN sources s
  ON s.source_id = c.source_id
WHERE chunk_fts_cjk MATCH :query
  AND sn.approval_status = 'approved'
  AND s.enabled = 1
  AND c.jurisdiction IN (...)
  AND c.reliability IN (...)
ORDER BY lexical_rank
LIMIT 50;
```

BM25 列权重建议：

```text
document_number > title > heading > body
```

来源等级不直接混入 BM25；它属于准入条件和并列排序因素，而不是文本相关性。

## 12. 多路召回、融合与去重

一次检索流程：

```text
For each query variant
  ├─ CJK FTS Top 30
  └─ Word FTS Top 30
          ↓
       RRF fusion
          ↓
   Metadata tie-break
          ↓
  Chunk/source deduplication
          ↓
     Coverage evaluation
```

RRF 公式：

```text
score(document) += 1 / (60 + rank)
```

排序优先级：

1. RRF 相关性；
2. 精确文号命中；
3. 标题精确命中；
4. 法域和领域匹配；
5. 当前版本优先；
6. S/A/B 作为相近相关度时的 tie-break；
7. 同一来源 chunk 数量限制。

建议参数：

```yaml
retrieval:
  lexical_candidates_per_query: 30
  fused_candidates: 50
  max_chunks_per_source: 3
  final_chunks: 12
  final_max_chars: 20000
  rrf_constant: 60
```

去重顺序：

1. `chunk_uid`；
2. `body_sha256`；
3. 同来源相邻 chunk 合并；
4. 官方发布机关优先于转载页面；
5. 历史和当前版本保留为不同结果，不静默合并。

## 13. Coverage 与 Web Fallback

每个 `claim × jurisdiction × domain` 都需要 coverage 状态：

```text
covered       已命中具体、可用的 S/A/B 证据
partial       有相关来源，但不足以支撑完整问题
insufficient  未命中具体官方证据
```

只有 `partial` 或 `insufficient` 才触发 Web Search。

Web 获取的新页面：

- 本次运行可以作为临时证据；
- 必须保存 retrieved_at、URL 和正文 hash；
- 不能自动提升为长期知识库中的 approved source；
- 经过 registry 纳入或人工审核后才能进入长期索引。

## 14. Qwen-Agent 工具接入

### 14.1 SourceRegistrySearchTool

功能：按法域、领域、等级和关键词筛选 registry 来源。

### 14.2 LocalRagSearchTool

功能：执行 metadata filter、双 FTS 召回、RRF、去重和 coverage 计算。

### 14.3 LocalSourceReadTool

功能：根据 `source_id / snapshot_id / locator / chunk_uid` 回读完整证据。

`MainAgent` 工具分配建议：

```python
retrieval_tools = subagent_tools + [
    "SourceRegistrySearchTool",
    "LocalRagSearchTool",
    "LocalSourceReadTool",
    "WebSearchTool",
    "WebFetchTool",
]

verification_tools = subagent_tools + [
    "LocalSourceReadTool",
    "WebSearchTool",
    "WebFetchTool",
]
```

领域 Analyst 不开放检索工具，只消费 Validate 之后的证据包。

RAG Prompt 固定执行顺序：

```text
Read RetrievalRequest
→ Search registry
→ Search local FTS
→ Read selected local chunks if needed
→ Evaluate coverage
→ Search/fetch web only for gaps
→ Write EvidencePack
```

## 15. 定时更新方案

Updater 独立于 Gradio 和 Agent 进程，以 CLI 形式运行：

```bash
python -m src.rag.cli update --due
python -m src.rag.cli update --source-id cn-safe-xxx
python -m src.rag.cli update --all
python -m src.rag.cli update --dry-run
```

调度方式：

- macOS 本地交付：launchd；
- Linux 单机：systemd timer；
- Docker/Kubernetes：CronJob；
- CI：scheduled workflow。

不同来源建议使用不同频率：

```text
监管公告/政策目录  每日
具体法规正文       每周
税收协定/法律库    每周或每月
临近生效/失效法规  指定日期额外检查
长期失败来源       降频并告警
```

## 16. 并发、事务和可用性

连接初始化：

```sql
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;
PRAGMA synchronous = NORMAL;
```

运行规则：

- Agent 主要执行只读查询；
- Updater 是唯一写入者；
- 使用文件锁防止并发 updater；
- 每个来源独立事务；
- 写入失败时旧 active snapshot 继续服务；
- 数据库连接不得跨线程无约束共享；
- 所有文件路径必须限制在 `sources/` 目录下。

大规模重建采用 staging database：

```text
sources/index.sqlite
sources/index.sqlite.rebuilding
```

步骤：

1. 完整构建 `.rebuilding`；
2. 执行 `PRAGMA quick_check`；
3. 执行 FTS integrity check；
4. 执行固定冒烟查询；
5. 关闭所有 staging 连接；
6. 原子替换正式数据库；
7. 保留上一版数据库用于短期回滚。

## 17. 配置文件

建议新增 `config/rag.yaml`：

```yaml
database:
  path: sources/index.sqlite
  wal: true
  busy_timeout_ms: 5000

snapshots:
  directory: sources/snapshots
  staging_directory: sources/snapshots/.staging
  keep_history: true
  hash_algorithm: sha256

chunking:
  preferred_chars: 1000
  max_chars: 1800
  fallback_overlap_chars: 150
  preserve_article_boundary: true
  preserve_page_locator: true

retrieval:
  lexical_candidates_per_query: 30
  fused_candidates: 50
  final_chunks: 12
  max_chunks_per_source: 3
  final_max_chars: 20000
  rrf_constant: 60

query:
  max_variants: 5
  max_terms_per_query: 12
  max_query_chars: 500
  enable_llm_expansion: true

updates:
  default_interval: weekly
  max_concurrency: 2
  retries: 3
  require_lock: true
```

## 18. 维护、备份和监控

周期任务：

```text
每日          update --due
每日          重试失败来源
每周          PRAGMA quick_check
每周          FTS integrity-check
批量写入后    FTS optimize
按需          VACUUM
```

备份应使用：

- Python SQLite Backup API；
- `VACUUM INTO`；
- 或在停止写入后进行一致性文件备份。

不能在 WAL 活跃写入期间只复制主 `.sqlite` 文件。

需要监控：

- 数据库和 FTS 索引大小；
- source、snapshot、chunk 数量；
- 最近成功更新时间；
- pending/rejected 数量；
- 抓取失败率；
- 没有 active snapshot 的来源；
- FTS 与 chunks 行数一致性；
- 本地命中率和 Web fallback 比例；
- 查询耗时和 EvidencePack 字符数。

## 19. 测试计划

### 19.1 单元测试

至少覆盖：

- Registry YAML 同步；
- 重复 ingestion 幂等性；
- 内容变化生成新 snapshot；
- 中文 trigram 命中；
- 英文词形和缩写检索；
- 法规文号精确命中；
- jurisdiction/domain/subdomain/reliability 过滤；
- current/as-of/all 版本过滤；
- FTS Insert/Update/Delete 触发器；
- 非法 MATCH 查询处理；
- chunk 和正文 hash 去重；
- locator 回读；
- 事务失败回滚；
- 更新锁和重试；
- FTS integrity check。

### 19.2 集成测试

构建覆盖四法域、三领域的小型测试库，验证：

```text
RetrievalRequest
→ Registry Search
→ Local FTS Search
→ EvidencePack
→ Validate
→ Citation Verifier
```

### 19.3 检索评测集

准备 50–100 条金标问题，每条标注：

- 正确 source_id；
- 正确 snapshot/version；
- 正确 locator 或条款；
- 必须召回的法规；
- 不应召回的历史或错误法域法规。

问题类型至少包括：

- 精确法规名称；
- 文号；
- 条款原文；
- 自然语言改写；
- 中英文混合；
- 跨法域问题；
- 历史时点问题；
- 无答案和 coverage gap。

## 20. 验收标准

第一阶段建议门槛：

| 指标 | 目标 |
|---|---:|
| Source Recall@10 | ≥ 85% |
| Chunk Recall@10 | ≥ 80% |
| 错误法域率 | < 2% |
| 历史版本误用率 | 0 |
| C/D 单独进入正式证据 | 0 |
| 引用 locator 可解析率 | 100% |
| 本地查询 P95 | < 2 秒 |
| 单次最终 chunk 数 | ≤ 12 |
| 单次 EvidencePack 正文 | ≤ 20,000 字符 |

还需满足：

- 本地覆盖充分时不触发 Web Search；
- 更新失败不影响上一版索引查询；
- 相同索引和请求能够基本复现检索结果；
- 所有正式引用能定位到 source、snapshot 和 chunk；
- 数据库可以从 registry 和 snapshots 完整重建。

## 21. 实施阶段

### S0：契约与评测准备

交付：

- RetrievalRequest schema；
- EvidencePack schema；
- 20–30 条首批金标问题；
- `config/rag.yaml` 初版。

预计：1–2 个开发日。

### S1：数据库与 FTS 基础

交付：

- schema 和迁移机制；
- WAL、事务、连接管理；
- CJK/word 双 FTS；
- Insert/Update/Delete triggers；
- integrity check。

预计：2 个开发日。

### S2：Registry、Snapshot 与 Ingestion

交付：

- YAML registry 同步；
- snapshot 文件布局；
- hash 和幂等 ingestion；
- 内容质量门禁；
- 原子激活和失败回退。

预计：2–3 个开发日。

### S3：解析与结构化分块

交付：

- HTML/PDF 标准化；
- 条款、标题、页码 locator；
- 表格和长条文处理；
- parser/chunker version 记录。

预计：2–4 个开发日。

### S4：查询、融合与 Coverage

交付：

- QueryPlan；
- metadata filters；
- 双 FTS 召回；
- RRF、去重、来源限制；
- coverage 和 Web fallback 判定。

预计：2–3 个开发日。

### S5：Agent 工具接入

交付：

- SourceRegistrySearchTool；
- LocalRagSearchTool；
- LocalSourceReadTool；
- MainAgent 工具注册；
- RAG、Validate、Citation prompt 调整；
- EvidencePack 持久化。

预计：2–3 个开发日。

### S6：定时更新与运维

交付：

- updater CLI；
- due-source 调度；
- 锁、重试和日志；
- staging rebuild 和原子切换；
- launchd/systemd 示例。

预计：2–3 个开发日。

### S7：评测与调优

交付：

- 50–100 条金标集；
- Recall/MRR/nDCG 报告；
- tokenizer、BM25、RRF 参数调优；
- 端到端回归测试；
- 是否引入 Dense Retriever 的决策报告。

预计：3–5 个开发日。

总体预计：单人约 2–3 周完成首个生产可用版本。

## 22. 后续向量检索扩展

上层统一依赖 Retriever 接口：

```python
class Retriever:
    def search(self, request: RetrievalRequest) -> list[Evidence]:
        ...


class SqliteFtsRetriever(Retriever):
    ...


class DenseRetriever(Retriever):
    ...
```

只有满足以下条件时才进入 Dense Retrieval 阶段：

- 金标评测显示 FTS Recall@10 低于目标；
- 主要遗漏来自同义改写、口语化或跨语言表达；
- chunk 数量和并发规模明显增长；
- embedding 模型和运行方式已经稳定。

届时增加：

```text
SQLite FTS results ─┐
                    ├─ RRF → dedup → EvidencePack
Dense results ──────┘
```

无论后续选择 Elasticsearch、Chroma、sqlite-vec 或其他后端，以下部分保持不变：

- registry；
- immutable snapshots；
- chunk_uid；
- RetrievalRequest；
- EvidencePack；
- Validate 和 Citation 工作流；
- 定时更新与审计记录。

## 23. 非目标

第一阶段不实现：

- 面向互联网任意页面的通用爬虫；
- 自动生成最终法律意见；
- 未经审核自动推广新来源；
- 自动推断所有法规修订链；
- 多租户权限体系；
- 分布式索引；
- 持久向量数据库；
- 扫描件高精度 OCR 服务；
- 对受限法律数据库的自动绕过访问。

## 24. 参考资料

- [SQLite FTS5 Extension](https://www.sqlite.org/fts5.html)
- [Qwen-Agent Tool Introduction](https://github.com/QwenLM/Qwen-Agent/blob/main/qwen-agent-docs/website/content/en/guide/core_moduls/tool.md)
- 项目来源元数据约定：`src/sources/README.md`
- 项目检索任务模板：`src/templates/retrieval-task.md`
- 项目当前 RAG prompt：`src/prompts/prompts.py`
- 项目当前 pipeline：`src/agent/main_agent.py`

