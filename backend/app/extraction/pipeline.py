"""Extraction pipeline: metadata + deterministic rules (+ optional LLM) ->
evidence validation -> merged, de-duplicated report."""

from __future__ import annotations

from ..models import Claim, ClaimCategory, ExtractionReport, JobDetail
from .deterministic import extract_all
from .llm import LLMExtractor
from .validate import validate_claims

_PRECEDENCE = {"metadata": 0, "rules": 1, "llm": 2}

# Categories reported as "not stated" when nothing verified was found.
REPORTABLE = [
    ClaimCategory.work_arrangement,
    ClaimCategory.job_location,
    ClaimCategory.geographic_restriction,
    ClaimCategory.sponsorship_policy,
    ClaimCategory.relocation_requirement,
    ClaimCategory.employment_type,
    ClaimCategory.technical_requirement,
]


def _merge(claims: list[Claim]) -> list[Claim]:
    """Keep one claim per (category, value, source), preferring rules over llm.

    Metadata and description evidence for the same value are both kept: the
    description quote is usually more informative ("in person 5 days a week").
    """
    best: dict[tuple[str, str], Claim] = {}
    for c in claims:
        key = (c.category.value, c.value.casefold(), c.evidence_source)
        cur = best.get(key)
        if cur is None or _PRECEDENCE[c.extractor] < _PRECEDENCE[cur.extractor]:
            best[key] = c
    order = {id(c): i for i, c in enumerate(claims)}
    return sorted(best.values(), key=lambda c: (REPORTABLE.index(c.category), order[id(c)]))


async def run_extraction(job: JobDetail, llm: LLMExtractor | None) -> ExtractionReport:
    candidates = extract_all(job)
    llm_status = "disabled"
    if llm is not None and llm.enabled:
        llm_claims, llm_status = await llm.extract(job)
        candidates.extend(llm_claims)

    verified, rejected = validate_claims(candidates, job)
    merged = _merge(verified)
    present = {c.category for c in merged}
    unknown = [cat for cat in REPORTABLE if cat not in present]
    desc = job.description_text or ""
    return ExtractionReport(
        claims=merged,
        rejected_claims=rejected,
        unknown_categories=unknown,
        llm_status=llm_status,  # type: ignore[arg-type]
        description_chars=len(desc),
        description_truncated=len(desc) >= 15000,
    )
