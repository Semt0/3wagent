<h1 align="center">3wagent</h1>

<p align="center">
  <strong>个人跨境政策研究 Agent Workspace</strong><br>
  从问题识别、政策检索、法规时效校验到报告归档，全程交给 Claude Code subagents 执行
</p>

<p align="center">
  <a href="README.md">English</a>
  ·
  <a href="CHANGELOG.md">CHANGELOG</a>
</p>

---

## 快速开始

### 第一步：clone 仓库到本地

本项目不需要启动后端服务，也不需要运行单独的 agent runtime。先把仓库 clone 到本地：

```bash
git clone git@github.com:Semt0/3wagent.git
cd 3wagent
```

如果使用 Claude Code，在仓库目录中打开即可，`.claude/CLAUDE.md` 会作为项目规则自动读取。

如果使用 Codex，需要显式提醒它读取规则：

```text
请阅读这个仓库的 .claude/CLAUDE.md，并按 3wagent workflow 分析我的问题。
```

### 第二步：直接输入问题或上传文件

```text
香港公司向新加坡公司支付服务费，需要关注哪些税务和银行合规问题？
```

也可以上传 PDF / Word 后提问：

```text
请分析这份协议里涉及的跨境付款、税务和公司法风险。
```

### 第三步：等待 Agent 输出报告

Agent 会输出三项结果：

```text
1. 对话中的纯文本政策分析
2. reports/YYYYMMDD-topic/report.md
3. reports/YYYYMMDD-topic/report.pdf
```

如果本地暂时缺少 Markdown 转 PDF 工具，会先保留 `report.md`，并说明 PDF 未生成的原因。

---

## Motivation：为什么不是再造一个应用

3wagent 的目标不是先做一个庞大的法律科技产品，而是搭一个给自己使用的跨境政策研究工作区。

对于这个阶段，更重要的是把政策研究的判断边界沉淀下来：

- 什么时候优先看资金流动、银行合规、AML 和制裁
- 什么时候税务独立分析，不强行牵扯外汇
- 什么时候补充公司法、合同、牌照和民商法规
- 哪些资料可以作为依据，哪些资料只能作为线索
- 最终如何稳定输出法规索引和风险提示

所以项目暂时不自建 FastAPI / LangChain / LangGraph runtime，而是直接使用 Claude Code 的 rules、skills 和 subagents。通用 coding agent 已经具备工具调用、文件读写、检索和任务拆分能力；这个仓库只负责提供稳定的领域规则和执行边界。

---

## Introduction

3wagent 面向中国内地、美国、香港、新加坡的跨境政策研究，支持：

- 直接输入政策问题
- 上传 PDF / Word 等材料后分析
- 从资金合规（含中国内地外汇管理）、税务、民商法规三个方向拆解问题
- 检索官方政策、法规和监管指引
- 区分官方依据、专业解读和公众号线索
- 输出纯文本分析、Markdown 归档报告和 PDF 报告

核心原则：

```text
官方法律 / 法规 / 监管指引优先
先确认法规和指引是否现行有效
专业机构文章只作为辅助解释
公众号和媒体内容只作为线索
没有来源的结论必须降级
```

---

## Features

| 功能 | 说明 |
|------|------|
| 问题识别 | 自动识别法域、交易类型、付款性质和主分析领域 |
| 文档解析 | 内置 `liteparse` skill，优先处理 PDF / Word / 扫描件 |
| Subagent 分析 | 资金合规、税务、民商法规分别由专项 subagent 处理 |
| 政策检索 | 先查 `sources/`，再按 CN / US / HK / SG 和 funds / tax / commercial 过滤来源 |
| 法规时效性校验 | 检查法规、通知、指引和官方案例是否现行有效、被替代或需按交易时间适用历史版本 |
| 引用校验 | 检查结论是否由正确法域和正确来源支持 |
| 报告归档 | 同步生成 `report.md` 和 `report.pdf` |

---

## Claude Code 会做什么

### 模式一：直接政策问题

当你只输入一个问题时：

```text
1. Lead Policy Agent 识别法域、主体、交易和付款性质
2. 判断主领域：资金合规 / 税务 / 民商法规
3. 召唤 rag-retriever 先查 `sources/`，再检索官方来源
4. 调用 regulatory-validity-verifier 校验法规时效和版本适用性
5. 按需调用专项 subagents
6. 调用 citation-verifier 校验依据
7. 输出纯文本结论
8. 写入 reports/YYYYMMDD-topic/report.md
9. 转换为 reports/YYYYMMDD-topic/report.pdf
```

### 模式二：文件 + 问题

当你上传 PDF / Word 时：

```text
1. document-parser 解析文件
   └─ 优先使用 liteparse
   └─ 保留页码、标题、表格、脚注和 OCR 不确定性

2. Lead Policy Agent 提取交易事实
   └─ 主体、金额、币种、付款路径、合同类型、收入性质

3. rag-retriever 先查 `sources/` registry，再检索来源
   └─ 官方法规和监管指引优先
   └─ 专业文章和公众号只作为线索

4. regulatory-validity-verifier 校验来源时效
   └─ 是否现行有效、已废止、被替代、被修订或只适用特定时间点

5. 专项 subagents 分析
   └─ funds-compliance-analyst
   └─ tax-policy-analyst
   └─ commercial-law-analyst

6. citation-verifier 校验
   └─ 检查法域、来源等级和结论支撑关系

7. 生成最终答复和报告文件
```

---

## Agent Team 结构

```text
Lead Policy Agent（主会话）
│
├── document-parser
│   └── PDF / Word / 图片 / 表格解析，不做法律分析
│
├── rag-retriever
│   └── 检索官方政策、法规、监管指引和辅助资料
│
├── regulatory-validity-verifier
│   └── 校验法规、通知、指引和官方案例的现行有效性与版本适用性
│
├── funds-compliance-analyst
│   └── 资金流动、银行 KYC、AML/CFT、OFAC、制裁、付款牌照
│
├── tax-policy-analyst
│   └── 预提税、利得税、企业所得税、GST/VAT、税收协定
│
├── commercial-law-analyst
│   └── 公司设立、股权转让、合同、董事责任、牌照和登记
│
└── citation-verifier
    └── 校验引用、来源等级、法域匹配和结论可靠性
```

主会话负责路由、任务拆分、冲突处理和最终写作。subagent 只处理自包含专项任务，不承担顶层编排。

---

## Workflow

```text
用户输入问题或上传 PDF / Word
  ↓
Lead Policy Agent 识别问题、法域、主领域和辅助领域
  ↓
如有文件，调用 document-parser，并优先使用 liteparse 解析
  ↓
Lead Policy Agent 形成任务包并决定使用哪些 subagents
  ↓
rag-retriever 先查 `sources/` registry，再检索官方政策、法规和辅助资料
  ↓
regulatory-validity-verifier 校验法规时效、版本和适用时间点
  ↓
专项 subagents 分析
  ├── funds-compliance-analyst
  ├── tax-policy-analyst
  └── commercial-law-analyst
  ↓
citation-verifier 校验引用、法域、来源等级和结论可靠性
  ↓
Lead Policy Agent 生成最终纯文本答复
  ↓
同时在 reports/YYYYMMDD-topic/ 生成 report.md
  ↓
将 report.md 转换为 report.pdf
```

---

## 路由规则

| 触发条件 | 主分析方向 |
|----------|------------|
| 跨境付款、汇款、银行 KYC、资金来源、OFAC、制裁、账户、投资款、分红汇出 | 资金合规 |
| 预提税、利得税、企业所得税、GST/VAT、股息、利息、特许权使用费、服务费、资本利得、税收协定 | 税务 |
| 公司设立、董事、股东、股权转让、合同、商业登记、牌照、投资准入 | 民商法规 |

如果税务和资金问题同时出现，且核心是付款性质判断，则税务作为主分析，资金合规作为辅助分析。

---

## 来源等级

| 等级 | 来源类型 |
|------|----------|
| S | 法律原文、法规、条例和官方法律数据库 |
| A | 监管机构指引、税局指引和官方 FAQ |
| B | 官方通函、公告、判例和正式通知 |
| C | 律所、会计师事务所、银行或专业机构简报 |
| D | 公众号、媒体文章和个人评论 |

C 和 D 级来源只能作为线索，不能作为最终法律依据。

---

## 输出结构

```text
【问题识别】
【简要结论】
【资金流动 / 银行合规 / AML / 制裁分析】
【税务分析】
【民商法规分析】
【法规与政策索引】
【法规时效性校验】
【实务文件清单】
【风险提示】
【结论可靠性】
【报告文件】
```

---

## 项目结构

```text
.claude/
  CLAUDE.md                     Claude Code 项目级规则和 lead agent 约束
  agents/                       项目级 subagents
  skills/                       政策研究、检索、引用校验和来源采集规则

.agents/
  skills/
    liteparse/                  项目内置的第三方文档解析 skill

docs/
  rag-mcp-design.md             RAG / MCP 工具设计草案

sources/
  README.md                     来源 registry 字段和等级说明
  cn.yaml                       中国内地官方来源索引
  us.yaml                       美国官方来源索引
  hk.yaml                       香港官方来源索引
  sg.yaml                       新加坡官方来源索引

templates/
  report.md                     归档报告模板
  retrieval-task.md             rag-retriever 任务包模板

tools/
  render_report.py              生成 report.md 并尽量转换 report.pdf

reports/
  .gitkeep                      报告生成目录占位
  YYYYMMDD-topic/
    report.md                   详细 Markdown 报告，本地产物
    report.pdf                  Markdown 转换后的 PDF，本地产物

CHANGELOG.md                    项目演进记录
README.md
README.zh-CN.md
pyproject.toml
uv.lock
skills-lock.json
```

---

## 本地设置

安装最小工具环境：

```bash
uv venv
source .venv/bin/activate
uv sync --extra dev
```

`liteparse` 已随仓库提供。只有需要刷新或重新安装该 skill 时，才运行：

```bash
npx skills add run-llama/llamaparse-agent-skills --skill liteparse
```

检查配置文件：

```bash
uv run ruff check .
```

生成一份本地报告模板：

```bash
uv run python tools/render_report.py --title "示例政策报告" --topic sample --overwrite
```

---

## Discussion

当前版本优先验证 agent-native workflow，不急于产品化。后续只有在以下需求稳定出现时，才考虑加入更重的工程层：

- 需要长期维护本地 RAG 索引
- 需要多人共享同一套政策资料库
- 需要 Web UI、权限、文件管理或审计日志
- 需要把高频流程封装为 MCP 工具或后台服务

在此之前，3wagent 的核心仍然是：用尽量少的项目代码，把 Claude Code / Codex 的通用 agent 能力约束在一个清晰、可复用、可审计的跨境政策研究流程里。
