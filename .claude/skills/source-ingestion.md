# source-ingestion

Ingest policy sources and attach structured metadata.

## When to use

- Collecting new laws, regulations or guidance into the knowledge base.
- Importing external policy documents for retrieval.
- Updating the source corpus after a regulatory change.

## Steps

1. Identify the source type and jurisdiction.
2. Extract metadata:
   - jurisdiction
   - domain (funds | tax | commercial)
   - source type
   - authority
   - title
   - URL
   - publication date
   - effective date
   - retrieved date
   - language
   - reliability level (S / A / B / C / D)
3. Separate official sources (S, A, B) from professional commentary (C) and public posts (D).
4. Store with metadata attached; do not strip it.

## Output

A source entry with full metadata, ready for retrieval.
