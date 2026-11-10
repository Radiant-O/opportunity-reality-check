"""Pydantic models shared by the API, the extractors and the rules engine.

These models are the public contract between the FastAPI backend and the
React frontend (mirrored in ``frontend/src/types.ts``).
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---------------------------------------------------------------------------
# Candidate preferences (never persisted, never logged)
# ---------------------------------------------------------------------------

WorkPreference = Literal["remote", "hybrid", "onsite", "flexible"]
RelocationPreference = Literal["yes", "no", "conditional"]
SponsorshipNeed = Literal["yes", "no", "unsure"]


class CandidatePreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    country: str | None = Field(
        default=None,
        max_length=64,
        description="Current country of residence (free text, e.g. 'Nigeria').",
    )
    work_arrangement: WorkPreference = "flexible"
    relocation: RelocationPreference = "conditional"
    sponsorship: SponsorshipNeed = "unsure"
    skills: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("skills")
    @classmethod
    def _clean_skills(cls, v: list[str]) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for s in v:
            s = s.strip()[:40]
            if s and s.lower() not in seen:
                seen.add(s.lower())
                out.append(s)
        return out

    @field_validator("country")
    @classmethod
    def _clean_country(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None


# ---------------------------------------------------------------------------
# Jobs (normalized from the speedrun API)
# ---------------------------------------------------------------------------


class JobSummary(BaseModel):
    id: str
    title: str
    company: str
    company_url: str | None = None
    location: str | None = None
    workplace_type: Literal["remote", "hybrid", "onsite"] | None = None
    workplace_type_raw: str | None = None
    employment_type: str | None = None
    function: str | None = None
    seniority: str | None = None
    remote: bool = False
    published_at: str | None = None
    url: str = Field(description="Canonical speedrun job URL. Always link users here.")


class JobDetail(JobSummary):
    status: Literal["open", "closed"] = "open"
    apply_url: str | None = None
    apply_kind: Literal["onsite", "external"] | None = None
    comp_summary: str | None = None
    description_text: str | None = None


class JobListResponse(BaseModel):
    jobs: list[JobSummary]
    total: int
    page: int
    total_pages: int
    query: str | None = None
    attribution: str = "Job data from the speedrun talent network public API."


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


class ClaimCategory(str, Enum):
    work_arrangement = "work_arrangement"
    job_location = "job_location"
    geographic_restriction = "geographic_restriction"
    sponsorship_policy = "sponsorship_policy"
    relocation_requirement = "relocation_requirement"
    employment_type = "employment_type"
    technical_requirement = "technical_requirement"


EvidenceSource = Literal[
    "description",
    "metadata.location",
    "metadata.workplace_type",
    "metadata.employment_type",
    "metadata.remote",
]

VerificationStatus = Literal["verified", "rejected"]
Extractor = Literal["metadata", "rules", "llm"]

# Canonical values per category. Free-text categories (job_location,
# geographic_restriction, technical_requirement) are not enumerated.
CANONICAL_VALUES: dict[ClaimCategory, set[str]] = {
    ClaimCategory.work_arrangement: {"remote", "hybrid", "onsite"},
    ClaimCategory.sponsorship_policy: {
        "offered",
        "not_offered",
        "case_by_case",
        "existing_authorization_required",
        "citizenship_required",
    },
    ClaimCategory.relocation_requirement: {
        "required",
        "assistance_offered",
        "not_offered",
    },
    ClaimCategory.employment_type: {
        "full_time",
        "part_time",
        "contract",
        "internship",
        "temporary",
    },
}


class Claim(BaseModel):
    """One factual statement extracted from a job listing.

    Every claim must carry an exact quote from ``evidence_source``. Claims whose
    quote cannot be found in the source are kept in ``rejected_claims`` and are
    never used by the rules engine.
    """

    id: str
    category: ClaimCategory
    value: str = Field(max_length=200)
    evidence_text: str = Field(max_length=600)
    evidence_source: EvidenceSource
    confidence: float = Field(ge=0.0, le=1.0)
    verification_status: VerificationStatus = "verified"
    extractor: Extractor
    rejection_reason: str | None = None


class ExtractionReport(BaseModel):
    claims: list[Claim]
    rejected_claims: list[Claim] = Field(default_factory=list)
    unknown_categories: list[ClaimCategory] = Field(default_factory=list)
    llm_status: Literal["disabled", "ok", "failed", "skipped"] = "disabled"
    description_chars: int = 0
    description_truncated: bool = False


# ---------------------------------------------------------------------------
# Analysis output
# ---------------------------------------------------------------------------

FindingStatus = Literal["agreement", "conflict", "unknown", "caution"]


class Finding(BaseModel):
    rule_id: str
    status: FindingStatus
    title: str
    explanation: str
    evidence_claim_ids: list[str] = Field(default_factory=list)


SectionStatus = Literal["compatible", "conflict", "needs_clarification", "unknown"]


class LocationSection(BaseModel):
    status: SectionStatus
    headline: str
    job_location: str | None
    job_country: str | None
    work_arrangement: Literal["remote", "hybrid", "onsite"] | None
    findings: list[Finding]


AuthorizationLabel = Literal[
    "explicitly_supported",
    "explicitly_restricted",
    "not_specified",
    "needs_clarification",
]


class AuthorizationSection(BaseModel):
    label: AuthorizationLabel
    headline: str
    findings: list[Finding]
    note: str


class SkillMatch(BaseModel):
    skill: str
    evidence_claim_id: str | None = None


class TechnicalSection(BaseModel):
    status: Literal["needs_skills", "assessed", "no_requirements_found"]
    headline: str
    matched: list[SkillMatch] = Field(default_factory=list)
    listed_not_provided: list[SkillMatch] = Field(default_factory=list)
    provided_not_listed: list[str] = Field(default_factory=list)
    note: str


class NextStep(BaseModel):
    id: str
    text: str
    reason: str
    priority: Literal["high", "medium", "low"]


class AnalysisResponse(BaseModel):
    job: JobDetail
    extraction: ExtractionReport
    technical: TechnicalSection
    location: LocationSection
    authorization: AuthorizationSection
    assessment: str
    next_steps: list[NextStep]
    draft_inquiry: str
    disclaimer: str


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(min_length=6, max_length=160)
    preferences: CandidatePreferences = Field(default_factory=CandidatePreferences)


# ---------------------------------------------------------------------------
# Listing clarity (founder-facing)
# ---------------------------------------------------------------------------


class ClarityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str | None = Field(default=None, min_length=6, max_length=160)
    description_text: str | None = Field(default=None, max_length=15000)
    location: str | None = Field(default=None, max_length=200)
    workplace_type: str | None = Field(default=None, max_length=40)
    employment_type: str | None = Field(default=None, max_length=40)


ClarityStatus = Literal["clear", "partial", "missing"]


class ClarityItem(BaseModel):
    dimension: Literal[
        "location",
        "work_arrangement",
        "relocation",
        "sponsorship",
        "employment_type",
    ]
    label: str
    status: ClarityStatus
    detail: str
    evidence_claim_ids: list[str] = Field(default_factory=list)
    suggestion: str | None = None


class ClarityResponse(BaseModel):
    items: list[ClarityItem]
    clear_count: int
    total: int
    extraction: ExtractionReport
    job: JobSummary | None = None
    note: str
