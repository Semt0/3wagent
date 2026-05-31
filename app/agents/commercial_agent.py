from app.core.schemas import AgentAnalysis, SourceChunk
from app.llm.chains import run_skill_chain


def analyze_commercial(
    question: str,
    sources: list[SourceChunk],
    issue_profile_text: str = "",
    source_context: str = "",
) -> AgentAnalysis:
    citations = [source for source in sources if source.domain == "commercial"]
    llm_analysis = run_skill_chain(
        "commercial_analysis",
        {
            "question": question,
            "issue_profile": issue_profile_text,
            "sources": source_context,
        },
    )

    return AgentAnalysis(
        domain="commercial",
        conclusion="Preliminary commercial-law analysis should identify entity, contract and license issues.",
        analysis=llm_analysis
        or (
            "Review company formation, directors and shareholders, share transfer, contract validity, "
            "commercial registration, licensing, investment access and baseline regulatory status."
        ),
        citations=citations,
        open_questions=["Confirm entity type, governing law, business activity and license-sensitive areas."],
    )
