"""Listing Clarity Check (founder-facing): which candidate-critical details a
listing communicates clearly. It reports gaps, never assumes a policy."""

from __future__ import annotations

from .geo import infer_country
from .models import ClaimCategory, ClarityItem, ExtractionReport, JobDetail
from .rules import resolve_arrangement


def evaluate_clarity(job: JobDetail, report: ExtractionReport) -> list[ClarityItem]:
    claims = report.claims
    by = lambda cat: [c for c in claims if c.category == cat]  # noqa: E731
    items: list[ClarityItem] = []

    # Location
    loc = by(ClaimCategory.job_location)
    geo = by(ClaimCategory.geographic_restriction)
    arrangement, arr_claims, disagreement = resolve_arrangement(claims)
    if not loc:
        items.append(ClarityItem(dimension="location", label="Location", status="missing",
            detail="No location is given.",
            suggestion="State the office city and country, or for remote roles, the countries you can hire in."))
    elif arrangement == "remote" and not geo:
        items.append(ClarityItem(dimension="location", label="Location", status="partial",
            detail=f"Listed as \"{job.location}\", but eligible countries for remote work aren't stated.",
            evidence_claim_ids=[c.id for c in loc],
            suggestion="Add which countries or time zones you can hire remote employees in."))
    elif arrangement != "remote" and not infer_country(job.location):
        items.append(ClarityItem(dimension="location", label="Location", status="partial",
            detail=f"Listed as \"{job.location}\". The country isn't explicit.",
            evidence_claim_ids=[c.id for c in loc],
            suggestion="Include the country so international candidates can tell where the role is."))
    else:
        items.append(ClarityItem(dimension="location", label="Location", status="clear",
            detail=f"Listed as \"{job.location}\".", evidence_claim_ids=[c.id for c in loc + geo]))

    # Work arrangement
    desc_arr = [c for c in arr_claims if c.extractor != "metadata"]
    if arrangement is None:
        items.append(ClarityItem(dimension="work_arrangement", label="Remote / hybrid / onsite", status="missing",
            detail="The listing doesn't say whether the role is remote, hybrid or onsite.",
            suggestion="State the arrangement explicitly, and for hybrid roles, the expected days in office."))
    elif disagreement:
        items.append(ClarityItem(dimension="work_arrangement", label="Remote / hybrid / onsite", status="partial",
            detail="The workplace label and the description disagree.",
            evidence_claim_ids=[c.id for c in arr_claims],
            suggestion="Make the workplace field and description say the same thing."))
    elif arrangement == "hybrid" and not desc_arr:
        items.append(ClarityItem(dimension="work_arrangement", label="Remote / hybrid / onsite", status="partial",
            detail="Marked hybrid, but the expected office days aren't described.",
            evidence_claim_ids=[c.id for c in arr_claims],
            suggestion="Say how many days per week are in the office."))
    else:
        items.append(ClarityItem(dimension="work_arrangement", label="Remote / hybrid / onsite", status="clear",
            detail=f"Clearly {arrangement}.", evidence_claim_ids=[c.id for c in arr_claims]))

    # Relocation
    reloc = by(ClaimCategory.relocation_requirement)
    if reloc:
        items.append(ClarityItem(dimension="relocation", label="Relocation", status="clear",
            detail="The listing addresses relocation.", evidence_claim_ids=[c.id for c in reloc]))
    elif arrangement == "remote":
        items.append(ClarityItem(dimension="relocation", label="Relocation", status="clear",
            detail="Remote role, so relocation is less relevant (not stated).",
            suggestion=None))
    else:
        items.append(ClarityItem(dimension="relocation", label="Relocation", status="missing",
            detail="Nothing about relocation expectations or support.",
            suggestion="Say whether candidates must already live nearby and whether relocation support is offered."))

    # Sponsorship
    sp = by(ClaimCategory.sponsorship_policy)
    vals = {c.value for c in sp}
    if vals & {"offered", "not_offered", "citizenship_required"} and not ({"offered"} & vals and vals & {"not_offered", "citizenship_required"}):
        items.append(ClarityItem(dimension="sponsorship", label="Visa sponsorship", status="clear",
            detail="The listing states a sponsorship position.", evidence_claim_ids=[c.id for c in sp]))
    elif sp:
        items.append(ClarityItem(dimension="sponsorship", label="Visa sponsorship", status="partial",
            detail="Sponsorship is mentioned, but the position is ambiguous or conditional.",
            evidence_claim_ids=[c.id for c in sp],
            suggestion="State plainly whether you can sponsor visas for this role."))
    else:
        items.append(ClarityItem(dimension="sponsorship", label="Visa sponsorship", status="missing",
            detail="Sponsorship isn't mentioned. International candidates can't tell if they're eligible.",
            suggestion="Add one sentence: \"We can / cannot sponsor visas for this role.\""))

    # Employment type
    et = by(ClaimCategory.employment_type)
    if et:
        items.append(ClarityItem(dimension="employment_type", label="Employment type", status="clear",
            detail=f"Stated as {', '.join(sorted({c.value.replace('_', '-') for c in et}))}.",
            evidence_claim_ids=[c.id for c in et]))
    else:
        items.append(ClarityItem(dimension="employment_type", label="Employment type", status="missing",
            detail="Full-time, part-time or contract isn't stated.",
            suggestion="State the employment type."))
    return items
