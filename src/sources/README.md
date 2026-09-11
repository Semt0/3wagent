# Source Registries

This folder contains curated starting points for 3wagent retrieval. The registry is not a complete legal database. It gives the lead agent and `rag-retriever` a trusted first pass before using open web search.

## Entry Schema

Each registry file should include a top-level `jurisdiction` such as `CN`, `US`, `HK`, or `SG`.

Each source entry should include:

- `id`: Stable lowercase identifier.
- `title`: Human-readable source title.
- `authority`: Issuing authority or official database.
- `url`: Canonical URL.
- `domains`: One or more of `funds`, `tax`, `commercial`.
- `subdomains` (optional): Finer-grained labels within a domain. For `funds`: `forex-administration` (SAFE, FX settlement, current/capital account), `aml-kyc` (anti-money laundering, customer due diligence), `sanctions` (OFAC, UN, sectoral sanctions), `payment-licensing`. For `commercial`: `securities-regulation` (securities supervision, overseas issuance/listing and filing rules).
- `reliability`: `S`, `A`, `B`, `C`, or `D`.
- `source_type`: Law, regulation, regulator guidance, tax authority guidance, official FAQ, professional commentary, or public commentary.
- `notes`: Retrieval guidance and limits.

Optional fields for amendment lineage (populated where known):

- `amended_from` (optional): A list of prior regulation `id`s that the current source directly amended, replaced or repealed. Used for single-tier amendment tracing.

Optional fields for time-sensitive sources:

- `publication_date`
- `effective_date`
- `amendment_date`
- `repeal_or_expiry_date`
- `status`
- `retrieved_date`

For Mainland China, foreign exchange administration, SAFE rules, settlement and sale of foreign exchange, capital-account filings and cross-border payment controls belong to the `funds` domain.

## Reliability Rules

The S/A/B/C/D reliability scale is defined in `config/source-levels.yaml` — that file is the single source of truth. Key rules:

- `S`, `A`, `B` sources can support final conclusions.
- `C` and `D` sources can only be used as leads. They must not support final conclusions on their own.
