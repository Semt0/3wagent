from app.core.schemas import AgentAnalysis, SourceChunk
from app.llm.chains import run_skill_chain


def analyze_funds(
    question: str,
    sources: list[SourceChunk],
    issue_profile_text: str = "",
    source_context: str = "",
) -> AgentAnalysis:
    citations = [source for source in sources if source.domain == "funds"]
    llm_analysis = run_skill_chain(
        "funds_analysis",
        {
            "question": question,
            "issue_profile": issue_profile_text,
            "sources": source_context,
        },
    )

    return AgentAnalysis(
        domain="funds",
        conclusion="Preliminary funds-compliance analysis requires official-source retrieval.",
        analysis=llm_analysis
        or (
            "Review whether the matter involves cross-border payment, bank KYC, AML/CFT, "
            "source-of-funds review, sanctions screening, payment licensing or reporting duties. "
            "US, Hong Kong and Singapore generally do not operate broad China-style foreign "
            "exchange approval regimes, so practical risk often sits with banks and regulators."
        ),
        citations=citations,
        open_questions=["Confirm transaction parties, payment route, amount, currency and bank request."],
    )
