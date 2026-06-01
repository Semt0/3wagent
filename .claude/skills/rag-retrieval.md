# rag-retrieval

Retrieve policy sources with jurisdiction, domain and reliability metadata.

## When to use

- Before writing any legal, tax or compliance conclusion.
- When the user question references a specific jurisdiction or domain.
- After the `source-ingestion` skill when building a source pack.

## Steps

1. Apply jurisdiction filters first (US, Hong Kong, Singapore).
2. Apply domain filters second (funds, tax, commercial).
3. Query with the user's issue profile.
4. Score and filter by reliability:
   - Prefer S and A sources.
   - Use B sources as supporting evidence.
   - Use C and D sources only as leads.
5. Record for each result: title, authority, URL, jurisdiction, domain, reliability level, applicable point.
6. If official support is missing, flag the conclusion as preliminary.

## Output

Concise source packs with metadata. Do not write the final report.
