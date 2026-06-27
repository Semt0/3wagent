# 架构设计说明（Design Notes）

本文沉淀 3wagent 的**设计取舍与人机分工**，与两份既有文档互补：

- `README.md` / `README.zh-CN.md` — 功能概览、目录结构与使用方法
- `docs/rag-mcp-design.md` — 检索层（RAG / MCP 工具）的接口设计

这里只讲 **为什么这样设计**，以及 **哪些由人定义、哪些交给 agent 实现**。

---

## 1. 核心命题：人定义边界，agent 负责实现

3wagent 把一次跨境政策研究拆成两类工作：

| 角色 | 负责什么 | 沉淀在哪里 |
|------|----------|------------|
| **人类（架构师）** | 定义问题边界、领域判断规则、来源可信分级、输出契约、不做什么 | `config/`、`.claude/principles.md`、`.claude/contracts.md` |
| **Agent（执行者）** | 在既定边界内检索、校验、分析、生成报告与配套工具代码 | `.claude/agents/`、`.claude/skills/`、`tools/`、`mcp_server/`、`server/` |

项目的智力核心不是某段代码，而是这套**被显式写下来的判断边界**：什么时候资金合规优先、
什么时候税务独立分析、哪些来源能支撑结论、输出必须包含哪 5 项。代码只是这些边界的执行壳。

---

## 2. 关键架构决策：agent-native，而非自建 runtime

第一版曾用 Python / FastAPI / LangChain 搭后端原型（见 `CHANGELOG.md` 阶段二）。随后做出
本项目最重要的一次转向：**移除自建分析 runtime，改由 Claude Code / Codex 通用 agent 承载执行**。

理由：

- 通用 coding agent 已具备工具调用、文件读写、检索与任务拆分能力，重写一套编排框架是重复劳动
- 个人研究场景下，**领域规则的稳定性** 比 **运行时工程** 更值钱
- 规则、技能、子代理以纯文本沉淀，可审计、可 diff、可复用，迁移成本低

由此形成一条边界（`principles.md` 第 7 条）：**规则、技能、子代理够用时，不另造后台框架**。
当前的 FastAPI dashboard 与 MCP bridge 都只是**薄的可选层**，只读本地文件、不承载分析逻辑。

---

## 3. 分层与依赖方向

依赖严格单向，**配置与逻辑分离**：

```
config/*.yaml            ← 策略数据唯一来源（routing / source-levels / jurisdictions / output-contract）
   ▲ 被引用
.claude/agents, skills   ← 子代理与技能引用 config，不复写策略定义
   ▲ 被编排
.claude/CLAUDE.md        ← Lead Policy Agent 顶层编排，只指向 config 与 principles
   ▲ 可选观测
tools / mcp_server /      ← 检索索引、报告生成、进度日志、dashboard（只读本地产物）
server / viewer
```

好处：改一处生效全局。例如新增一类问题分类，只改 `config/routing.yaml`，
所有引用它的子代理与技能自动对齐，无需逐个文件同步。

---

## 4. 按关注点组织

`.claude/agents/` 与 `.claude/skills/` 都按关注点分目录，改某一环只看对应目录：

| 关注点 | 子代理 | 技能 |
|--------|--------|------|
| parsing 解析 | `document-parser` | `document-parse`、`liteparse` |
| retrieval 检索 | `rag-retriever` | `rag-retrieval`、`source-ingestion` |
| validation 校验 | `regulatory-validity-verifier`、`citation-verifier` | `regulatory-validity-verification`、`citation-verification` |
| analysis 分析 | `funds-compliance-analyst`、`tax-policy-analyst`、`commercial-law-analyst` | `policy-research` |

---

## 5. 一次请求的流动

```
用户问题 / 文档
  → Lead Policy Agent 识别法域·领域·付款性质，按 routing.yaml 分类
  → （如有文件）document-parser 解析
  → rag-retriever 先查 sources/ registry 与本地 RAG 索引，含类案库
  → regulatory-validity-verifier 校验时效与单层级修订关系
  → 专项 analyst 在各自边界内分析
  → citation-verifier 校验法域·来源等级·结论支撑
  → Lead Policy Agent 综合，按 output-contract.yaml 写 5 项核心输出
  → 归档 reports/YYYYMMDD-topic/report.md(+pdf)，progress.py 记录进度
```

编排（路由、冲突处理、最终写作）始终由主会话掌握；子代理只做自包含专项任务，
返回**证据而非成稿**，避免下层代理自由发挥越过人定义的边界。

---

## 6. 边界（Non-Goals）

明确「现在不做什么」与「做什么」同样重要：

- 不在 MVP 阶段自建 FastAPI / LangChain 分析 runtime
- 来源规模未要求前，不引入持久向量数据库（先用 SQLite FTS）
- C / D 级来源（专业简报、公众号、媒体）不得作为最终法律依据，只作线索
- 不做未经引用校验的自动法律结论

这些边界由人显式设定，确保 agent 的高效执行不会滑出可审计、可信赖的研究流程。
