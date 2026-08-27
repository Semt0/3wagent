# 3wagent Refactor（基于 qwen-agent 的新运行时）

`src/` 是 3wagent 的第二次架构转向：重新自建 runtime，但基于 [qwen-agent](https://github.com/QwenLM/qwen-agent) 而非 LangChain。`src/` 同时也是新框架的运行时根目录；运行所需的配置、来源注册表、模板与 Web Search 服务均位于其中，不依赖仓库根目录的旧架构。

> 原架构说明见仓库根目录的 `docs/architecture.md`；本文档只描述 `src/` 重构。

## 当前状态

骨架已搭好并可在本地 llama-server 上跑通对话；多子代理路由、检索、校验、领域分析、引用核验和报告写作流水线已经接入，仍处于持续验证阶段。

## 目录结构

```
src/
├── main.py                 # CLI 入口（argparse + 启动 agent + Gradio WebUI）
├── pyproject.toml          # 独立包 3wagent-refactor，依赖 qwen-agent[gui,python-executor]
├── environment.yml         # 等价的 conda 环境定义（python 3.12）
├── agent/
│   ├── attachments.py      # 将上传的文本附件安全地内联到模型上下文
│   ├── main_agent.py       # MainAgent(FnCallAgent) 与子 agent 流水线编排
│   └── subagent.py         # Routing/RAG/Validate/Analyst/Citation/Writer 子 agent
├── config/
│   ├── llm.py              # LLM provider 配置加载器
│   ├── llm.yaml            # DeepSeek / Kimi / local provider 配置
│   ├── webui.py            # Gradio WebUI 的 chatbot 配置（prompt 建议）
│   ├── logger.py           # DEBUG 模式文件日志，写 src/workspace/logs/<model><ts>.log
│   └── *.yaml              # 路由、法域、来源等级与输出契约
├── sources/                # 各法域官方来源注册表
├── templates/              # 报告与检索任务模板
├── infra/open-websearch/   # 固定版本的本地 Web Search daemon
├── tools/
│   ├── read_markdown_files.py  # MarkDownReadTool
│   ├── read_yaml_files.py      # YamlReadTool
│   ├── web_search.py           # WebSearchTool（候选来源发现）
│   └── web_fetch.py            # WebFetchTool（网页正文抓取）
├── websearch/
│   ├── client.py               # open-websearch daemon HTTP 客户端
│   ├── policy.py               # 法域搜索引擎和官方域名策略
│   └── protocol.py             # 稳定的内部返回结构
├── prompts/
│   └── prompts.py          # MAIN_AGENT_SYS_PROMPT 系统提示词
├── reports/                # 生成的正式报告（运行时创建，Git 忽略）
├── workspace/              # 子代理中间产物与日志（运行时创建，Git 忽略）
└── llm/                    # 空占位目录，LLM 逻辑目前在 config/llm.py
```

## 运行方式

```bash
# 在项目根目录（src/ 的上一级）执行；默认使用 src/config/llm.yaml 的 local
python -m src.main
python -m src.main --provider deepseek
python -m src.main --provider kimi
python -m src.main --provider local --model <model-name>
python -m src.main -d              # DEBUG 模式，日志写入 src/workspace/logs/
```

启动时会自动探测并启动本地 open-websearch daemon，随后打开 qwen-agent
内置的 Gradio WebUI。程序退出时会关闭本次启动的 daemon；如果 daemon
原本已经运行，则只复用、不关闭。

### 外部模型 API + 本地 Agent

`src/config/llm.yaml` 是 LLM provider 的配置入口，当前内置 `deepseek`、
`kimi` 和原有的 `local` 三个配置。DeepSeek 与 Kimi 都使用 OpenAI-compatible
Chat Completions 接口；API key 只从环境变量读取，不应写进 YAML 或提交到 Git。

先设置对应密钥：

```bash
export DEEPSEEK_API_KEY="你的 DeepSeek API key"
# 或：export MOONSHOT_API_KEY="你的 Kimi API key"
```

然后启动：

```bash
python -m src.main --provider deepseek
python -m src.main --provider kimi
python -m src.main --llm-config path/to/my-llm.yaml --provider my-provider
```

如需换模型，可以用 `--model` 覆盖 YAML 中的模型名；如需新增 provider，复制
`llm.yaml` 中的一个 provider，修改 `model`、`model_server` 和 `api_key_env` 即可。
如果不想修改仓库内的默认文件，可用 `--llm-config path/to/my-llm.yaml` 指向自己的配置。

### 远程部署模型 + 本地 Agent（兼容保留）

LLM 推理服务可以运行在远程 GPU 服务器，Agent、Gradio WebUI 和 Web
Search 运行在本地。推荐启动顺序如下。

1. 在远程服务器启动 OpenAI API 兼容的 LLM 推理服务。
2. 通过 SSH 将远程推理端口转发到本地 `127.0.0.1:11434`。例如远程服务
   监听 `8000` 时：

   ```bash
   ssh -N -L 11434:127.0.0.1:8000 <user>@<server>
   ```

3. 首次使用时，在本地安装 OpenWebSearch 的固定版本依赖：

   ```bash
   npm ci --prefix src/infra/open-websearch
   ```

4. 确认本地能够访问转发后的 LLM API：

   ```bash
   curl http://127.0.0.1:11434/v1/models
   ```

5. 在项目根目录启动 Agent：

   ```bash
   python -m src.main
   # 或指定远程推理服务中加载的模型名
   python -m src.main -m <model-name>
   ```

程序随后会自动启动本地 OpenWebSearch、启动 Gradio WebUI，并在终端输出
WebUI 地址。浏览器中的 Agent 会自动获得 `WebSearchTool` 和
`WebFetchTool`；专业政策问题进入检索、法规有效性验证或引用核验阶段时，
Agent 会按需调用这些工具，简单对话通常不会触发搜索。

LLM 请求通过 SSH 隧道发送到远程服务器；搜索引擎访问和官方网页抓取则
从本地机器发起，因此本地网络必须能够访问所选搜索引擎及目标网站。
OpenWebSearch 启动日志位于：

```text
src/workspace/logs/open-websearch.log
```

### Web Search 配置

Web Search 使用独立的本地 `open-websearch` daemon。安装与启动方法见
[`infra/open-websearch/README.md`](infra/open-websearch/README.md)。默认地址为
`http://127.0.0.1:3210`。

可用环境变量：

| 变量 | 默认值 | 说明 |
|---|---:|---|
| `OPEN_WEBSEARCH_URL` | `http://127.0.0.1:3210` | daemon 地址；默认只允许 localhost |
| `OPEN_WEBSEARCH_ALLOW_REMOTE` | `false` | 显式允许远程 daemon，不建议日常开启 |
| `OPEN_WEBSEARCH_AUTOSTART` | `true` | 随 `python -m src.main` 自动启动本地 daemon |
| `OPEN_WEBSEARCH_STARTUP_TIMEOUT_SECONDS` | `15` | daemon 就绪等待时间，范围 1–120 秒 |
| `WEBSEARCH_TIMEOUT_SECONDS` | `30` | 单次 HTTP 调用超时，范围 1–120 秒 |
| `WEBSEARCH_MAX_RESULTS` | `10` | 搜索结果硬上限，范围 1–50 |
| `WEBFETCH_MAX_CHARS` | `20000` | 单页正文字符硬上限，范围 1000–200000 |
| `WEBSEARCH_FALLBACK_TO_SEARXNG` | `false` | open-websearch 失败或无结果时回退旧 SearXNG |

检索遵循：本地 `sources/` registry 优先，开放网络仅作补充；搜索摘要只能用于发现候选 URL，必须通过 `WebFetchTool` 获取官方页面正文后才能作为证据。法域对应的引擎与官方域名配置位于 `config/jurisdictions.yaml`。

### LLM 配置

LLM 配置位于 `src/config/llm.yaml`，由 `src/config/llm.py` 加载。provider 的结构为：

- `model`: 服务商要求的模型 ID
- `model_server`: OpenAI-compatible base URL
- `api_key_env`: 存放密钥的环境变量名
- `generate_cfg`: qwen-agent 的生成参数

不同服务商对生成参数的约束可能不同；例如内置 Kimi K2.5 配置默认不额外传递
`temperature` 和 `top_p`。

也可以设置 `LLM_PROVIDER=kimi`，作为 `--provider` 之外的环境变量方式。

## 架构要点

| 维度 | 说明 |
|---|---|
| Agent 基类 | `FnCallAgent`（function-call 风格，非 Assistant/ReActChat） |
| 前端 | qwen-agent 内置 `qwen_agent.gui.WebUI`（Gradio） |
| 工具注册 | `@register_tool` + `BaseTool`，在 `main_agent.py` 中 import 触发注册，以字符串名传给 `function_list`（未使用 MCP） |
| 系统提示词 | `MAIN_AGENT_SYS_PROMPT`，移植自旧 `.claude/CLAUDE.md` 的 Lead Policy Agent 规则（子代理树、8 步工作流、`reports/YYYYMMDD-topic/` 归档） |
| 领域策略 | `src/config/*.yaml`（工具中的运行时相对路径为 `config/*.yaml`），由提示词引导模型用 `YamlReadTool` 自行读取 |

主要工具：

- **MarkDownReadTool** — 读取 Markdown 文件全文（入参 `file_path`）
- **YamlReadTool** — 读取 YAML 文件全文（入参 `file_path`）
- **WebSearchTool** — 调用 open-websearch 搜索候选来源并标记官方域名
- **WebFetchTool** — 抓取候选页面正文和来源元数据；网页内容始终视为不可信证据

## 与原架构的关键差异

原项目的核心决策是 "agent-native，不自建 runtime"：分析逻辑由 Claude Code 承载，规则沉淀在 `.claude/CLAUDE.md`、`.claude/agents/` 和 `config/*.yaml` 中。本次重构：

**被 qwen-agent 替代的**：对话循环、工具调用协议、Web 交互界面、消息 schema。

**保留为自定义的**：领域提示词、`src/config/*.yaml` 策略文件、`src/sources/` 来源注册表、`src/templates/` 和文件读取工具。仓库根目录的旧目录可以在迁移完成后删除，不影响新运行时。

## 当前流水线

`MainAgent._run()` 会将上传的 Markdown、纯文本和 YAML 文件内联到模型上下文；如果用户未输入提示词且没有附件成功解析，则直接返回格式提示，不进入 FnCallAgent 工具循环。专业问题依次经过：

1. 附件解析（parsing）
2. Routing（策略路由）
3. RAG 检索
4. Validate（来源校验）
5. 领域分析
6. Citation-Verifier（引用核验）
7. Report Writing（报告生成与归档）

开放网络工具只分配给 RAG、时效校验和引用核验步骤；领域分析只消费前序证据包。后续重点是扩大端到端评测样本、完善检索快照归档，并根据真实失败情况决定是否启用 Playwright 浏览器兜底。
