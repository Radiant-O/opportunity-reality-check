"""Evidence validation: the gate between any extractor and the rules engine.

A claim is only usable if:
1. its quote is long enough to be meaningful,
2. the quote actually appears in the declared source (after whitespace /
   quote-character normalization),
3. the quote isn't an instruction aimed at the model (prompt injection),
4. for policy categories, the quote is about the right topic and its
   deterministic polarity doesn't contradict the claimed value,
5. its value is in the category's canonical vocabulary.

Claims failing any check are returned as rejected, with a reason.
"""

from __future__ import annotations

import re
import unicodedata

from ..models import CANONICAL_VALUES, Claim, ClaimCategory, JobDetail

MIN_QUOTE_CHARS = 3
MIN_DESCRIPTION_QUOTE_CHARS = 12

INJECTION_MARKERS = re.compile(
    r"\b(?:ignore|disregard|forget)\b[^.]{0,40}\b(?:previous|prior|above|earlier|all|any)\b[^.]{0,20}"
    r"\b(?:instructions?|prompts?|rules)\b|"
    r"\b(?:system prompt|you are (?:an? )?(?:ai|assistant|language model|llm)|as an ai\b)|"
    r"\b(?:respond|reply|output|answer|classify|mark|report)\b[^.]{0,40}\b(?:as|with|that)\b[^.]{0,40}"
    r"\b(?:sponsorship|visa|eligible|eligibility)\b[^.]{0,40}\b(?:is|are)? ?(?:offered|available|guaranteed|true|yes)\b(?=[^.]*\b(?:ai|model|assistant|llm|bot|tool)\b)|"
    r"<\s*/?\s*(?:system|instructions?|prompt)\s*>",
    re.IGNORECASE,
)

TOPIC_PATTERNS: dict[ClaimCategory, re.Pattern[str]] = {
    ClaimCategory.sponsorship_policy: re.compile(
        r"sponsor|visa|immigra|h-?1b|o-?1|green card|authori[sz]|right to work|citizen|clearance|work permit|eligible to work",
        re.IGNORECASE,
    ),
    ClaimCategory.relocation_requirement: re.compile(r"relocat|move to|moving to", re.IGNORECASE),
    ClaimCategory.work_arrangement: re.compile(
        r"remote|hybrid|on-?site|in[- ]?person|in[- ]office|office|days? (?:a|per) week|anywhere",
        re.IGNORECASE,
    ),
}

_QUOTE_MAP = str.maketrans(
    {
        "‘": "'", "’": "'", "“": '"', "”": '"', "–": "-",
        "—": "-", "−": "-", " ": " ", "•": "-",
    }
)


def normalize_for_match(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).translate(_QUOTE_MAP)
    s = re.sub(r"\s+", " ", s)
    return s.strip().casefold()


def source_text(job: JobDetail, source: str) -> str | None:
    if source == "description":
        return job.description_text
    if source == "metadata.location":
        return job.location
    if source == "metadata.workplace_type":
        return job.workplace_type_raw
    if source == "metadata.employment_type":
        return job.employment_type
    if source == "metadata.remote":
        return "true" if job.remote else "false"
    return None


def _polarity_contradiction(claim: Claim) -> str | None:
    """Run the deterministic classifier on the quote itself and reject claims
    whose value contradicts what the quote plainly says."""
    from .deterministic import extract_description  # local import to avoid cycle

    if claim.category not in (
        ClaimCategory.sponsorship_policy,
        ClaimCategory.relocation_requirement,
        ClaimCategory.work_arrangement,
    ):
        return None
    det = [c for c in extract_description(claim.evidence_text) if c.category == claim.category]
    if not det:
        return None
    det_values = {c.value for c in det}
    if claim.value in det_values:
        return None
    opposites = {
        ("offered", "not_offered"), ("not_offered", "offered"),
        ("offered", "citizenship_required"),
        ("assistance_offered", "not_offered"), ("not_offered", "assistance_offered"),
        ("remote", "onsite"), ("onsite", "remote"),
    }
    for dv in det_values:
        if (claim.value, dv) in opposites:
            return f"Quote reads as '{dv}', which contradicts the claimed value '{claim.value}'."
    return None


def validate_claim(claim: Claim, job: JobDetail) -> Claim:
    def reject(reason: str) -> Claim:
        return claim.model_copy(update={"verification_status": "rejected", "rejection_reason": reason})

    quote = claim.evidence_text or ""
    min_len = MIN_DESCRIPTION_QUOTE_CHARS if claim.evidence_source == "description" else MIN_QUOTE_CHARS
    if len(quote.strip()) < min_len:
        return reject("Quoted evidence is too short to support a claim.")

    canon = CANONICAL_VALUES.get(claim.category)
    if canon is not None and claim.value not in canon:
        return reject(f"'{claim.value}' is not a recognised value for {claim.category.value}.")

    src = source_text(job, claim.evidence_source)
    if not src:
        return reject(f"The source field '{claim.evidence_source}' is empty for this listing.")
    if normalize_for_match(quote) not in normalize_for_match(src):
        return reject("Quoted evidence does not appear in the listing (possible fabrication).")

    if INJECTION_MARKERS.search(quote):
        return reject("Quoted text looks like an instruction aimed at an AI model, not a job requirement.")

    topic = TOPIC_PATTERNS.get(claim.category)
    if topic is not None and claim.evidence_source == "description" and not topic.search(quote):
        return reject(f"Quoted evidence is not about {claim.category.value.replace('_', ' ')}.")

    contradiction = _polarity_contradiction(claim)
    if contradiction:
        return reject(contradiction)

    return claim.model_copy(update={"verification_status": "verified", "rejection_reason": None})


def validate_claims(claims: list[Claim], job: JobDetail) -> tuple[list[Claim], list[Claim]]:
    verified: list[Claim] = []
    rejected: list[Claim] = []
    for c in claims:
        v = validate_claim(c, job)
        (verified if v.verification_status == "verified" else rejected).append(v)
    return verified, rejected
