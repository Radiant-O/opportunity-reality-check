"""Transparent, deterministic compatibility rules.

Inputs: candidate preferences + *verified* claims only.
Outputs: per-section findings with rule ids, statuses and claim references.

The rules never decide legal eligibility. They report agreement, conflict,
unknown or caution relative to what the listing explicitly states. Every rule
id is documented in docs/RULES.md.
"""

from __future__ import annotations

import re

from .geo import canonical_country, infer_country, region_includes
from .models import (
    AuthorizationSection,
    CandidatePreferences,
    Claim,
    ClaimCategory,
    Finding,
    JobDetail,
    LocationSection,
    SkillMatch,
    TechnicalSection,
)

ARRANGEMENT_LABEL = {"remote": "Remote", "hybrid": "Hybrid", "onsite": "Onsite"}


def _by_cat(claims: list[Claim], cat: ClaimCategory) -> list[Claim]:
    return [c for c in claims if c.category == cat]


# ---------------------------------------------------------------------------
# Work arrangement resolution
# ---------------------------------------------------------------------------


def resolve_arrangement(claims: list[Claim]) -> tuple[str | None, list[Claim], bool]:
    """Return (effective arrangement, supporting claims, disagreement flag).

    Description statements are more specific than the board's workplace label,
    so they win; disagreement between sources is flagged for the candidate.
    """
    wa = _by_cat(claims, ClaimCategory.work_arrangement)
    meta = [c for c in wa if c.extractor == "metadata"]
    desc = [c for c in wa if c.extractor != "metadata"]
    desc_values = {c.value for c in desc}
    meta_values = {c.value for c in meta}

    if desc_values:
        # Most restrictive explicit statement wins: onsite > hybrid > remote.
        for v in ("onsite", "hybrid", "remote"):
            if v in desc_values:
                effective = v
                break
        support = [c for c in desc if c.value == effective] + [c for c in meta if c.value == effective]
        disagreement = bool(meta_values) and effective not in meta_values
        if disagreement:
            support += meta
        return effective, support, disagreement
    if meta:
        return meta[0].value, meta[:1], False
    return None, [], False


# ---------------------------------------------------------------------------
# Location & work arrangement
# ---------------------------------------------------------------------------


def evaluate_location(prefs: CandidatePreferences, job: JobDetail, claims: list[Claim]) -> LocationSection:
    findings: list[Finding] = []
    arrangement, arr_claims, disagreement = resolve_arrangement(claims)
    arr_ids = [c.id for c in arr_claims]
    loc_claims = _by_cat(claims, ClaimCategory.job_location)
    loc_ids = [c.id for c in loc_claims]
    job_country = infer_country(job.location)
    # Only recognised countries are compared; free text we can't map is reported as unknown.
    cand_country = canonical_country(prefs.country)
    unrecognised_country = bool(prefs.country) and cand_country is None
    if unrecognised_country:
        findings.append(Finding(
            rule_id="L2_COUNTRY_UNRECOGNISED", status="unknown",
            title=f"We couldn't match \"{prefs.country}\" to a country",
            explanation="Location comparisons are skipped rather than guessed. Try the country's English name.",
        ))
    geo = _by_cat(claims, ClaimCategory.geographic_restriction)
    region_claims = [c for c in geo if not c.value.startswith("Time zone")]
    tz_claims = [c for c in geo if c.value.startswith("Time zone")]
    reloc = _by_cat(claims, ClaimCategory.relocation_requirement)

    # L0: sources disagree
    if disagreement:
        findings.append(Finding(
            rule_id="L0_SOURCE_DISAGREEMENT", status="caution",
            title="The listing's label and description disagree",
            explanation=(
                f"The board labels this role differently from what the description says. "
                f"We use the description ({ARRANGEMENT_LABEL[arrangement or 'onsite']}) because it is more specific; confirm with the employer."
            ),
            evidence_claim_ids=arr_ids,
        ))

    # L1: work-arrangement preference
    pref = prefs.work_arrangement
    if arrangement is None:
        findings.append(Finding(
            rule_id="L1_ARRANGEMENT_UNKNOWN", status="unknown",
            title="Work arrangement not stated",
            explanation="The listing doesn't say whether the role is remote, hybrid or onsite.",
        ))
    elif pref == "flexible" or pref == arrangement:
        findings.append(Finding(
            rule_id="L1_ARRANGEMENT_MATCH", status="agreement",
            title=f"{ARRANGEMENT_LABEL[arrangement]} role fits your preference",
            explanation=f"The listing states {'an' if arrangement == 'onsite' else 'a'} {arrangement} arrangement, and you're open to it.",
            evidence_claim_ids=arr_ids,
        ))
    elif pref == "remote" and arrangement in ("onsite", "hybrid"):
        detail = "requires regular onsite attendance" if arrangement == "hybrid" else "requires working onsite"
        findings.append(Finding(
            rule_id="L1_ARRANGEMENT_CONFLICT", status="conflict",
            title="Work-arrangement conflict",
            explanation=f"You want remote work, but the listing {detail}.",
            evidence_claim_ids=arr_ids,
        ))
    elif pref == "hybrid" and arrangement == "onsite":
        findings.append(Finding(
            rule_id="L1_ARRANGEMENT_PARTIAL", status="caution",
            title="More office time than you prefer",
            explanation="You prefer hybrid, but the listing describes an onsite role.",
            evidence_claim_ids=arr_ids,
        ))
    else:  # pref onsite/hybrid, job remote; or pref onsite, job hybrid
        findings.append(Finding(
            rule_id="L1_ARRANGEMENT_DIFFERENT", status="caution",
            title=f"Role is {arrangement}, you preferred {pref}",
            explanation="Not a blocker, but the day-to-day setup differs from what you asked for.",
            evidence_claim_ids=arr_ids,
        ))

    # L2: physical location vs residence (onsite / hybrid)
    if arrangement in ("onsite", "hybrid"):
        if not job.location:
            findings.append(Finding(
                rule_id="L2_LOCATION_UNKNOWN", status="unknown",
                title="Office location not listed",
                explanation="The role needs office attendance, but the listing doesn't say where.",
            ))
        elif unrecognised_country:
            pass  # already reported as L2_COUNTRY_UNRECOGNISED
        elif not cand_country:
            findings.append(Finding(
                rule_id="L2_COUNTRY_MISSING", status="unknown",
                title="Add your country to check location fit",
                explanation=f"The role is based in {job.location}. Tell us where you live to compare.",
                evidence_claim_ids=loc_ids,
            ))
        elif not job_country:
            findings.append(Finding(
                rule_id="L2_JOB_COUNTRY_UNKNOWN", status="unknown",
                title="Couldn't determine the office's country",
                explanation=f"The listed location is \"{job.location}\". Check whether it is in your country.",
                evidence_claim_ids=loc_ids,
            ))
        elif job_country == cand_country:
            findings.append(Finding(
                rule_id="L2_SAME_COUNTRY", status="agreement",
                title=f"Office is in your country ({job_country})",
                explanation=f"The role is based in {job.location}. You may still need to live within commuting distance.",
                evidence_claim_ids=loc_ids,
            ))
        else:
            if prefs.relocation == "no":
                findings.append(Finding(
                    rule_id="L2_RELOCATION_CONFLICT", status="conflict",
                    title=f"Would require relocating to {job_country}",
                    explanation=(
                        f"The role needs {arrangement} attendance in {job.location}, and you're not open to relocation."
                    ),
                    evidence_claim_ids=loc_ids + arr_ids,
                ))
            else:
                qual = "you're open to relocating" if prefs.relocation == "yes" else "you'd consider relocating"
                findings.append(Finding(
                    rule_id="L2_RELOCATION_NEEDED", status="caution",
                    title=f"Relocation to {job_country} would be needed",
                    explanation=(
                        f"The role needs {arrangement} attendance in {job.location} and {qual}. "
                        "Whether you can legally work there is a separate question (see work authorization)."
                    ),
                    evidence_claim_ids=loc_ids + arr_ids,
                ))

    # L3: remote geography
    if arrangement == "remote":
        if region_claims:
            decided = []
            for c in region_claims:
                inc = region_includes(c.value, cand_country) if cand_country else None
                decided.append((c, inc))
            if not cand_country:
                findings.append(Finding(
                    rule_id="L3_REMOTE_REGION_COUNTRY_MISSING", status="unknown",
                    title=f"Remote within {', '.join(c.value for c in region_claims)}",
                    explanation="Add your country to check whether you're inside the stated region.",
                    evidence_claim_ids=[c.id for c in region_claims],
                ))
            elif any(inc is True for _, inc in decided):
                ok = [c for c, inc in decided if inc is True]
                findings.append(Finding(
                    rule_id="L3_REMOTE_REGION_MATCH", status="agreement",
                    title=f"Remote region includes {cand_country}",
                    explanation=f"The listing limits remote work to {', '.join(c.value for c in ok)}.",
                    evidence_claim_ids=[c.id for c in ok],
                ))
            elif all(inc is False for _, inc in decided):
                findings.append(Finding(
                    rule_id="L3_REMOTE_REGION_CONFLICT", status="conflict",
                    title="Remote, but restricted to another region",
                    explanation=(
                        f"The listing limits remote work to {', '.join(c.value for c in region_claims)}, "
                        f"which doesn't include {cand_country}."
                    ),
                    evidence_claim_ids=[c.id for c in region_claims],
                ))
            else:
                findings.append(Finding(
                    rule_id="L3_REMOTE_REGION_UNCLEAR", status="caution",
                    title="Remote with a location limit we can't interpret",
                    explanation="Read the quoted restriction and confirm whether your country qualifies.",
                    evidence_claim_ids=[c.id for c in region_claims],
                ))
        else:
            findings.append(Finding(
                rule_id="L3_REMOTE_COUNTRIES_UNSPECIFIED", status="unknown",
                title="Remote, but eligible countries aren't stated",
                explanation=(
                    "Many remote roles only hire in specific countries for payroll and tax reasons. "
                    "The listing doesn't say which countries qualify."
                ),
                evidence_claim_ids=arr_ids,
            ))
    # Region limits on non-remote roles are still worth showing.
    elif region_claims and cand_country:
        for c in region_claims:
            if region_includes(c.value, cand_country) is False:
                findings.append(Finding(
                    rule_id="L3_LOCATION_REQUIREMENT", status="caution",
                    title=f"Candidates must be located in {c.value}",
                    explanation="You'd need to be based there to take this role.",
                    evidence_claim_ids=[c.id],
                ))

    # L4: time zone
    if tz_claims:
        findings.append(Finding(
            rule_id="L4_TIMEZONE", status="caution",
            title="Working-hours / time-zone requirement",
            explanation="The listing asks for specific working hours or time zones. Check that they work from where you live.",
            evidence_claim_ids=[c.id for c in tz_claims],
        ))

    # L5: relocation statements
    reloc_values = {c.value: c for c in reloc}
    if "required" in reloc_values:
        c = reloc_values["required"]
        if prefs.relocation == "no":
            findings.append(Finding(
                rule_id="L5_RELOCATION_REQUIRED_CONFLICT", status="conflict",
                title="Listing requires relocation",
                explanation="The listing explicitly expects relocation, and you're not open to it.",
                evidence_claim_ids=[c.id],
            ))
        else:
            findings.append(Finding(
                rule_id="L5_RELOCATION_REQUIRED", status="caution",
                title="Listing requires relocation",
                explanation="The listing explicitly expects you to relocate.",
                evidence_claim_ids=[c.id],
            ))
    if "assistance_offered" in reloc_values:
        findings.append(Finding(
            rule_id="L5_RELOCATION_ASSISTANCE", status="agreement",
            title="Relocation assistance is mentioned",
            explanation="The listing says the company helps with relocation. Ask whether this covers international moves.",
            evidence_claim_ids=[reloc_values["assistance_offered"].id],
        ))
    if "not_offered" in reloc_values:
        findings.append(Finding(
            rule_id="L5_RELOCATION_NOT_OFFERED", status="caution",
            title="No relocation support",
            explanation="The listing says relocation support is not provided.",
            evidence_claim_ids=[reloc_values["not_offered"].id],
        ))

    statuses = {f.status for f in findings}
    if "conflict" in statuses:
        status = "conflict"
    elif arrangement is None and not job.location:
        status = "unknown"
    elif statuses & {"unknown", "caution"}:
        status = "needs_clarification"
    else:
        status = "compatible"

    headline = _location_headline(job, arrangement, status)
    return LocationSection(
        status=status,  # type: ignore[arg-type]
        headline=headline,
        job_location=job.location,
        job_country=job_country,
        work_arrangement=arrangement,  # type: ignore[arg-type]
        findings=findings,
    )


def _location_headline(job: JobDetail, arrangement: str | None, status: str) -> str:
    where = job.location or "an unlisted location"
    if arrangement is None:
        base = f"Listed in {where}; work arrangement not stated."
    elif arrangement == "remote":
        base = f"Remote role (listed: {where})."
    else:
        base = f"{ARRANGEMENT_LABEL[arrangement]} role in {where}."
    tail = {
        "conflict": " At least one stated requirement conflicts with your preferences.",
        "needs_clarification": " Some details need confirming.",
        "compatible": " No conflicts with what you told us.",
        "unknown": "",
    }[status]
    return base + tail


# ---------------------------------------------------------------------------
# Work authorization & sponsorship
# ---------------------------------------------------------------------------

AUTH_NOTE = (
    "Sponsorship depends on the destination country and your personal legal status. "
    "This reflects only what the listing says. It is not legal or immigration advice."
)


def evaluate_authorization(prefs: CandidatePreferences, job: JobDetail, claims: list[Claim]) -> AuthorizationSection:
    sp = _by_cat(claims, ClaimCategory.sponsorship_policy)
    values = {c.value for c in sp}
    ids = lambda *vals: [c.id for c in sp if c.value in vals]  # noqa: E731
    findings: list[Finding] = []
    need = prefs.sponsorship
    country = infer_country(job.location)
    where = f" in {country}" if country else ""

    if {"offered"} & values and {"not_offered", "citizenship_required"} & values:
        label = "needs_clarification"
        headline = "The listing contains conflicting statements about sponsorship."
        findings.append(Finding(
            rule_id="A0_CONFLICTING_STATEMENTS", status="caution",
            title="Conflicting sponsorship statements",
            explanation="One passage suggests sponsorship is possible and another restricts it. Ask the employer directly.",
            evidence_claim_ids=ids("offered", "not_offered", "citizenship_required"),
        ))
    elif "not_offered" in values or "citizenship_required" in values:
        label = "explicitly_restricted"
        citizenship = "citizenship_required" in values
        kind = "requires citizenship or a security clearance" if citizenship and "not_offered" not in values else "states sponsorship is not available"
        headline = f"The listing {kind}."
        ev = ids("not_offered", "citizenship_required")
        if citizenship and need != "yes":
            # Not needing sponsorship (e.g. green card / work permit holders) does
            # not satisfy a citizenship or clearance requirement.
            findings.append(Finding(
                rule_id="A1_CITIZENSHIP_REQUIREMENT", status="caution",
                title="Citizenship or clearance requirement",
                explanation="The listing requires citizenship or a security clearance. Not needing sponsorship isn't enough. Check that you meet this specific requirement.",
                evidence_claim_ids=ids("citizenship_required"),
            ))
        elif need == "yes":
            findings.append(Finding(
                rule_id="A1_PUBLISHED_RESTRICTION", status="conflict",
                title="Published sponsorship restriction",
                explanation=f"You said you need sponsorship, and the listing {kind}.",
                evidence_claim_ids=ev,
            ))
        elif need == "unsure":
            findings.append(Finding(
                rule_id="A1_RESTRICTION_UNSURE", status="caution",
                title="Restriction may affect you",
                explanation=f"The listing {kind}. Check whether you'd need sponsorship to work{where}.",
                evidence_claim_ids=ev,
            ))
        else:
            findings.append(Finding(
                rule_id="A1_RESTRICTION_NOT_APPLICABLE", status="agreement",
                title="Restriction doesn't apply to you",
                explanation=f"The listing {kind}, but you said you don't need sponsorship.",
                evidence_claim_ids=ev,
            ))
    elif "offered" in values:
        label = "explicitly_supported"
        headline = "The listing states that visa sponsorship is offered."
        findings.append(Finding(
            rule_id="A2_SPONSORSHIP_OFFERED",
            status="agreement" if need != "no" else "agreement",
            title="Sponsorship is explicitly offered",
            explanation=(
                "The listing says the company sponsors visas. That's a stated policy, not a guarantee for "
                "any individual case. Confirm it covers your situation."
                if need != "no"
                else "The listing says the company sponsors visas (you said you don't need it)."
            ),
            evidence_claim_ids=ids("offered"),
        ))
    elif "case_by_case" in values:
        label = "needs_clarification"
        headline = "The listing says sponsorship may be considered case by case."
        findings.append(Finding(
            rule_id="A3_CASE_BY_CASE", status="caution" if need != "no" else "agreement",
            title="Sponsorship considered case by case",
            explanation="Ask early whether your situation would be considered.",
            evidence_claim_ids=ids("case_by_case"),
        ))
    elif "existing_authorization_required" in values:
        label = "needs_clarification"
        headline = "The listing asks for existing work authorization but doesn't say whether sponsorship is possible."
        findings.append(Finding(
            rule_id="A4_EXISTING_AUTHORIZATION", status="caution" if need != "no" else "agreement",
            title="Existing work authorization requested",
            explanation=(
                "The listing asks candidates to be authorized to work already. It doesn't explicitly rule out "
                "sponsorship, so confirm before applying if you'd need it."
                if need != "no"
                else "The listing asks for existing work authorization. If you're already authorized to work where the role is based, this isn't an obstacle."
            ),
            evidence_claim_ids=ids("existing_authorization_required"),
        ))
    else:
        label = "not_specified"
        headline = "Not specified in the available listing."
        findings.append(Finding(
            rule_id="A5_NOT_SPECIFIED",
            status="unknown" if need != "no" else "agreement",
            title="Sponsorship isn't mentioned",
            explanation=(
                "The listing says nothing about visa sponsorship. Silence isn't a yes or a no, so ask the employer."
                if need != "no"
                else "The listing says nothing about sponsorship, which matters less since you don't need it."
            ),
        ))

    arrangement, _, _ = resolve_arrangement(claims)
    if arrangement == "remote" and need != "no":
        findings.append(Finding(
            rule_id="A6_REMOTE_INTERNATIONAL", status="caution",
            title="Remote roles can avoid visas, or not",
            explanation=(
                "Some companies hire remote workers abroad as contractors or through an employer of record. "
                "Others only employ people who can work in their own country. The listing doesn't settle this."
            ),
        ))

    return AuthorizationSection(label=label, headline=headline, findings=findings, note=AUTH_NOTE)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Technical alignment (supporting info only)
# ---------------------------------------------------------------------------

SKILL_ALIASES = {
    "js": "javascript", "ts": "typescript", "golang": "go", "k8s": "kubernetes",
    "postgres": "postgresql", "node": "node.js", "nodejs": "node.js", "reactjs": "react",
    "react.js": "react", "nextjs": "next.js", "ml": "machine learning", "llm": "llms",
    "py": "python", "gcp": "gcp", "google cloud": "gcp", "amazon web services": "aws",
    "ror": "rails", "ruby on rails": "rails", "c sharp": "c#", "cpp": "c++",
}


def _skill_key(s: str) -> str:
    k = re.sub(r"\s+", " ", s.strip().casefold())
    return SKILL_ALIASES.get(k, k)


def evaluate_technical(prefs: CandidatePreferences, claims: list[Claim]) -> TechnicalSection:
    tech = _by_cat(claims, ClaimCategory.technical_requirement)
    note = "Supporting information only: skills mentioned in the listing compared with skills you entered. Not a hiring decision."
    if not prefs.skills:
        return TechnicalSection(
            status="needs_skills",
            headline="Add a few skills to compare against the listing." if tech else "Requires additional skills information.",
            listed_not_provided=[SkillMatch(skill=c.value, evidence_claim_id=c.id) for c in tech],
            note=note,
        )
    if not tech:
        return TechnicalSection(
            status="no_requirements_found",
            headline="We didn't find named technologies in this listing.",
            provided_not_listed=list(prefs.skills),
            note=note,
        )
    listed = {_skill_key(c.value): c for c in tech}
    provided = {_skill_key(s): s for s in prefs.skills}
    matched = [SkillMatch(skill=listed[k].value, evidence_claim_id=listed[k].id) for k in listed if k in provided]
    missing = [SkillMatch(skill=listed[k].value, evidence_claim_id=listed[k].id) for k in listed if k not in provided]
    extra = [provided[k] for k in provided if k not in listed]
    headline = f"{len(matched)} of {len(listed)} technologies mentioned in the listing match your skills."
    return TechnicalSection(
        status="assessed", headline=headline, matched=matched,
        listed_not_provided=missing, provided_not_listed=extra, note=note,
    )
