# 3wagent Refactor（基于 qwen-agent 的新运行时）

`src/` 是 3wagent 的第二次架构转向：重新自建 runtime，但基于 [qwen-agent](https://github.com/QwenLM/qwen-agent) 而非 LangChain。它与仓库根部的旧架构（Claude Code 驱动的 agent-native 方案）并行存在，目前是**早期脚手架阶段**。

> 原架构说明见仓库根目录的 `docs/architecture.md`；本文档只描述 `src/` 重构。

## 当前状态

骨架已搭好并可在本地 llama-server 上跑通对话；核心价值——多子代理路由 / 检索 / 校验流水线——尚未实现（见下文「路线图」）。

## 目录结构

```
src/
├── main.py                 # CLI 入口（argparse + 启动 agent + Gradio WebUI）
├── pyproject.toml          # 独立包 3wagent-refactor，依赖 qwen-agent[gui,python-executor]
├── environment.yml         # 等价的 conda 环境定义（python 3.12）
├── agent/
│   ├── attachments.py      # 将上传的文本附件安全地内联到模型上下文
│   └── main_agent.py       # MainAgent(FnCallAgent) 子类 + run_3wagent() 启动函数
├── config/
│   ├── llm.py              # LLM 连接配置（BASIC_CONFIG 模板 + load_llm_config）
│   ├── webui.py            # Gradio WebUI 的 chatbot 配置（prompt 建议）
│   └── logger.py           # DEBUG 模式文件日志，写 workspace/logs/<model><ts>.log
├── tools/
│   ├── read_markdown_files.py  # MarkDownReadTool
│   └── read_yaml_files.py      # YamlReadTool
├── prompts/
│   └── prompts.py          # MAIN_AGENT_SYS_PROMPT 系统提示词
└── llm/                    # 空占位目录，LLM 逻辑目前在 config/llm.py
```

## 运行方式

```bash
# 在项目根目录（src/ 的上一级）执行
python -m src.main                 # 默认模型 finance-27b
python -m src.main -m <model-name> # 切换 llama-server 上挂载的其他模型
python -m src.main -d              # DEBUG 模式，日志写入 workspace/logs/
```

启动后通过 qwen-agent 内置的 Gradio WebUI 进行交互。

### LLM 配置

`config/llm.py` 中只有一个 OpenAI 兼容端点模板：

- `model_server`: `http://127.0.0.1:11434/v1`（远程 llama-server 经 SSH 隧道转发到本地）
- `api_key`: `"EMPTY"`
- `generate_cfg`: `temperature: 0.15, top_p: 0.85`

`load_llm_config(model_name)` 深拷贝模板并填入模型名。暂不支持多 provider；"多模型"仅靠 `-m` 参数切换模型名。

## 架构要点

| 维度 | 说明 |
|---|---|
| Agent 基类 | `FnCallAgent`（function-call 风格，非 Assistant/ReActChat） |
| 前端 | qwen-agent 内置 `qwen_agent.gui.WebUI`（Gradio） |
| 工具注册 | `@register_tool` + `BaseTool`，在 `main_agent.py` 中 import 触发注册，以字符串名传给 `function_list`（未使用 MCP） |
| 系统提示词 | `MAIN_AGENT_SYS_PROMPT`，移植自旧 `.claude/CLAUDE.md` 的 Lead Policy Agent 规则（子代理树、8 步工作流、`reports/YYYYMMDD-topic/` 归档） |
| 领域策略 | 仓库根部 `config/*.yaml`（routing / source-levels / jurisdictions / output-contract）原样保留，由提示词引导模型用 `YamlReadTool` 自行读取 |

已有工具：

- **MarkDownReadTool** — 读取 Markdown 文件全文（入参 `absolute_address`）
- **YamlReadTool** — 读取并解析 YAML 文件（入参 `absolute_address`）

## 与原架构的关键差异

原项目的核心决策是 "agent-native，不自建 runtime"：分析逻辑由 Claude Code 承载，规则沉淀在 `.claude/CLAUDE.md`、`.claude/agents/` 和 `config/*.yaml` 中。本次重构：

**被 qwen-agent 替代的**：对话循环、工具调用协议、Web 交互界面、消息 schema。

**保留为自定义的**：领域提示词、`config/*.yaml` 策略文件、文件读取工具。旧的 `server/`、`mcp_server/`、`tools/`、`.claude/` 全部原样保留。

## 路线图

`MainAgent._run()` 目前会将上传的 Markdown、纯文本和 YAML 文件内联到模型上下文；如果用户未输入提示词且没有附件成功解析，则直接返回格式提示，不进入 FnCallAgent 工具循环。注释中规划的其余子代理流水线尚待落地：

1. 附件解析（parsing）
2. Routing（策略路由）
3. RAG 检索
4. Validate（来源校验）
5. 领域分析
6. Citation-Verifier（引用核验）
7. Report Writing（报告生成与归档）

下一步方向：将 `.claude/agents/` 的各子代理用 qwen-agent 的多 agent 机制在 `MainAgent._run()` 中编排落地。
