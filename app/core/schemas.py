from typing import Literal

from pydantic import BaseModel, Field

Domain = Literal["funds", "tax", "commercial"]
Jurisdiction = Literal["US", "HK", "SG"]
Reliability = Literal["S", "A", "B", "C", "D"]


class UserQuery(BaseModel):
    question: str
    file_text: str | None = None
    preferred_jurisdictions: list[Jurisdiction] = Field(default_factory=list)


class IssueProfile(BaseModel):
    jurisdictions: list[Jurisdiction]
    primary_domain: Domain
    secondary_domains: list[Domain] = Field(default_factory=list)
    transaction_type: str | None = None
    payment_type: str | None = None
    reason: str


class SourceChunk(BaseModel):
    title: str
    authority: str
    jurisdiction: Jurisdiction
    domain: Domain
    text: str
    reliability: Reliability = "D"
    source_type: str = "unknown"
    url: str | None = None
    applicability: str | None = None


class AgentAnalysis(BaseModel):
    domain: Domain
    conclusion: str
    analysis: str
    citations: list[SourceChunk] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)


class FinalReport(BaseModel):
    issue_profile: IssueProfile
    summary: str
    funds_analysis: str | None = None
    tax_analysis: str | None = None
    commercial_analysis: str | None = None
    citations: list[SourceChunk] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    reliability_note: str

