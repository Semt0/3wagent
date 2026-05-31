from app.core.schemas import AgentAnalysis, IssueProfile, SourceChunk


def write_answer(
    issue_profile: IssueProfile,
    analyses: list[AgentAnalysis],
    reliability_note: str,
) -> str:
    analysis_by_domain = {analysis.domain: analysis for analysis in analyses}
    citations = _collect_citations(analyses)

    return "\n".join(
        [
            "【问题识别】",
            f"法域：{', '.join(issue_profile.jurisdictions)}",
            f"主要领域：{issue_profile.primary_domain}",
            f"辅助领域：{', '.join(issue_profile.secondary_domains) or '无'}",
            f"付款/交易性质：{_nature_line(issue_profile)}",
            "",
            "【简要结论】",
            _summary_block(issue_profile, analyses),
            "",
            "【资金流动 / 银行合规 / AML / 制裁分析】",
            _domain_text(analysis_by_domain.get("funds")),
            "",
            "【税务分析】",
            _domain_text(analysis_by_domain.get("tax")),
            "",
            "【民商法规分析】",
            _domain_text(analysis_by_domain.get("commercial")),
            "",
            "【法规与政策索引】",
            _citation_text(citations),
            "",
            "【实务文件清单】",
            "- 合同、发票或付款通知",
            "- 董事会/股东决议（如适用）",
            "- 资金来源说明和交易背景材料",
            "- 税务居民证明或扣缴税文件（如适用）",
            "- 银行 KYC / AML 问询材料",
            "",
            "【风险提示】",
            "- 当前版本仍使用占位检索，正式结论需要接入官方资料库后复核。",
            "- 公众号或专业文章只能作为线索，不能作为最终法律依据。",
            "",
            "【结论可靠性】",
            reliability_note,
        ]
    )


def _nature_line(issue_profile: IssueProfile) -> str:
    parts = [part for part in (issue_profile.transaction_type, issue_profile.payment_type) if part]
    return " / ".join(parts) if parts else "待确认"


def _summary_block(issue_profile: IssueProfile, analyses: list[AgentAnalysis]) -> str:
    if not analyses:
        return "1. 暂未生成分析结论。"

    # Primary domain first, remaining analyses keep their original order.
    ordered = sorted(analyses, key=lambda a: a.domain != issue_profile.primary_domain)
    return "\n".join(f"{index}. {analysis.conclusion}" for index, analysis in enumerate(ordered, start=1))


def _domain_text(analysis: AgentAnalysis | None) -> str:
    if analysis is None:
        return "本问题未将该领域列为重点分析。"
    open_questions = "\n".join(f"- 待确认：{item}" for item in analysis.open_questions)
    return f"{analysis.conclusion}\n{analysis.analysis}\n{open_questions}".strip()


def _collect_citations(analyses: list[AgentAnalysis]) -> list[SourceChunk]:
    """Aggregate the sources actually cited by each specialist, de-duplicated."""
    seen: set[tuple] = set()
    citations: list[SourceChunk] = []
    for analysis in analyses:
        for source in analysis.citations:
            key = (source.title, source.jurisdiction, source.domain, source.url)
            if key not in seen:
                seen.add(key)
                citations.append(source)
    return citations


def _citation_text(citations: list[SourceChunk]) -> str:
    if not citations:
        return "未找到可引用资料。"

    lines: list[str] = []
    for index, citation in enumerate(citations, start=1):
        lines.extend(
            [
                f"{index}. 名称：{citation.title}",
                f"   机构：{citation.authority}",
                f"   法域：{citation.jurisdiction}",
                f"   链接：{citation.url or '待补充'}",
                f"   适用点：{citation.applicability or '待补充'}",
                f"   来源等级：{citation.reliability}",
            ]
        )
    return "\n".join(lines)
