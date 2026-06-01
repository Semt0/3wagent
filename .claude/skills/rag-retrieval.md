# rag-retrieval

Retrieve policy sources with jurisdiction, domain and reliability metadata.

## When to use

- Before writing any legal, tax or compliance conclusion.
- When the user question references a specific jurisdiction or domain.
- After the `source-ingestion` skill when building a source pack.

## Steps

1. Apply jurisdiction filters first (US, Hong Kong, Singapore).
2. Apply domain filters second (funds, tax, commercial).
3. Read matching registry files under `sources/`:
   - `sources/us.yaml`
   - `sources/hk.yaml`
   - `sources/sg.yaml`
4. Use `templates/retrieval-task.md` to normalize incomplete retrieval requests.
5. Query with the user's issue profile.
6. Score and filter by reliability:
   - Prefer S and A sources.
   - Use B sources as supporting evidence.
   - Use C and D sources only as leads.
7. Record for each result: source id, title, authority, URL, jurisdiction, domain, reliability level, applicable point.
8. If official support is missing, flag the conclusion as preliminary.

## Output

Concise source packs with metadata. Do not write the final report.
