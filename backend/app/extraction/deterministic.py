"""Deterministic (regex/keyword) extraction of job requirements.

This runs first and always. Every claim quotes an exact, contiguous span of the
source text (a sentence or bullet), so evidence validation is trivially
satisfied and fully reproducible.

Design rules:
* Prefer precision over recall. A missed statement becomes "Not specified",
  which is honest; a false statement would be harmful.
* Negations are checked before affirmations within the same segment.
* "Sponsor" only counts when the segment is about visas / immigration / work
  authorization (so "Company Sponsored Conferences" is ignored).
* Nothing is inferred from salary, company size, country, reputation or title.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..geo import canonical_region, infer_country
from ..models import Claim, ClaimCategory, JobDetail
from ..normalize import normalize_workplace

# ---------------------------------------------------------------------------
# Segmentation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Segment:
    text: str
    start: int


_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(•\-–])")


def segments(text: str) -> list[Segment]:
    """Split text into lines, then sentences, keeping exact substrings."""
    out: list[Segment] = []
    pos = 0
    for line in text.splitlines(keepends=True):
        line_start = pos
        pos += len(line)
        stripped = line.strip()
        if not stripped:
            continue
        offset = line_start + line.index(stripped)
        cursor = 0
        for m in _SENT_SPLIT.finditer(stripped):
            piece = stripped[cursor : m.start()].strip()
            if piece:
                out.append(Segment(piece, offset + stripped.index(piece, cursor)))
            cursor = m.end()
        tail = stripped[cursor:].strip()
        if tail:
            out.append(Segment(tail, offset + stripped.index(tail, cursor)))
    return out


def _clip(seg: str, match: re.Match[str], limit: int = 420) -> str:
    """Return the segment, or a window around the match if it is very long."""
    if len(seg) <= limit:
        return seg
    start = max(0, match.start() - limit // 2)
    end = min(len(seg), start + limit)
    return seg[start:end].strip()


# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

_I = re.IGNORECASE

# Immigration terms. "visa-free" is travel, not immigration; bare "sponsorship"
# is NOT immigration context on its own ("conference sponsorship").
IMMIGRATION_TERM = re.compile(
    r"\b(?:visas?(?![-\s]free)|immigration|h-?1b|o-?1|e-?3|tn visa|green cards?|opt|stem opt|cpt|"
    r"work (?:authori[sz]ation|permits?)|employment authori[sz]ation|right to work|authori[sz]ed to work|"
    r"current or future sponsorship|employer sponsorship)\b|"
    # "Sponsorship ..." as the subject of a sentence in a job listing means visa sponsorship.
    r"^\W*sponsorship\b",
    _I,
)
# Label-style lines where bare "sponsorship" clearly means visa sponsorship.
SPONSOR_LABEL = re.compile(r"^\W*(?:visa |immigration )?sponsorship\s*[:\-–]\s*(yes|no|available|not available|unavailable)\b", _I)

# Clause-level negation (applies only within the clause mentioning sponsorship).
NEGATION = re.compile(
    r"\b(?:not|never|no longer|unable|cannot|ceased|stopped|unavailable|won't|without)\b|n't\b|"
    r"\bno (?:visa |immigration |h-?1b )?sponsorship\b|\bwill not be considered\b",
    _I,
)
# Hedges like "we cannot guarantee your visa" are not refusals.
HEDGE = re.compile(
    r"\b(?:cannot|can ?not|can't|do not|don't|does not|doesn't|not able to|unable to|won't)\s+(?:always\s+)?"
    r"(?:guarantee|promise|ensure)\w*|\bno guarantees?\b|\bnot guaranteed\b|\bisn't guaranteed\b",
    _I,
)


def has_negation(text: str) -> bool:
    return bool(NEGATION.search(HEDGE.sub(" ", text)))


CLAUSE_SPLIT = re.compile(r"\s*(?:;|,\s*(?:but|however|though|although|except)\b|\bbut\b|\bhowever\b|\bexcept\b)\s*", _I)
SPONSOR_WORD = re.compile(r"\bsponsor\w*\b", _I)

SPONSOR_NEG = [
    re.compile(r"\b(?:unable|not able|cannot|can ?not|can't|won't|will not|do not|don't|does not|doesn't|"
               r"are not|is not|aren't|isn't|no longer|never)\b[^.;]{0,40}?\bsponsor", _I),
    re.compile(r"\bno (?:visa |immigration |h-?1b )?sponsorship\b", _I),
    re.compile(r"\bsponsorship[^.;]{0,20}\b(?:not|un)\s?(?:available|offered|provided|possible)\b", _I),
    re.compile(r"\bsponsorship (?:is|isn't|is not)\s*(?:n't )?(?:available|offered)\b(?=[^.;]*\bn't\b)", _I),
    re.compile(r"\bwithout (?:the need for |requiring |needing )?(?:current or future |future |any )?"
               r"(?:visa |employer |immigration )?sponsorship\b", _I),
    re.compile(r"\bnot eligible for (?:visa |immigration )?sponsorship\b", _I),
    re.compile(r"\b(?:require|need)s? (?:visa |immigration |employer )?sponsorship\b[^.;]{0,40}\b(?:will not|won't|cannot|can't) be considered\b", _I),
    re.compile(r"\bstopped sponsoring\b|\bceased sponsoring\b", _I),
]

SPONSOR_CASE = [
    re.compile(r"\bsponsorship[^.;]{0,40}\bcase[- ]by[- ]case\b", _I),
    re.compile(r"\bcase[- ]by[- ]case\b[^.;]{0,60}\b(?:sponsor|visa)", _I),
    re.compile(r"\b(?:may|might|can sometimes) (?:be able to )?sponsor\b", _I),
    re.compile(r"\bsponsorship (?:may|might) be (?:available|considered|possible)\b", _I),
]

SPONSOR_POS = [
    re.compile(r"\b(?:happy|glad|able|willing|open|excited) to sponsor\b", _I),
    re.compile(r"\b(?:we|company) (?:will |can |do |does )?sponsors?\b[^.;]{0,30}\b(?:visas?|international|candidates|h-?1b|o-?1)\b", _I),
    re.compile(r"\b(?:visa|immigration|h-?1b|o-?1) sponsorship (?:is )?(?:available|offered|provided|supported)\b", _I),
    re.compile(r"\b(?:offer|provide|support)s? (?:full )?(?:visa|immigration|h-?1b|o-?1) (?:sponsorship|support|assistance)\b", _I),
    re.compile(r"\bwork hard to get you a visa\b", _I),
    re.compile(r"\b(?:been )?successful(?:ly)? (?:in )?sponsor\w*", _I),
    re.compile(r"\bsponsor(?:ing|s)? (?:visas?|international candidates|h-?1b|o-?1)\b", _I),
]

CITIZENSHIP = re.compile(
    r"\b(?:must be|requires?|required to be|only open to|limited to)\b[^.;]{0,30}?"
    r"\b(?:(?:a )?(?:u\.?s\.?|united states|uk|canadian|eu) (?:citizens?(?:hip)?|persons?)|citizens? of)\b|"
    r"\b(?:u\.?s\.?|united states) citizenship (?:is )?required\b|"
    r"\b(?:active |current )?(?:security|ts/sci|secret|top secret) clearance (?:is )?required\b|"
    r"\b(?:eligible|able) to obtain (?:and maintain )?(?:a |an )?(?:u\.?s\.? )?(?:security |secret |top secret )?clearance\b|"
    r"\bu\.?s\.? persons? (?:as defined|under) (?:by )?(?:itar|ear)\b",
    _I,
)

EXISTING_AUTH = re.compile(
    r"\b(?:must|should|need to|required to) (?:be |have )?(?:legally |currently )?"
    r"(?:authori[sz]ed|eligible|permitted|legally able) to work in (?:the )?(?:U\.?S\.?A?\b|UK\b|EU\b|[A-Z][a-z]+)|"
    r"\b(?:must|should) have (?:the )?(?:legal )?right to work in\b|"
    r"\bvalid work (?:authori[sz]ation|permit) (?:in|for)\b",
    _I,
)

RELOC_NOT_OFFERED = [
    re.compile(r"\b(?:no|not|unable to (?:offer|provide)|do not (?:offer|provide)|does not (?:offer|provide)|"
               r"cannot (?:offer|provide)|don't (?:offer|provide))\b[^.;]{0,20}\brelocation\b", _I),
    re.compile(r"\brelocation (?:assistance |support |package |benefits? )?(?:is |are )?(?:not|n't|unavailable|isn't)\b", _I),
    re.compile(r"\brelocation[^.;]{0,25}\b(?:not (?:available|offered|provided|covered)|unavailable|isn't (?:available|offered))\b", _I),
]
RELOC_ASSIST = [
    re.compile(r"\brelocation (?:assistance|support|package|stipend|bonus|reimbursement|benefits?)\b", _I),
    re.compile(r"\b(?:help|assist|support)s? (?:you )?(?:with )?relocat\w+\b", _I),
    re.compile(r"\brelocation (?:is |will be )?(?:available|offered|provided|covered|paid)\b", _I),
    re.compile(r"\b(?:cover|pay for|reimburse)s? (?:your )?relocation\b", _I),
]
RELOC_REQUIRED = [
    re.compile(r"\b(?:must|will need to|required to|willing to|open to|able to|need to) relocate\b", _I),
    re.compile(r"\brelocation (?:to [A-Z][\w .]+ )?(?:is )?required\b", _I),
]
RELOC_NEGATED = re.compile(r"\b(?:not|no|never|don't|doesn't|won't|isn't)\b[^.;]{0,25}\brelocat|n't\b[^.;]{0,25}\brelocat|\?", _I)

DAYS_IN_OFFICE = re.compile(
    r"\b(?:in[- ]?person|in[- ]office|in the office|on[- ]?site|onsite|in office)\b[^.;]{0,40}?"
    r"\b(\d)(?:\s*(?:-|–|to)\s*(\d))?\s*(?:days?|x)\s*(?:a|per|/)\s*week\b|"
    r"\b(\d)(?:\s*(?:-|–|to)\s*(\d))?\s*days?\s*(?:a|per|/)\s*week\b[^.;]{0,40}?"
    r"\b(?:in[- ]?person|in[- ]office|in the office|on[- ]?site|onsite|in office|at (?:our|the) (?:office|hq))\b",
    _I,
)
ONSITE = [
    re.compile(r"\b(?:fully|100%|strictly) (?:in[- ]person|on[- ]?site|in[- ]office)\b", _I),
    re.compile(r"\b(?:this|the) (?:role|position|job) is (?:an? )?(?:based )?(?:fully )?(?:in[- ]person|on[- ]?site|in[- ]office)\b", _I),
    re.compile(r"\b(?:in[- ]person|on[- ]?site|in[- ]office) (?:role|position)\b", _I),
    re.compile(r"\b(?:this is )?not (?:a )?remote(?: role| position)?\b", _I),
    re.compile(r"\bno remote\b", _I),
    re.compile(r"\bwork(?:s|ing)? in person\b", _I),
]
HYBRID = [
    re.compile(r"\bhybrid (?:work|working|schedule|model|arrangement|setup|policy|environment|role|position|team)\b", _I),
    re.compile(r"\b(?:this|the) (?:role|position|job) is hybrid\b", _I),
    re.compile(r"\bhybrid\b[^.;]{0,30}\b(?:office|in[- ]person|on[- ]?site|days)\b", _I),
    re.compile(r"\b(?:in[- ]office|in[- ]person|on[- ]?site)\b[^.;]{0,30}\bhybrid\b", _I),
]
# "MTS/Research-Software Hybrid Role" style compounds are not work arrangements.
HYBRID_FALSE = re.compile(
    r"[\w]+[-/][\w]+ hybrid\b|\b(?:research|software|engineering|design|product|technical|mts) hybrid\b", _I
)
REMOTE = [
    re.compile(r"\b(?:fully|100%|completely) remote\b", _I),
    re.compile(r"\bremote[- ](?:first|friendly)\b", _I),
    re.compile(r"\bwork from anywhere\b", _I),
    re.compile(r"\b(?:this|the) (?:role|position|job) is (?:a )?(?:fully )?remote\b", _I),
    re.compile(r"\bthis is a (?:fully )?remote (?:role|position|job)\b", _I),
    re.compile(r"\bopen to remote\b", _I),
]

GEO_LOCATED = re.compile(
    r"\b(?:must|should|need to|required to) (?:be )?(?:located|based|reside|residing|live|living) "
    r"(?:with)?in (?:the )?([A-Z][A-Za-z.]+(?: [A-Z][A-Za-z.]+){0,3})",
)
_REGION_ALT = r"US|U\.S\.|USA|United States|Canada|UK|EU|Europe|LATAM|EMEA|APAC|North America|Latin America"
GEO_ONLY = re.compile(
    rf"\b({_REGION_ALT})[- ]only\b"
    rf"|\b(?:remote|open to candidates|candidates) (?:with)?in (?:the )?({_REGION_ALT})\b(?:,? (?:or|and) (?:the )?({_REGION_ALT})\b)?",
)
TIMEZONE = re.compile(
    r"\b(?:GMT|UTC)\s?[+-−]\s?\d{1,2}\b[^.;]{0,30}?\b(?:GMT|UTC)\s?[+-−]\s?\d{1,2}\b|"
    r"\b(?:PST|PT|EST|ET|CET|Pacific|Eastern|Central European) (?:time ?zone|working hours|hours)\b|"
    r"\b(?:overlap|overlapping) (?:with )?[^.;]{0,30}?\b(?:time ?zones?|hours)\b|"
    r"\b(?:north american|us|european) time ?zones?\b",
    _I,
)

EMPLOYMENT = [
    ("internship", re.compile(r"\b(?:this is an? (?:paid )?internship|paid internship|\d+[- ](?:week|month) internship|internship (?:role|position) (?:is|for))\b", _I)),
    ("contract", re.compile(r"\b(?:contract(?:or)? (?:role|position)|(?:\d+|six|three|twelve)[- ]month contract|contract-to-hire)\b", _I)),
    ("part_time", re.compile(r"\bpart[- ]time (?:role|position)\b", _I)),
    ("full_time", re.compile(r"\bfull[- ]time (?:role|position|employee|employment|job)\b", _I)),
]

_META_EMPLOYMENT = {
    "fulltime": "full_time",
    "parttime": "part_time",
    "intern": "internship",
    "internship": "internship",
    "contract": "contract",
    "temporary": "temporary",
}

# Canonical skill -> regex alternatives. Word-bounded, case-insensitive.
SKILLS: dict[str, str] = {
    "Python": r"python", "TypeScript": r"typescript", "JavaScript": r"javascript",
    "Go": r"golang|go(?= ?(?:,|/|\)| and | or )|\s+services|\s+backend)", "Rust": r"rust(?! belt)",
    "Java": r"java(?!script)", "Kotlin": r"kotlin", "Swift": r"swift", "C++": r"c\+\+",
    "C#": r"c#", "Ruby": r"ruby", "Rails": r"rails|ruby on rails", "PHP": r"php", "Scala": r"scala",
    "Elixir": r"elixir", "SQL": r"sql", "React": r"react(?:\.js|js)?(?! native)",
    "React Native": r"react native", "Next.js": r"next\.?js", "Vue": r"vue(?:\.js)?",
    "Angular": r"angular", "Svelte": r"svelte", "Node.js": r"node(?:\.js|js)?",
    "Django": r"django", "FastAPI": r"fastapi", "Flask": r"flask", "GraphQL": r"graphql",
    "PostgreSQL": r"postgres(?:ql)?", "MySQL": r"mysql", "MongoDB": r"mongo(?:db)?",
    "Redis": r"redis", "Kafka": r"kafka", "Elasticsearch": r"elasticsearch",
    "AWS": r"aws|amazon web services", "GCP": r"gcp|google cloud", "Azure": r"azure",
    "Kubernetes": r"kubernetes|k8s", "Docker": r"docker", "Terraform": r"terraform",
    "Linux": r"linux", "PyTorch": r"pytorch", "TensorFlow": r"tensorflow", "JAX": r"jax",
    "CUDA": r"cuda", "LLMs": r"llms?|large language models?", "Machine learning": r"machine learning|\bml\b",
    "Computer vision": r"computer vision", "NLP": r"nlp|natural language processing",
    "Data engineering": r"data engineering|data pipelines?", "Spark": r"spark",
    "Figma": r"figma", "iOS": r"ios", "Android": r"android", "Tailwind": r"tailwind",
    "Solidity": r"solidity", "Distributed systems": r"distributed systems",
    "Embedded": r"embedded (?:systems|software|c)", "Robotics": r"robotics", "ROS": r"\bros2?\b",
    "Unity": r"unity(?= ?(?:3d|engine|game|developer|,|/| and | or |\)))","Unreal": r"unreal", "WebGL": r"webgl", "HTML/CSS": r"html|css",
}
_SKILL_RES = {name: re.compile(rf"(?<![\w+#.])(?:{pat})(?![\w+#])", _I) for name, pat in SKILLS.items()}


# ---------------------------------------------------------------------------
# Sentence classifiers (also reused by the validator on full sentences)
# ---------------------------------------------------------------------------


def classify_sponsorship(sentence: str) -> list[tuple[str, re.Match[str]]]:
    """Return sponsorship values stated by one sentence, with the matching span.

    Works clause by clause so "We sponsor O-1 visas, but cannot sponsor green
    cards" yields both 'offered' and 'not_offered' (-> needs clarification),
    and any negation in a clause blocks a positive reading of that clause.
    """
    out: list[tuple[str, re.Match[str]]] = []
    seen: set[str] = set()

    def add(v: str, m: re.Match[str]) -> None:
        if v not in seen:
            seen.add(v)
            out.append((v, m))

    label = SPONSOR_LABEL.search(sentence)
    if label:
        add("not_offered" if label.group(1).lower() in ("no", "not available", "unavailable") else "offered", label)

    has_immigration = bool(IMMIGRATION_TERM.search(sentence))
    if has_immigration or label:
        for clause in CLAUSE_SPLIT.split(sentence):
            if not clause or not (SPONSOR_WORD.search(clause) or re.search(r"\bget you a visa\b", clause, _I)):
                continue
            unhedged = HEDGE.sub(" ", clause)
            neg = next((m for p in SPONSOR_NEG if (m := p.search(unhedged))), None)
            if neg is None and has_negation(clause):
                neg = NEGATION.search(unhedged)
            if neg is not None:
                m = re.search(re.escape(clause), sentence) or neg
                add("not_offered", m)
                continue
            case = next((m for p in SPONSOR_CASE if (m := p.search(clause))), None)
            if case is not None:
                add("case_by_case", re.search(re.escape(clause), sentence) or case)
                continue
            pos = next((m for p in SPONSOR_POS if (m := p.search(clause))), None)
            if pos is not None:
                add("offered", re.search(re.escape(clause), sentence) or pos)

    m = CITIZENSHIP.search(sentence)
    if m:
        add("citizenship_required", m)
    elif not out:
        m = EXISTING_AUTH.search(sentence)
        if m:
            add("existing_authorization_required", m)
    return out


def classify_relocation(sentence: str) -> list[tuple[str, re.Match[str]]]:
    out: list[tuple[str, re.Match[str]]] = []
    m = next((m for p in RELOC_NOT_OFFERED if (m := p.search(sentence))), None)
    if m:
        out.append(("not_offered", m))
    else:
        m = next((m for p in RELOC_ASSIST if (m := p.search(sentence))), None)
        if m:
            out.append(("assistance_offered", m))
    if not RELOC_NEGATED.search(sentence):
        m = next((m for p in RELOC_REQUIRED if (m := p.search(sentence))), None)
        if m:
            out.append(("required", m))
    return out


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


class _Builder:
    def __init__(self) -> None:
        self.claims: list[Claim] = []
        self._n = 0
        self._seen: set[tuple[str, str]] = set()

    def add(
        self,
        category: ClaimCategory,
        value: str,
        evidence: str,
        source: str,
        confidence: float,
        extractor: str,
        dedupe_on_evidence: bool = False,
    ) -> None:
        key = (category.value, source, value.lower() + (("|" + evidence) if dedupe_on_evidence else ""))
        if key in self._seen:
            return
        self._seen.add(key)
        self._n += 1
        prefix = "m" if extractor == "metadata" else "r"
        self.claims.append(
            Claim(
                id=f"{prefix}{self._n}",
                category=category,
                value=value,
                evidence_text=evidence,
                evidence_source=source,  # type: ignore[arg-type]
                confidence=confidence,
                extractor=extractor,  # type: ignore[arg-type]
            )
        )


def extract_metadata(job: JobDetail, b: _Builder | None = None) -> list[Claim]:
    """Claims taken directly from structured listing fields."""
    b = b or _Builder()
    if job.location:
        b.add(ClaimCategory.job_location, job.location, job.location, "metadata.location", 1.0, "metadata")
        loc_low = job.location.lower()
        # "Remote – US", "Remote (Canada)", "Remote - PST Working Hours"
        if "remote" in loc_low:
            rest = re.sub(r"(?i)remote", "", job.location).strip(" -–—()/,:|")
            region = canonical_region(rest) if rest else None
            if region:
                b.add(ClaimCategory.geographic_restriction, region, job.location, "metadata.location", 0.9, "metadata")
            elif rest and TIMEZONE.search(job.location):
                b.add(ClaimCategory.geographic_restriction, f"Time zone: {rest}", job.location, "metadata.location", 0.9, "metadata")
    if job.workplace_type_raw:
        wp = normalize_workplace(job.workplace_type_raw)
        if wp:
            b.add(ClaimCategory.work_arrangement, wp, job.workplace_type_raw, "metadata.workplace_type", 1.0, "metadata")
    if job.employment_type:
        et = _META_EMPLOYMENT.get(job.employment_type.lower().replace("_", "").replace("-", "").replace(" ", ""))
        if et:
            b.add(ClaimCategory.employment_type, et, job.employment_type, "metadata.employment_type", 1.0, "metadata")
    return b.claims


def extract_description(text: str, b: _Builder | None = None) -> list[Claim]:
    b = b or _Builder()
    if not text:
        return b.claims
    skill_count = 0
    for seg in segments(text):
        s = seg.text

        # --- sponsorship ---
        for value, m in classify_sponsorship(s):
            conf = {"not_offered": 0.9, "offered": 0.85, "case_by_case": 0.8,
                    "citizenship_required": 0.85, "existing_authorization_required": 0.8}[value]
            b.add(ClaimCategory.sponsorship_policy, value, _clip(s, m), "description", conf, "rules")

        # --- relocation ---
        for value, m in classify_relocation(s):
            b.add(ClaimCategory.relocation_requirement, value, _clip(s, m), "description", 0.85 if value != "required" else 0.8, "rules")

        # --- work arrangement ---
        m = DAYS_IN_OFFICE.search(s)
        if m:
            nums = [int(g) for g in m.groups() if g]
            days = max(nums) if nums else 0
            value = "onsite" if days >= 5 else "hybrid"
            b.add(ClaimCategory.work_arrangement, value, _clip(s, m), "description", 0.85, "rules", dedupe_on_evidence=False)
        else:
            matched = False
            for value, pats in (("onsite", ONSITE), ("remote", REMOTE), ("hybrid", HYBRID)):
                for pat in pats:
                    m = pat.search(s)
                    if m and value == "hybrid" and HYBRID_FALSE.search(s):
                        continue
                    if m:
                        b.add(ClaimCategory.work_arrangement, value, _clip(s, m), "description", 0.75, "rules")
                        matched = True
                        break
                if matched:
                    break

        # --- geographic restriction ---
        m = GEO_LOCATED.search(s)
        if m:
            region = canonical_region(m.group(1)) or canonical_region(m.group(1).split()[0])
            if region:
                b.add(ClaimCategory.geographic_restriction, region, _clip(s, m), "description", 0.8, "rules")
        m = GEO_ONLY.search(s)
        if m:
            for raw in filter(None, m.groups()):
                region = canonical_region(raw)
                if region:
                    b.add(ClaimCategory.geographic_restriction, region, _clip(s, m), "description", 0.8, "rules")
        m = TIMEZONE.search(s)
        if m:
            b.add(ClaimCategory.geographic_restriction, f"Time zone: {m.group(0).strip()}", _clip(s, m), "description", 0.7, "rules")

        # --- employment type ---
        for value, pat in EMPLOYMENT:
            m = pat.search(s)
            if m:
                b.add(ClaimCategory.employment_type, value, _clip(s, m), "description", 0.7, "rules")
                break

        # --- technical requirements ---
        if skill_count < 30:
            for name, rx in _SKILL_RES.items():
                m = rx.search(s)
                if m:
                    before = len(b.claims)
                    b.add(ClaimCategory.technical_requirement, name, _clip(s, m), "description", 0.7, "rules")
                    if len(b.claims) > before:
                        skill_count += 1
    return b.claims


def extract_all(job: JobDetail) -> list[Claim]:
    b = _Builder()
    extract_metadata(job, b)
    extract_description(job.description_text or "", b)
    return b.claims


def job_country(job: JobDetail) -> str | None:
    return infer_country(job.location)
