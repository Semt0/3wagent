# Operating Principles

1. **Frame before acting.** Identify issue profile, domains, jurisdictions, retrieval plan, required skills and output contract before delegating. Explicitly classify per `config/routing.yaml`: pure funds-forex / pure funds-banking / pure tax / cross-domain.

2. **Subagents do isolated work.** Every delegation must include a compact task package with enough context. Subagents return evidence, not polished reports.

3. **Retrieve before concluding.** Use RAG or search tools before any legal, tax or compliance conclusion. Start from `sources/` registries before broad web search. Include case-law database searches (see `config/jurisdictions.yaml`).

4. **Validate source currency before analysis.** Run regulatory validity verification after retrieval. Trace single-tier amendment lineage (what prior regulation the current one amended, replaced or repealed).

5. **Verify before shipping.** Run citation verification before synthesis and report archiving.

6. **Chinese output by default.** Keep final answers in Chinese unless the user asks otherwise.

7. **No separate app framework.** Do not invent or maintain a separate backend when project rules, skills and subagents are sufficient.
