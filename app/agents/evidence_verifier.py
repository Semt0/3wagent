from app.core.schemas import AgentAnalysis
from app.llm.chains import run_skill_chain


def verify_evidence(analyses: list[AgentAnalysis]) -> str:
    if not analyses:
        return "No analysis was generated."

    missing = [analysis.domain for analysis in analyses if not analysis.citations]
    placeholder_only = [
        analysis.domain
        for analysis in analyses
        if analysis.citations and all(source.source_type == "placeholder" for source in analysis.citations)
    ]

    notes: list[str] = []
    if missing:
        notes.append(f"No citations found for: {', '.join(missing)}.")
    if placeholder_only:
        notes.append(f"Only placeholder sources available for: {', '.join(placeholder_only)}.")

    deterministic_note = " ".join(notes) or "Each generated analysis has at least one cited source."
    llm_note = run_skill_chain(
        "citation_verification",
        {
            "question": "Verify whether the generated analyses are adequately supported.",
            "issue_profile": "Evidence verification stage.",
            "sources": _format_analyses_for_verification(analyses),
        },
    )
    return llm_note or deterministic_note


def _format_analyses_for_verification(analyses: list[AgentAnalysis]) -> str:
    blocks: list[str] = []
    for analysis in analyses:
        blocks.append(
            "\n".join(
                [
                    f"Domain: {analysis.domain}",
                    f"Conclusion: {analysis.conclusion}",
                    f"Analysis: {analysis.analysis}",
                    f"Citation count: {len(analysis.citations)}",
                ]
            )
        )
    return "\n\n".join(blocks)
