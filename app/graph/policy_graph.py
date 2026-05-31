from app.agents.answer_writer import write_answer
from app.agents.commercial_agent import analyze_commercial
from app.agents.evidence_verifier import verify_evidence
from app.agents.funds_agent import analyze_funds
from app.agents.source_context import format_issue_profile, format_sources
from app.agents.tax_agent import analyze_tax
from app.core.schemas import AgentAnalysis, IssueProfile, SourceChunk, UserQuery
from app.retrieval.retriever import retrieve_sources
from app.router.issue_router import route_issue


def run_policy_workflow(question: str, file_text: str | None = None) -> str:
    query = UserQuery(question=question, file_text=file_text)
    issue_profile = route_issue(query)
    sources = retrieve_sources(issue_profile, question)
    analyses = _run_specialists(question, issue_profile, sources)
    reliability_note = verify_evidence(analyses)
    return write_answer(issue_profile, analyses, reliability_note)


def _run_specialists(
    question: str,
    issue_profile: IssueProfile,
    sources: list[SourceChunk],
) -> list[AgentAnalysis]:
    domains = [issue_profile.primary_domain, *issue_profile.secondary_domains]
    analyses: list[AgentAnalysis] = []
    issue_profile_text = format_issue_profile(issue_profile)
    source_context = format_sources(sources)

    if "funds" in domains:
        analyses.append(analyze_funds(question, sources, issue_profile_text, source_context))
    if "tax" in domains:
        analyses.append(analyze_tax(question, sources, issue_profile_text, source_context))
    if "commercial" in domains:
        analyses.append(analyze_commercial(question, sources, issue_profile_text, source_context))

    return analyses
