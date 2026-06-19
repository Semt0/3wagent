# Task Package & Output Contract

## Task Package (send to every subagent)

- Issue profile
- Primary and secondary domains
- Jurisdiction filters
- Relevant date or "as of" date
- Retrieval plan or source pack
- Required skills
- MCP/RAG tool hints
- Final output contract

## Output Contract

The final report must address the sections defined in `config/output-contract.yaml`.

**5 required sections** (Chinese by default):

1. **【问题分类】** — Classification per `config/routing.yaml`, sub-domains and transaction type.
2. **【结论或考量维度】** — Directly quotable conclusions, or dimensions that must be considered.
3. **【类案与公开答案】** — Analogous public judgments with case numbers, courts, key holdings and quoted excerpts.
4. **【涉及现行法规】** (Priority) — Complete numbered list of currently effective laws, regulations and guidance, with jurisdiction, domain, issuing authority and current status.
5. **【法规修订关系】** — Single-tier amendment lineage for each effective regulation.

**3 supporting sections:**

- 【风险提示】
- 【结论可靠性】
- 【报告文件】

Source reliability rules are in `config/source-levels.yaml`. C and D sources cannot support final conclusions.
