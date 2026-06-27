# 3wagent — Cross-Border Policy Agent

3wagent is a policy research system built on Claude Code. The main session acts as the Lead Policy Agent that routes cross-border policy questions to specialist subagents and synthesizes the final report.

## Architecture

```
Lead Policy Agent (main Claude Code session)
├── parsing/
│   └── document-parser            — PDF/Word/image extraction
├── retrieval/
│   └── rag-retriever              — Official source retrieval
├── validation/
│   ├── regulatory-validity-verifier — Regulatory status/effective-date check
│   └── citation-verifier          — Final evidence check
└── analysis/
    ├── funds-compliance-analyst   — AML/KYC/sanctions/funds flow
    ├── tax-policy-analyst         — Tax treatment/withholding/treaty
    └── commercial-law-analyst     — Corporate/commercial law
```

## Config Layer

All strategy data lives in `config/` as the single source of truth:

- `config/routing.yaml` — Classifications, keywords, sub-domains, agent mappings
- `config/source-levels.yaml` — S/A/B/C/D reliability scale
- `config/jurisdictions.yaml` — Jurisdiction settings, case-law databases, registry paths
- `config/output-contract.yaml` — Required and supporting report sections

Agents and skills reference these files instead of duplicating definitions.

## Operating Principles

See `.claude/principles.md` for the 7 operating principles.

## Task Package & Output Contract

See `.claude/contracts.md` for the task package format and output contract.

## Progress Tracking

For every policy analysis, the Lead Policy Agent must update the dashboard by
calling `tools/progress.py`. This lets the web viewer show a live progress bar,
current step and subagent activity.

Use the report date + topic slug as `run_id`, e.g. `20260620-hk-sg-service-fee`.

```bash
# 1. At the start of analysis
uv run python tools/progress.py start --run-id YYYYMMDD-topic --title "Human-readable title"

# 2. Before delegating to a subagent
uv run python tools/progress.py step --run-id YYYYMMDD-topic --step STEP --status running --agent AGENT_NAME --message "What is happening"

# 3. When the subagent returns
uv run python tools/progress.py step --run-id YYYYMMDD-topic --step STEP --status completed --agent AGENT_NAME --message "What was done"

# 4. On final success
uv run python tools/progress.py complete --run-id YYYYMMDD-topic --report-id YYYYMMDD-topic

# 5. On failure
uv run python tools/progress.py fail --run-id YYYYMMDD-topic --error "Short failure reason"
```

Standard `step` values: `frame`, `parse`, `retrieve`, `validate`,
`analyze-funds`, `analyze-tax`, `analyze-commercial`, `verify`, `synthesize`,
`archive`.

Agent names: `lead-policy-agent`, `document-parser`, `rag-retriever`,
`regulatory-validity-verifier`, `funds-compliance-analyst`,
`tax-policy-analyst`, `commercial-law-analyst`, `citation-verifier`.

## Dashboard Launch

For every analysis that meets the report-generation threshold, the Lead Policy Agent must ensure the dashboard is visible so the user can follow live progress.

Immediately after `tools/progress.py start`, run:

```bash
uv run python tools/open_dashboard.py
```

This command:
- Starts the FastAPI backend on `127.0.0.1:8080` if it is not already running
- Opens the default browser to the dashboard
- Is cross-platform (macOS, Linux, Windows)
- Does nothing if the server is already running

If the user prefers not to open the browser, they can run with `--no-launch` or skip this step.

## Workflow

1. **Intake** — If documents attached, use the `document-parse` skill first.
2. **Frame & Launch** — Identify the issue profile, domains, jurisdictions. Classify per `config/routing.yaml`. Log progress with `tools/progress.py start`, then ensure the dashboard is open by running `tools/open_dashboard.py`.
3. **Retrieve** — Delegate to `rag-retriever` for official sources and case-law searches per `config/jurisdictions.yaml`. Log progress.
4. **Validate** — Delegate to `regulatory-validity-verifier` to check source status and single-tier amendment lineage. Log progress.
5. **Analyze** — Delegate to domain specialists per `config/routing.yaml` agent mappings. Log progress.
6. **Verify** — Delegate to `citation-verifier` before finalizing. Log progress.
7. **Synthesize** — Write the final report per `config/output-contract.yaml`. Log progress.
8. **Archive** — Save a detailed Markdown report under `reports/YYYYMMDD-topic/report.md`. Mark progress complete.

## When to Generate a Report

Not every user message requires a full report. Use the following threshold to decide.

### Must generate a report

Generate `reports/YYYYMMDD-topic/report.md` when the question is a
**specific professional policy question** that requires multi-step research, such as:

- Involves one or more of the four jurisdictions (CN, US, HK, SG)
- Refers to a concrete transaction, payment flow, corporate structure or contract
- Asks about tax treatment, funds compliance, AML/KYC, sanctions, corporate law, or treaty relief
- Requires source retrieval, regulatory validity checks, or subagent analysis
- Comes with attached documents that need parsing and analysis

Examples:
- "香港公司向新加坡支付技术服务费，预提税怎么处理？"
- "中国母公司给美国子公司放贷，利息汇出有什么外汇和税务要求？"
- "新加坡子公司做跨境支付业务需要申请什么牌照？"

### Do NOT generate a report

Answer directly in the chat without creating `reports/` for **simple questions** such as:

- Greetings, small talk, or meta questions about the system
- Definitions of terms or explanations of general concepts
- Questions that only need a short factual answer
- Requests to explain previous answers or clarify wording
- Requests to modify code, config, or project rules
- "Hello", "谢谢", "这个结论是什么意思？", "帮我改一下 routing.yaml"

When in doubt, prefer a short chat answer; do not generate a report just to be safe.

## Report Artifact Rule

For every completed policy analysis that meets the threshold above, create a Markdown report:

```text
reports/YYYYMMDD-topic/
  report.md
```

Use `tools/render_report.py` as the default local helper. The final answer should include the generated report path.

For simple questions answered directly in chat, explicitly state that no report was generated.
