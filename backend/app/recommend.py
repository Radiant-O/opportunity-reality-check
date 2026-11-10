"""Deterministic next steps, assessment sentence, and copyable draft inquiry.

These are candidate-specific and derived only from rule findings, so they are
kept separate from factual extraction.
"""

from __future__ import annotations

from .models import (
    AuthorizationSection,
    CandidatePreferences,
    JobDetail,
    LocationSection,
    NextStep,
    TechnicalSection,
)


def _rules(section) -> set[str]:
    return {f.rule_id for f in section.findings}


def build_next_steps(
    prefs: CandidatePreferences,
    job: JobDetail,
    loc: LocationSection,
    auth: AuthorizationSection,
    tech: TechnicalSection,
) -> list[NextStep]:
    steps: list[NextStep] = []
    lr, ar = _rules(loc), _rules(auth)

    def add(id_: str, text: str, reason: str, priority: str) -> None:
        if all(s.id != id_ for s in steps):
            steps.append(NextStep(id=id_, text=text, reason=reason, priority=priority))  # type: ignore[arg-type]

    if "A1_PUBLISHED_RESTRICTION" in ar:
        add("reconsider", "Weigh whether to apply: the listing states a sponsorship restriction.",
            "A published restriction conflicts with your stated need. Unless you can get authorization another way, this role may not be workable.", "high")
    if prefs.sponsorship != "no" and auth.label in ("not_specified", "needs_clarification"):
        add("confirm-sponsorship", "Confirm sponsorship availability with the employer before investing significant time.",
            "The listing doesn't establish whether sponsorship is available for your situation.", "high")
    if prefs.sponsorship != "no" and auth.label == "explicitly_supported":
        add("confirm-sponsorship-scope", "Ask which visa types they have sponsored and whether that covers your situation.",
            "A stated sponsorship policy isn't a guarantee for every individual case.", "medium")
    if prefs.sponsorship == "unsure":
        add("check-status", "Check whether you'd need sponsorship to work in the role's country.",
            "You weren't sure. The answer depends on your citizenship and current status.", "medium")
    if "L3_REMOTE_COUNTRIES_UNSPECIFIED" in lr or "L3_REMOTE_REGION_UNCLEAR" in lr:
        add("remote-country", "Verify whether remote work includes your country.",
            "The listing is remote but doesn't clearly say which countries can be hired from.", "high")
    if "A6_REMOTE_INTERNATIONAL" in ar:
        add("remote-employment-model", "Ask whether international remote hires are employed directly, via an employer of record, or as contractors.",
            "That determines whether a visa is relevant at all.", "medium")
    if loc.work_arrangement in ("onsite", "hybrid"):
        add("presence", f"Check how often the role requires physical presence in {job.location or 'the office'}.",
            "Onsite and hybrid roles require living within reach of the office.", "medium")
    if "L2_RELOCATION_NEEDED" in lr or "L5_RELOCATION_REQUIRED" in lr:
        add("relocation-support", "Ask whether relocation support is offered, including for international moves.",
            "Relocation would be needed, and the cost and logistics matter.", "medium")
    if "L4_TIMEZONE" in lr:
        add("timezone", "Confirm the required working hours fit your time zone.",
            "The listing states a time-zone or working-hours requirement.", "medium")
    if "L0_SOURCE_DISAGREEMENT" in lr:
        add("arrangement-confirm", "Confirm the actual work arrangement (the listing's label and text disagree).",
            "Conflicting signals in the listing.", "medium")
    if not prefs.country:
        add("add-country", "Add your country of residence above for a more specific check.",
            "Location compatibility can't be assessed without it.", "low")
    if tech.status == "needs_skills" and tech.listed_not_provided:
        add("add-skills", "Add a few of your skills to compare against the technologies the listing mentions.",
            "Technical alignment is optional supporting information.", "low")
    add("official-page", "Review the employer's official application page for anything not covered here.",
        "This check only covers what the listing text states.", "low")
    order = {"high": 0, "medium": 1, "low": 2}
    return sorted(steps, key=lambda s: order[s.priority])


def build_assessment(prefs: CandidatePreferences, loc: LocationSection, auth: AuthorizationSection) -> str:
    conflicts = [f.title for f in loc.findings + auth.findings if f.status == "conflict"]
    unknowns: list[str] = []
    if auth.label in ("not_specified", "needs_clarification") and prefs.sponsorship != "no":
        unknowns.append("sponsorship")
    if any(f.rule_id in ("L3_REMOTE_COUNTRIES_UNSPECIFIED", "L3_REMOTE_REGION_UNCLEAR") for f in loc.findings):
        unknowns.append("which countries remote work covers")
    if any(f.rule_id == "L2_RELOCATION_NEEDED" for f in loc.findings):
        unknowns.append("relocation arrangements")
    if any(f.rule_id == "L1_ARRANGEMENT_UNKNOWN" for f in loc.findings):
        unknowns.append("the work arrangement")

    if conflicts:
        lead = f"The listing explicitly states something that conflicts with your preferences ({'; '.join(conflicts).lower()})."
        if unknowns:
            return lead + f" It also leaves {_join(unknowns)} unclear."
        return lead + " Consider whether this role is realistic before applying."
    if unknowns:
        return (
            f"No explicit conflicts, but the listing doesn't settle {_join(unknowns)}. "
            "Verify these before investing significant time in the application."
        )
    return (
        "Nothing the listing states conflicts with what you told us. "
        "That isn't a guarantee of eligibility, so still review the official posting."
    )


def _join(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def build_draft_inquiry(
    prefs: CandidatePreferences, job: JobDetail, loc: LocationSection, auth: AuthorizationSection
) -> str:
    questions: list[str] = []
    lr = _rules(loc)
    if prefs.sponsorship != "no" and auth.label != "explicitly_restricted":
        if auth.label == "explicitly_supported":
            questions.append("The listing mentions visa sponsorship. Could you share which visa types you typically sponsor?")
        else:
            country = loc.job_country or "the role's country"
            questions.append(f"Does this position support candidates who would need employer sponsorship to work in {country}?")
    if "L3_REMOTE_COUNTRIES_UNSPECIFIED" in lr or "L3_REMOTE_REGION_UNCLEAR" in lr or "L3_REMOTE_REGION_MATCH" in lr:
        where = prefs.country or "my country"
        questions.append(f"Is the remote arrangement open to candidates based in {where}?")
    if loc.work_arrangement in ("onsite", "hybrid"):
        questions.append(f"How many days per week is in-office presence expected in {job.location or 'the office'}?")
    if "L2_RELOCATION_NEEDED" in lr or "L5_RELOCATION_REQUIRED" in lr:
        questions.append("Is relocation support available, including for international moves?")
    if "L4_TIMEZONE" in lr:
        questions.append("What working hours or time-zone overlap does the team expect?")
    if not questions:
        questions.append("Is there anything about location or work authorization I should know before applying?")

    lines = [
        "Hi there,",
        "",
        f"I'm interested in the {job.title} role at {job.company} and want to make sure I understand "
        "the requirements before applying. Could you help with a few quick questions?",
        "",
    ]
    lines += [f"{i}. {q}" for i, q in enumerate(questions, start=1)]
    lines += ["", "Thank you for your time.", "", "[Your name]"]
    return "\n".join(lines)
