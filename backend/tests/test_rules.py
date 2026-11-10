from __future__ import annotations

import pytest

from app.analysis import analyze
from app.extraction.pipeline import run_extraction
from app.rules import evaluate_authorization, evaluate_location, evaluate_technical

from .conftest import make_job, prefs


async def claims_for(job):
    return (await run_extraction(job, None)).claims


def rule_ids(section):
    return {f.rule_id: f.status for f in section.findings}


async def test_remote_preference_vs_explicit_onsite_is_conflict():
    job = make_job(workplace_type="OnSite", description_text="This role is in-person 5 days a week in SF.")
    loc = evaluate_location(prefs(work_arrangement="remote", country="United States"), job, await claims_for(job))
    assert rule_ids(loc)["L1_ARRANGEMENT_CONFLICT"] == "conflict"
    assert loc.status == "conflict"


async def test_unwilling_to_relocate_vs_required_relocation_is_conflict():
    job = make_job(workplace_type="OnSite", description_text="You must be willing to relocate to San Francisco.")
    loc = evaluate_location(prefs(country="United States", relocation="no"), job, await claims_for(job))
    assert rule_ids(loc)["L5_RELOCATION_REQUIRED_CONFLICT"] == "conflict"


async def test_needs_sponsorship_vs_explicit_restriction():
    job = make_job(description_text="We are unable to sponsor visas for this role.")
    auth = evaluate_authorization(prefs(sponsorship="yes"), job, await claims_for(job))
    assert auth.label == "explicitly_restricted"
    assert rule_ids(auth)["A1_PUBLISHED_RESTRICTION"] == "conflict"


async def test_needs_sponsorship_and_listing_silent_is_not_specified():
    job = make_job(description_text="We build developer tools in Python.")
    auth = evaluate_authorization(prefs(sponsorship="yes"), job, await claims_for(job))
    assert auth.label == "not_specified"
    assert rule_ids(auth)["A5_NOT_SPECIFIED"] == "unknown"


async def test_open_to_relocation_onsite_abroad_is_caution_not_eligibility():
    job = make_job(workplace_type="OnSite")
    loc = evaluate_location(prefs(country="Nigeria", relocation="yes"), job, await claims_for(job))
    f = next(f for f in loc.findings if f.rule_id == "L2_RELOCATION_NEEDED")
    assert f.status == "caution"
    assert "separate question" in f.explanation
    assert loc.status == "needs_clarification"


async def test_sponsorship_offered_is_supported_but_not_guaranteed():
    job = make_job(description_text="We're happy to sponsor international candidates (H1B, O1).")
    auth = evaluate_authorization(prefs(sponsorship="yes"), job, await claims_for(job))
    assert auth.label == "explicitly_supported"
    assert "not a guarantee" in auth.findings[0].explanation


async def test_conflicting_sponsorship_statements_need_clarification():
    job = make_job(description_text="We're happy to sponsor visas for engineers.\nWe are unable to sponsor visas for this role.")
    auth = evaluate_authorization(prefs(sponsorship="yes"), job, await claims_for(job))
    assert auth.label == "needs_clarification"


async def test_existing_authorization_is_clarification_not_restriction():
    job = make_job(description_text="You must be legally authorized to work in the United States.")
    auth = evaluate_authorization(prefs(sponsorship="yes"), job, await claims_for(job))
    assert auth.label == "needs_clarification"


async def test_ambiguous_remote_without_countries():
    job = make_job(location="Remote", workplace_type="Remote", remote=True, description_text="We are a remote-first team.")
    loc = evaluate_location(prefs(country="Nigeria", work_arrangement="remote"), job, await claims_for(job))
    assert rule_ids(loc)["L3_REMOTE_COUNTRIES_UNSPECIFIED"] == "unknown"
    assert loc.status == "needs_clarification"


async def test_remote_restricted_to_other_region_is_conflict():
    job = make_job(location="Remote - US", workplace_type="Remote", remote=True, description_text="Work from home.")
    loc = evaluate_location(prefs(country="Nigeria", work_arrangement="remote"), job, await claims_for(job))
    assert rule_ids(loc)["L3_REMOTE_REGION_CONFLICT"] == "conflict"


async def test_remote_region_including_candidate():
    job = make_job(location="Remote - EU", workplace_type="Remote", remote=True, description_text="Work from home.")
    loc = evaluate_location(prefs(country="Germany", work_arrangement="remote"), job, await claims_for(job))
    assert rule_ids(loc)["L3_REMOTE_REGION_MATCH"] == "agreement"


async def test_label_vs_description_disagreement_flagged():
    job = make_job(workplace_type="Remote", description_text="This role is in-person 5 days a week in SF.")
    loc = evaluate_location(prefs(), job, await claims_for(job))
    assert "L0_SOURCE_DISAGREEMENT" in rule_ids(loc)
    assert loc.work_arrangement == "onsite"


async def test_missing_arrangement_is_unknown():
    job = make_job(workplace_type=None, description_text="Join us.")
    loc = evaluate_location(prefs(), job, await claims_for(job))
    assert rule_ids(loc)["L1_ARRANGEMENT_UNKNOWN"] == "unknown"


async def test_technical_alignment_is_separate_and_needs_skills():
    job = make_job(description_text="We use Python, Go and Kubernetes.")
    claims = await claims_for(job)
    assert evaluate_technical(prefs(), claims).status == "needs_skills"
    t = evaluate_technical(prefs(skills=["python", "k8s", "Figma"]), claims)
    assert t.status == "assessed"
    assert {m.skill for m in t.matched} == {"Python", "Kubernetes"}
    assert t.provided_not_listed == ["Figma"]


async def test_spec_example_nigeria_sf_hybrid_sponsorship_unmentioned():
    """Section 14 of the spec, reproduced end to end."""
    job = make_job(
        title="Senior Software Engineer", location="San Francisco, California",
        workplace_type="Hybrid", description_text="Build our core platform. Strong backend experience required.",
    )
    # "Remote or willing to relocate" == flexible arrangement + open to relocation
    p = prefs(country="Nigeria", work_arrangement="flexible", relocation="yes", sponsorship="yes")
    res = await analyze(job, p, None)
    assert res.technical.status == "needs_skills"
    assert res.technical.headline == "Requires additional skills information."
    assert res.location.job_country == "United States"
    assert res.location.work_arrangement == "hybrid"
    assert res.authorization.label == "not_specified"
    assert res.authorization.headline == "Not specified in the available listing."
    assert "sponsorship" in res.assessment and "Verify" in res.assessment
    assert res.next_steps[0].id in {"confirm-sponsorship", "reconsider"}
    assert "sponsorship" in res.draft_inquiry
    assert "not legal or immigration advice" in res.disclaimer
    # no single opaque score anywhere
    assert "score" not in res.model_dump_json().lower()


@pytest.mark.parametrize("sp", ["yes", "no", "unsure"])
async def test_rules_are_deterministic(sp):
    job = make_job(description_text="We offer relocation assistance. Hybrid role, 3 days a week in office. We are unable to sponsor visas.")
    p = prefs(country="India", sponsorship=sp, relocation="conditional", work_arrangement="hybrid")
    a = (await analyze(job, p, None)).model_dump()
    b = (await analyze(job, p, None)).model_dump()
    assert a == b


async def test_every_finding_references_only_verified_claims():
    job = make_job(description_text="We are unable to sponsor visas. In-person 5 days a week. We offer relocation assistance.")
    res = await analyze(job, prefs(country="Kenya", sponsorship="yes", relocation="no", work_arrangement="remote"), None)
    ids = {c.id for c in res.extraction.claims}
    for section in (res.location, res.authorization):
        for f in section.findings:
            assert set(f.evidence_claim_ids) <= ids
