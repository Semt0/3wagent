from app.core.schemas import Domain, IssueProfile, SourceChunk


def retrieve_sources(issue_profile: IssueProfile, query_text: str) -> list[SourceChunk]:
    domains: list[Domain] = [issue_profile.primary_domain, *issue_profile.secondary_domains]
    sources: list[SourceChunk] = []

    for jurisdiction in issue_profile.jurisdictions:
        for domain in domains:
            sources.append(
                SourceChunk(
                    title=f"Placeholder source for {jurisdiction} {domain}",
                    authority="To be connected to official source index",
                    jurisdiction=jurisdiction,
                    domain=domain,
                    text=(
                        "This placeholder should be replaced by hybrid retrieval from official "
                        f"policy sources. Query: {query_text[:160]}"
                    ),
                    reliability="D",
                    source_type="placeholder",
                )
            )

    return sources

