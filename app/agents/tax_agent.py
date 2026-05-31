from app.core.schemas import AgentAnalysis, SourceChunk
from app.llm.chains import run_skill_chain


def analyze_tax(
    question: str,
    sources: list[SourceChunk],
    issue_profile_text: str = "",
    source_context: str = "",
) -> AgentAnalysis:
    citations = [source for source in sources if source.domain == "tax"]
    llm_analysis = run_skill_chain(
        "tax_analysis",
        {
            "question": question,
            "issue_profile": issue_profile_text,
            "sources": source_context,
        },
    )

    return AgentAnalysis(
        domain="tax",
        conclusion="Preliminary tax analysis depends on payment characterization and tax residency.",
        analysis=llm_analysis
        or (
            "Classify the payment as dividend, interest, royalty, service fee, capital gain, "
            "employment income or another income type. Then check source rules, withholding, "
            "filing obligations, indirect tax and treaty relief for each relevant jurisdiction."
        ),
        citations=citations,
        open_questions=["Confirm income type, payer/payee tax residency and whether a treaty applies."],
    )
