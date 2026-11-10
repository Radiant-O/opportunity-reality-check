"""Orchestrates: listing -> extraction -> validation -> rules -> explanation."""

from __future__ import annotations

from .extraction.llm import LLMExtractor
from .extraction.pipeline import run_extraction
from .models import AnalysisResponse, CandidatePreferences, ExtractionReport, JobDetail
from .recommend import build_assessment, build_draft_inquiry, build_next_steps
from .rules import evaluate_authorization, evaluate_location, evaluate_technical

DISCLAIMER = (
    "Opportunity Reality Check is an independent demo, not affiliated with a16z or speedrun. "
    "Results are generated automatically from the public listing and may be incomplete. "
    "They are informational only, not legal or immigration advice, and not a hiring decision. "
    "Always confirm details with the employer."
)


async def analyze(
    job: JobDetail,
    prefs: CandidatePreferences,
    llm: LLMExtractor | None,
    report: ExtractionReport | None = None,
) -> AnalysisResponse:
    """Extraction is preference-independent, so callers may pass a cached report."""
    if report is None:
        report = await run_extraction(job, llm)
    claims = report.claims
    location = evaluate_location(prefs, job, claims)
    authorization = evaluate_authorization(prefs, job, claims)
    technical = evaluate_technical(prefs, claims)
    return AnalysisResponse(
        job=job,
        extraction=report,
        technical=technical,
        location=location,
        authorization=authorization,
        assessment=build_assessment(prefs, location, authorization),
        next_steps=build_next_steps(prefs, job, location, authorization, technical),
        draft_inquiry=build_draft_inquiry(prefs, job, location, authorization),
        disclaimer=DISCLAIMER,
    )
