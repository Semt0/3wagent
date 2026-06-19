# source-ingestion

Ingest policy sources and attach structured metadata.

## When to use

- Collecting new laws, regulations or guidance into the knowledge base.
- Importing external policy documents for retrieval.
- Updating the source corpus after a regulatory change.

## Steps

1. Identify the source type and jurisdiction.
2. Extract metadata per `sources/README.md` schema:
   - stable id
   - jurisdiction
   - domain (funds | tax | commercial)
   - subdomains (see `config/routing.yaml` for valid values)
   - source type
   - authority
   - title
   - URL
   - publication date, effective date, amendment date, repeal or expiry date, retrieved date
   - current status
   - language
   - reliability level (S / A / B / C / D — see `config/source-levels.yaml`)
3. Separate official sources (S, A, B) from professional commentary (C) and public posts (D) per `config/source-levels.yaml`.
4. Add curated reusable sources to the matching registry file (paths in `config/jurisdictions.yaml`).
5. Store with metadata attached; do not strip it.

## Output

A source entry with full metadata, ready for retrieval.
