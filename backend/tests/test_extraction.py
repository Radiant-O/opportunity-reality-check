from __future__ import annotations

import pytest

from app.extraction.deterministic import extract_all, extract_description, segments
from app.models import ClaimCategory

from .conftest import make_job


def values(text: str, cat: ClaimCategory) -> set[str]:
    return {c.value for c in extract_description(text) if c.category == cat}


SP = ClaimCategory.sponsorship_policy
RL = ClaimCategory.relocation_requirement
WA = ClaimCategory.work_arrangement
GEO = ClaimCategory.geographic_restriction


@pytest.mark.parametrize(
    "text",
    [
        "We are unable to sponsor visas for this role.",
        "Unfortunately we cannot provide visa sponsorship at this time.",
        "No visa sponsorship is available.",
        "Candidates must be authorized to work in the US without the need for current or future sponsorship.",
        "We do not offer H-1B sponsorship.",
        "Sponsorship is not available for this position.",
    ],
)
def test_sponsorship_not_offered(text):
    assert values(text, SP) == {"not_offered"}


@pytest.mark.parametrize(
    "text",
    [
        "We're happy to sponsor international candidates (e.g., STEM OPT, OPT, H1B, O1, E3).",
        "- Visas: We’re happy to sponsor international candidates!",
        "Visa sponsorship is available for exceptional candidates.",
        "We offer visa sponsorship and relocation support.",
    ],
)
def test_sponsorship_offered(text):
    assert "offered" in values(text, SP)


def test_sponsorship_case_by_case():
    assert values("Visa sponsorship is considered on a case-by-case basis.", SP) == {"case_by_case"}


def test_citizenship_required():
    assert "citizenship_required" in values("Applicants must be a U.S. citizen due to export controls.", SP)


def test_existing_authorization_required():
    assert values("You must be legally authorized to work in the United States.", SP) == {
        "existing_authorization_required"
    }


@pytest.mark.parametrize(
    "text",
    [
        "🌎 Company Sponsored Conferences & Events",
        "We sponsor a weekly team lunch and hackathons.",
        "Our CEO previously worked at a company that sponsors open source.",
        "Competitive salary of $250k-$300k and a 401k.",
    ],
)
def test_perks_and_salary_never_imply_sponsorship(text):
    assert values(text, SP) == set()


def test_relocation_assistance_and_not_offered():
    assert values("We offer relocation assistance to San Francisco.", RL) == {"assistance_offered"}
    assert values("We do not offer relocation assistance for this role.", RL) == {"not_offered"}
    assert "required" in values("You must be willing to relocate to Austin, TX.", RL)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Our team works in person 4–5 days per week in San Francisco.", "onsite"),
        ("This full-time role is in-person 5 days a week in Miami.", "onsite"),
        ("We expect 3 days a week in the office.", "hybrid"),
        ("This is a hybrid role with two days in office.", "hybrid"),
        ("This role is fully remote.", "remote"),
        ("This is not a remote position.", "onsite"),
    ],
)
def test_work_arrangement_from_description(text, expected):
    assert expected in values(text, WA)


def test_compound_hybrid_title_is_not_work_arrangement():
    assert values("What you’ll do (MTS/Research-Software Hybrid Role):", WA) == set()


def test_free_meals_on_in_office_days_is_not_an_arrangement():
    assert values("- Free meals on in-office days", WA) == set()


def test_ambiguous_remote_mentions_are_not_overclaimed():
    # "remote" alone (e.g. tooling, sensors) is not an arrangement statement
    assert values("Experience with remote sensing data is a plus.", WA) == set()


def test_geographic_restrictions():
    assert "United States" in values("Candidates must be located in the United States.", GEO)
    assert "European Union" in values("This role is EU-only.", GEO)
    assert any(v.startswith("Time zone") for v in values("- Live between GMT-8 and GMT-5 (North American timezones)", GEO))


def test_remote_location_metadata_yields_region():
    job = make_job(location="Remote - US", workplace_type="Remote", remote=True, description_text="Build things.")
    claims = extract_all(job)
    geo = [c for c in claims if c.category == GEO]
    assert geo and geo[0].value == "United States" and geo[0].evidence_source == "metadata.location"


def test_metadata_claims():
    job = make_job()
    cats = {(c.category, c.value, c.evidence_source) for c in extract_all(job)}
    assert (ClaimCategory.job_location, "San Francisco, CA", "metadata.location") in cats
    assert (WA, "hybrid", "metadata.workplace_type") in cats
    assert (ClaimCategory.employment_type, "full_time", "metadata.employment_type") in cats


def test_technical_skills():
    skills = values("Strong Python, TypeScript and React. Experience with Kubernetes on AWS. JavaScript a plus.", ClaimCategory.technical_requirement)
    assert {"Python", "TypeScript", "React", "Kubernetes", "AWS", "JavaScript"} <= skills
    assert "Java" not in skills  # 'JavaScript' must not match 'Java'


def test_every_evidence_quote_is_an_exact_substring():
    text = (
        "About us\nWe’re a seed-stage team.   We are unable to sponsor visas.\n"
        "- We offer relocation assistance to SF!\nWork in person 5 days a week. Python required."
    )
    for c in extract_description(text):
        assert c.evidence_text in text


def test_segments_preserve_offsets():
    text = "First line.\n  Second sentence here. Third one!\n"
    for seg in segments(text):
        assert text[seg.start : seg.start + len(seg.text)] == seg.text


def test_extraction_is_deterministic():
    job = make_job(description_text="We are unable to sponsor visas. Hybrid role, 3 days a week in office. Python.")
    a = [c.model_dump() for c in extract_all(job)]
    b = [c.model_dump() for c in extract_all(job)]
    assert a == b
