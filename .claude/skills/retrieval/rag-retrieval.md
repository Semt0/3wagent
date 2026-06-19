# rag-retrieval

Retrieve policy sources with jurisdiction, domain and reliability metadata.

## When to use

- Before writing any legal, tax or compliance conclusion.
- When the user question references a specific jurisdiction or domain.
- After the `source-ingestion` skill when building a source pack.

## Steps

1. Apply jurisdiction filters per `config/jurisdictions.yaml`.
2. Apply domain and classification filters per `config/routing.yaml` — sub-domain keywords and classification rules are defined there.
3. Read matching registry files under `sources/` (paths listed in `config/jurisdictions.yaml`).
4. Use `templates/retrieval-task.md` to normalize incomplete retrieval requests.
5. Query with the user's issue profile.
6. Score and filter by reliability per `config/source-levels.yaml`:
   - Prefer S and A sources.
   - Use B sources as supporting evidence.
   - Use C and D sources only as leads (cannot support final conclusions).
7. **Search case-law databases** per jurisdiction — database URLs and notes are in `config/jurisdictions.yaml`. For each case: record case number/name, court, key holdings, quoted excerpt if accessible, and access limitations.
8. Record for each regulatory result: source id, title, authority, URL, jurisdiction, domain, sub-domain, reliability level, applicable point and available date/status metadata.
9. **Build a numbered list of all involved currently-effective regulations** with jurisdiction, domain, issuing authority and current status. This is the priority output (see `config/output-contract.yaml`).
10. Note visible amendment, replacement or repeal relationships (single-tier only) as leads for the validity verifier.
11. If official support is missing, flag the conclusion as preliminary.

## Output

Concise source packs with metadata. Include:
- Regulatory source pack (with sub-domain labels where applicable)
- Case-law search results (with quoted excerpts or access limitations)
- **Numbered list of involved currently-effective regulations (priority)**
- Amendment lineage leads (single-tier)

Do not write the final report.
