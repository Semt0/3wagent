# Source Registries

This folder contains curated starting points for 3wagent retrieval. The registry is not a complete legal database. It gives the lead agent and `rag-retriever` a trusted first pass before using open web search.

## Entry Schema

Each source entry should include:

- `id`: Stable lowercase identifier.
- `title`: Human-readable source title.
- `authority`: Issuing authority or official database.
- `url`: Canonical URL.
- `domains`: One or more of `funds`, `tax`, `commercial`.
- `reliability`: `S`, `A`, `B`, `C`, or `D`.
- `source_type`: Law, regulation, regulator guidance, tax authority guidance, official FAQ, professional commentary, or public commentary.
- `notes`: Retrieval guidance and limits.

## Reliability Rules

- `S`: Laws, statutes, regulations and official legal databases.
- `A`: Regulator guidance, tax authority guidance and official FAQs.
- `B`: Official circulars, announcements, cases and formal notices.
- `C`: Law firm, accounting firm, bank or professional institution briefings.
- `D`: Public account posts, media articles and individual commentary.

Use `C` and `D` entries only as leads. They must not support final conclusions on their own.
