# 3wagent 演进历程

> 从 Python 应用原型到 Claude Code subagent-native 的跨境政策研究工作区

---

## 阶段一：项目初始化

**Commit:** `872f15b`

- 创建 3wagent 仓库
- 确立项目方向：面向美国、香港、新加坡的跨境政策研究 Agent
- 初步沉淀需求：输入问题或 PDF/Word，输出带政策分析和法规索引的纯文本结果

---

## 阶段二：Python / LangChain 应用原型

**Commits:** `271e4ca`, `fda7deb`

第一版采用传统应用架构，用 Python 后端承载 agent 工作流：

- 新增 Python 项目配置、`uv` 包管理和基础开发环境
- 搭建 FastAPI / LangChain 风格的后端原型
- 拆分文档解析、问题路由、检索、专项分析和证据校验模块
- 设计资金合规、税务、民商法规三条分析主线
- 预留后续 RAG、MCP、前端和服务化扩展空间

这一阶段验证了业务边界，但整体架构对个人项目偏重。

---

## 阶段三：项目框架文档化

**Commit:** `1585b4d`

- 系统整理 README，说明项目定位、技术栈和初始开发流程
- 明确外汇/资金合规、税务、民商法规的路由优先级
- 讨论 Docker、前端、包管理、RAG、MCP 和多人协作方式
- 将项目从想法收敛为可执行的工程框架

---

## 阶段四：Claude Code subagent-native 重构

**Commit:** `d712a01`

这是项目第一次关键架构转向：从自建 app runtime 转为 **Claude Code / Codex agent-native 工作区**。

核心变化：

- 移除 `app/`、`scripts/`、`tests/` 等应用后端原型代码
- 不再默认采用 FastAPI、LangChain、LangGraph 或 Streamlit 作为 MVP 主架构
- 新增 `.claude/CLAUDE.md`，将主会话定义为 Lead Policy Agent
- 新增 `.claude/agents/` 项目级 subagents：
  - `document-parser`
  - `rag-retriever`
  - `funds-compliance-analyst`
  - `tax-policy-analyst`
  - `commercial-law-analyst`
  - `citation-verifier`
- 新增 `.claude/skills/`，沉淀文档解析、政策研究、RAG 检索、引用校验和来源采集规则
- 引入 `liteparse`，并将其作为项目内置 PDF/文档解析 skill 放入 `.agents/skills/liteparse/`
- 精简 `pyproject.toml`，仅保留最小项目元数据和开发工具
- 精简 `.gitignore`，保留虚拟环境、本地密钥、Claude 本地设置和编辑器噪音

架构原则：

- 主会话负责任务识别、路由、任务包构造、冲突处理和最终输出
- subagent 只负责自包含专项任务，不承担顶层编排
- 官方法规和监管指引优先，公众号和专业文章只作为辅助线索
- 每次深度分析前先形成任务包，避免 agent 临场自由发挥

---

## 阶段五：报告归档与 PDF 输出

**Commit:** `d712a01`

- 新增 `reports/` 专门目录，用于保存每次政策分析的归档结果
- 约定每次完整分析输出：
  - `reports/YYYYMMDD-topic/report.md`
  - `reports/YYYYMMDD-topic/report.pdf`
- 在 `.claude/CLAUDE.md` 中加入 `Report Artifact Rule`
- 在中文 README 中写入从用户输入到报告生成的完整 workflow
- 通过 `.gitignore` 忽略生成的报告文件，仅保留 `reports/.gitkeep`

这一阶段让对话结果不仅停留在聊天窗口，也能沉淀为可分享、可留档的 Markdown 和 PDF 报告。

---

## 演进主线总结

| 阶段 | 核心变化 |
|------|---------|
| 项目初始化 | 明确跨境政策研究 Agent 方向 |
| 应用原型 | 用 Python / LangChain / FastAPI 验证模块边界 |
| 框架文档化 | 梳理技术栈、路由规则和协作方式 |
| Agent-native 重构 | 转向 Claude Code rules / skills / subagents |
| 报告归档 | 固定生成 Markdown 和 PDF 报告文件 |

当前系统的核心形态：

- **运行方式**：Claude Code 主会话作为 Lead Policy Agent
- **协作方式**：项目级 subagents 负责文档解析、检索、专项分析和引用校验
- **文档解析**：内置 `liteparse` skill
- **输出形式**：对话纯文本答复 + `reports/` 下的 Markdown / PDF 报告
- **扩展方向**：后续按需加入 RAG 工具和 MCP 工具，而不是提前搭建臃肿 app runtime
