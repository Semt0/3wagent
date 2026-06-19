# citation-verification

Verify that policy conclusions are supported by correct jurisdiction and domain sources.

## When to use

- Before finalizing every policy report.
- After specialist subagents return their analysis.
- Whenever a conclusion cites a source.

## Steps

1. Check that every material conclusion has at least one cited source.
2. Verify the cited source belongs to the correct jurisdiction.
3. Verify the cited source actually supports the exact claim.
4. Confirm C and D sources are not treated as legal authority (see `config/source-levels.yaml`).
5. Confirm sources with unresolved regulatory validity warnings are not treated as reliable authority.
6. Flag missing, weak or placeholder evidence explicitly.

## Reliability labels

- Supported by official authority
- Likely but requiring manual review
- Secondary-source lead only
- No reliable source found

## Output

Verification findings and required fixes. Do not rewrite the whole report.
