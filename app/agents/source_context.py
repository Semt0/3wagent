from app.core.schemas import IssueProfile, SourceChunk


def format_issue_profile(issue_profile: IssueProfile | None) -> str:
    if issue_profile is None:
        return "No issue profile was provided."

    return "\n".join(
        [
            f"Jurisdictions: {', '.join(issue_profile.jurisdictions)}",
            f"Primary domain: {issue_profile.primary_domain}",
            f"Secondary domains: {', '.join(issue_profile.secondary_domains) or 'none'}",
            f"Transaction type: {issue_profile.transaction_type or 'unknown'}",
            f"Payment type: {issue_profile.payment_type or 'unknown'}",
            f"Routing reason: {issue_profile.reason}",
        ]
    )


def format_sources(sources: list[SourceChunk]) -> str:
    if not sources:
        return "No sources were retrieved."

    blocks: list[str] = []
    for index, source in enumerate(sources, start=1):
        blocks.append(
            "\n".join(
                [
                    f"[{index}] {source.title}",
                    f"Authority: {source.authority}",
                    f"Jurisdiction: {source.jurisdiction}",
                    f"Domain: {source.domain}",
                    f"Reliability: {source.reliability}",
                    f"Source type: {source.source_type}",
                    f"URL: {source.url or 'not available'}",
                    f"Text: {source.text}",
                ]
            )
        )

    return "\n\n".join(blocks)

