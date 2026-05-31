import re

from app.core.config import settings
from app.core.schemas import Domain, IssueProfile, Jurisdiction, UserQuery
from app.router.rules import (
    COMMERCIAL_KEYWORDS,
    FUNDS_KEYWORDS,
    JURISDICTION_KEYWORDS,
    PAYMENT_TYPE_KEYWORDS,
    TAX_KEYWORDS,
    TRANSACTION_TYPE_KEYWORDS,
)


def route_issue(query: UserQuery) -> IssueProfile:
    text = f"{query.question}\n{query.file_text or ''}".lower()
    scores: dict[Domain, int] = {
        "funds": _score_keywords(text, FUNDS_KEYWORDS),
        "tax": _score_keywords(text, TAX_KEYWORDS),
        "commercial": _score_keywords(text, COMMERCIAL_KEYWORDS),
    }

    primary_domain = _select_primary_domain(scores)

    secondary_domains = [
        domain for domain, score in scores.items() if domain != primary_domain and score > 0
    ]

    jurisdictions = query.preferred_jurisdictions or _detect_jurisdictions(text)

    return IssueProfile(
        jurisdictions=jurisdictions,
        primary_domain=primary_domain,
        secondary_domains=secondary_domains,
        transaction_type=_detect_labels(text, TRANSACTION_TYPE_KEYWORDS),
        payment_type=_detect_labels(text, PAYMENT_TYPE_KEYWORDS),
        reason=f"Routing scores: {scores}",
    )


def _keyword_matches(keyword: str, text: str) -> bool:
    """Match a keyword against already-lowercased text.

    Latin/ASCII keywords are matched on word boundaries so that short tokens like
    "us" or "vat" do not falsely fire inside "business" or "private". CJK keywords
    have no word boundaries, so plain substring matching is correct for them.
    """
    keyword = keyword.lower()
    if keyword.isascii():
        return re.search(rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])", text) is not None
    return keyword in text


def _score_keywords(text: str, keywords: list[str]) -> int:
    return sum(1 for keyword in keywords if _keyword_matches(keyword, text))


def _detect_labels(text: str, mapping: dict[str, list[str]]) -> str | None:
    labels = [
        label
        for label, keywords in mapping.items()
        if any(_keyword_matches(keyword, text) for keyword in keywords)
    ]
    return "、".join(labels) or None


def _select_primary_domain(scores: dict[Domain, int]) -> Domain:
    if max(scores.values()) == 0:
        return "funds"

    if scores["tax"] > 0 and scores["tax"] >= scores["funds"]:
        return "tax"

    if scores["funds"] > 0 and scores["funds"] >= scores["commercial"]:
        return "funds"

    return max(scores, key=scores.get)


def _detect_jurisdictions(text: str) -> list[Jurisdiction]:
    detected: list[Jurisdiction] = []
    for jurisdiction, keywords in JURISDICTION_KEYWORDS.items():
        if any(_keyword_matches(keyword, text) for keyword in keywords):
            detected.append(jurisdiction)  # type: ignore[arg-type]

    return detected or list(settings.default_jurisdictions)  # type: ignore[return-value]
