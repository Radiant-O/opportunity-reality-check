"""Evidence validation: the gate between any extractor and the rules engine.

A claim is only usable if all of these hold:

1. Its quote is long enough to mean something, and its value is in the
   category's canonical vocabulary.
2. The quote actually appears in the declared source (after whitespace /
   quote-character normalization).
3. Every semantic check runs on the **full sentence** containing the quote, not
   on the quote alone. Otherwise an extractor could quote "eligible for visa
   sponsorship" out of "This role is not eligible for visa sponsorship".
4. Prompt injection: if the listing contains text addressed to AI / automated
   tools anywhere, *every* LLM claim from that listing is rejected, and
   deterministic claims in or next to the injected sentence are rejected too.
5. Policy categories (sponsorship, relocation, work arrangement): the
   deterministic reading of the full sentence must agree with the claimed
   value. When the deterministic reader finds nothing, an LLM may only claim a
   *positive* policy from a sentence with no negation in it.
6. Other categories must be on-topic: regions must name a known place that
   appears in the sentence, employment types must mention employment terms,
   skills must appear in the quote.

Claims failing any check are returned as rejected, with a reason.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from ..geo import COUNTRY_ALIASES, REGION_ALIASES, canonical_region
from ..models import CANONICAL_VALUES, Claim, ClaimCategory, JobDetail
from . import deterministic as det

MIN_QUOTE_CHARS = 3
MIN_DESCRIPTION_QUOTE_CHARS = 12

INJECTION_MARKERS = re.compile(
    r"\b(?:ignore|disregard|forget|override)\b[^.\n]{0,40}\b(?:previous|prior|above|earlier|all|any|your|these|the)\b"
    r"[^.\n]{0,20}\b(?:instructions?|prompts?|rules|guidelines)\b|"
    r"\b(?:system prompt|you are (?:an? )?(?:ai|assistant|language model|llm|bot)|as an ai\b)|"
    r"\b(?:note|message|instructions?|attention|notice)\b[^.\n:]{0,25}\b(?:to|for)\b[^.\n:]{0,20}"
    r"\b(?:ai|a\.i\.|llms?|language models?|models?|assistants?|bots?|chatgpt|claude|gpt|automated|screening|screeners?|"
    r"tools?|parsers?|agents?|crawlers?)\b|"
    r"\b(?:ai|llm|automated|screening)\s+(?:screeners?|tools?|systems?|assistants?|agents?|reviewers?)\b[^.\n]{0,15}:|"
    r"\b(?:respond|reply|output|answer|classify|mark|report|say|state|tell)\b[^.\n]{0,15}\bthat\b[^.\n]{0,60}"
    r"\b(?:sponsorship|visa|eligible|eligibility|qualif\w+)\b[^.\n]{0,40}\b(?:is|are)?\s?(?:offered|available|guaranteed|true|yes|eligible)\b|"
    r"<\s*/?\s*(?:system|instructions?|prompt)\s*>",
    re.IGNORECASE,
)

_EMPLOYMENT_TOPIC = re.compile(
    r"full[- ]?time|part[- ]?time|contract|contractor|intern|internship|temporary|temp\b|freelance|fixed[- ]term",
    re.IGNORECASE,
)

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


@dataclass
class ListingContext:
    """Pre-computed sentence index for one description."""

    sentences: list[str]
    normalized: list[str]
    injection_idx: set[int]

    @classmethod
    def build(cls, text: str | None) -> ListingContext:
        sents = [s.text for s in det.segments(text or "")]
        norm = [normalize_for_match(s) for s in sents]
        inj = {i for i, s in enumerate(sents) if INJECTION_MARKERS.search(s)}
        return cls(sents, norm, inj)

    @property
    def injection_detected(self) -> bool:
        return bool(self.injection_idx)

    def locate(self, quote: str) -> tuple[str, range] | None:
        """Return (full sentence text, sentence index range) containing the quote."""
        q = normalize_for_match(quote)
        if not q:
            return None
        n = len(self.sentences)
        # Smallest window first, so a quote maps to its own sentence, not a span
        # that happens to include neighbouring sentences.
        for width in range(1, 5):
            for i in range(0, n - width + 1):
                joined = " ".join(self.normalized[i : i + width])
                if q in joined:
                    return " ".join(self.sentences[i : i + width]), range(i, i + width)
        return None

    def near_injection(self, idx: range) -> bool:
        return any(k in self.injection_idx for i in idx for k in (i - 1, i, i + 1))


def _region_mentioned(region: str, text: str) -> bool:
    low = normalize_for_match(text)
    aliases = [k for k, v in {**COUNTRY_ALIASES, **REGION_ALIASES}.items() if v == region] + [region.lower()]
    for a in aliases:
        if re.search(rf"(?<![\w.]){re.escape(a)}(?![\w])", low):
            return True
    return False


def _policy_values(category: ClaimCategory, sentence: str) -> set[str]:
    if category == ClaimCategory.sponsorship_policy:
        return {v for v, _ in det.classify_sponsorship(sentence)}
    if category == ClaimCategory.relocation_requirement:
        return {v for v, _ in det.classify_relocation(sentence)}
    if category == ClaimCategory.work_arrangement:
        return {c.value for c in det.extract_description(sentence) if c.category == ClaimCategory.work_arrangement}
    return set()


_POSITIVE_POLICY = {"offered", "assistance_offered", "case_by_case"}


def validate_claim(claim: Claim, job: JobDetail, ctx: ListingContext | None = None) -> Claim:
    def reject(reason: str) -> Claim:
        return claim.model_copy(update={"verification_status": "rejected", "rejection_reason": reason})

    if ctx is None:
        ctx = ListingContext.build(job.description_text)

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

    # Full-sentence context for description quotes.
    sentence = quote
    idx: range = range(0)
    if claim.evidence_source == "description":
        located = ctx.locate(quote)
        if located is None:
            return reject("Could not locate the sentence containing the quote.")
        sentence, idx = located

    # Prompt injection.
    if INJECTION_MARKERS.search(sentence):
        return reject("The quoted sentence looks like an instruction aimed at an AI tool, not a job requirement.")
    if claim.extractor == "llm" and ctx.injection_detected:
        return reject("This listing contains text addressed to AI tools, so AI-extracted claims from it are not trusted.")
    # Injected text aims to manufacture *favourable* readings, so favourable
    # claims next to it are distrusted; restrictive statements are kept.
    if claim.evidence_source == "description" and ctx.near_injection(idx) and claim.value in _POSITIVE_POLICY:
        return reject("The quote sits next to text addressed to AI tools, so a favourable reading is not trusted.")

    cat = claim.category
    if cat in (ClaimCategory.sponsorship_policy, ClaimCategory.relocation_requirement, ClaimCategory.work_arrangement):
        if claim.evidence_source == "description":
            found = _policy_values(cat, sentence)
            if found and claim.value not in found:
                return reject(
                    f"The full sentence reads as {', '.join(sorted(found))}, not '{claim.value}'."
                )
            if not found:
                topic = det.IMMIGRATION_TERM if cat == ClaimCategory.sponsorship_policy else None
                if cat == ClaimCategory.sponsorship_policy and not (
                    det.SPONSOR_WORD.search(sentence) or (topic and topic.search(sentence)) or det.CITIZENSHIP.search(sentence)
                ):
                    return reject("The quoted sentence is not about visa sponsorship or work authorization.")
                if cat == ClaimCategory.relocation_requirement and not re.search(r"relocat", sentence, re.I):
                    return reject("The quoted sentence is not about relocation.")
                if cat == ClaimCategory.work_arrangement and not re.search(
                    r"remote|hybrid|on-?site|in[- ]?person|in[- ]office|office|days? (?:a|per) week|anywhere", sentence, re.I
                ):
                    return reject("The quoted sentence is not about the work arrangement.")
                if claim.value in _POSITIVE_POLICY and det.has_negation(sentence):
                    return reject("The sentence contains a negation, so a positive reading is not supported.")
                if cat == ClaimCategory.sponsorship_policy and claim.value == "offered" and not (
                    det.SPONSOR_WORD.search(sentence) and det.IMMIGRATION_TERM.search(sentence)
                ):
                    return reject("Claiming sponsorship is offered needs an explicit visa sponsorship statement.")

    elif cat == ClaimCategory.geographic_restriction:
        if claim.value.startswith("Time zone"):
            if not det.TIMEZONE.search(sentence):
                return reject("The quoted text does not state a time-zone or working-hours requirement.")
        else:
            region = canonical_region(claim.value)
            if region is None:
                return reject(f"'{claim.value}' is not a country or region we can interpret.")
            if not _region_mentioned(region, sentence):
                return reject(f"The quoted text does not mention {region}.")

    elif cat == ClaimCategory.employment_type:
        if not _EMPLOYMENT_TOPIC.search(sentence):
            return reject("The quoted text does not mention an employment type.")

    elif cat == ClaimCategory.technical_requirement:
        rx = det._SKILL_RES.get(claim.value)
        if rx is not None:
            if not rx.search(quote):
                return reject(f"'{claim.value}' does not appear in the quoted text.")
        elif normalize_for_match(claim.value) not in normalize_for_match(quote):
            return reject(f"'{claim.value}' does not appear in the quoted text.")

    return claim.model_copy(update={"verification_status": "verified", "rejection_reason": None})


def validate_claims(claims: list[Claim], job: JobDetail) -> tuple[list[Claim], list[Claim], bool]:
    ctx = ListingContext.build(job.description_text)
    verified: list[Claim] = []
    rejected: list[Claim] = []
    for c in claims:
        v = validate_claim(c, job, ctx)
        (verified if v.verification_status == "verified" else rejected).append(v)
    return verified, rejected, ctx.injection_detected
