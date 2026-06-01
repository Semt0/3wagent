# regulatory-validity-verification

Verify whether policy sources are current and applicable to the relevant time period.

## When to use

- After `rag-retrieval` returns a source pack.
- Before specialist subagents rely on laws, regulations, notices, guidance or official cases.
- Whenever a conclusion depends on an effective date, transaction date, tax year, filing date or historical version.
- Especially for Mainland China SAFE, tax, State Council and national legal database sources.

## Steps

1. Identify the relevant date:
   - transaction date
   - payment date
   - tax year
   - filing or registration date
   - user's requested "as of" date
   - current retrieval date if no date is provided
2. For each source, record:
   - source id
   - title
   - authority
   - URL
   - publication date
   - effective date
   - amendment date
   - repeal or expiry date
   - retrieved date
   - current status
3. Check official status indicators, replacement notices, amendment notes and version pages.
4. Distinguish binding authority from navigation pages, news, interpretations and case materials.
5. Flag contradictions between old and new sources.
6. If validity cannot be confirmed from official materials, require manual review.

## Validity Labels

- Currently effective
- Likely effective but requiring manual review
- Historical version / replaced
- Repealed / should not be relied on
- Unable to confirm validity

## Output

Return a concise table:

```text
Source | Publication date | Effective date | Current status | Applicable to relevant date | Replacement / amendment | Notes
```

Do not rewrite the final report. Return required fixes and warnings for the Lead Policy Agent.
