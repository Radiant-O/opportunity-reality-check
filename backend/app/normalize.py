"""Normalize raw speedrun API job records into our models.

The API is defensive-parsed: unknown fields are ignored, missing optional fields
become ``None``, and records missing required fields are dropped.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit, urlunsplit

from .models import JobDetail, JobSummary

_WORKPLACE_MAP = {
    "onsite": "onsite",
    "on-site": "onsite",
    "on site": "onsite",
    "in office": "onsite",
    "in-office": "onsite",
    "hybrid": "hybrid",
    "remote": "remote",
}


def normalize_workplace(raw: Any) -> str | None:
    """'OnSite' / 'Onsite' / 'On-site' -> 'onsite' (the API mixes casings)."""
    if not isinstance(raw, str):
        return None
    key = raw.strip().lower()
    if key in _WORKPLACE_MAP:
        return _WORKPLACE_MAP[key]
    key = key.replace("_", "").replace("-", "").replace(" ", "")
    return {"onsite": "onsite", "hybrid": "hybrid", "remote": "remote"}.get(key)


def _str(v: Any, max_len: int = 500) -> str | None:
    if v is None:
        return None
    if not isinstance(v, (str, int, float)):
        return None
    s = str(v).strip()
    return s[:max_len] if s else None


def _clean_url(v: Any) -> str | None:
    """Accept only https speedrun-talent-network.com URLs for canonical links;
    strip tracking query params so we link to the canonical page."""
    s = _str(v, 2000)
    if not s:
        return None
    parts = urlsplit(s)
    if parts.scheme != "https" or not parts.netloc:
        return None
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _with_attribution(url: str) -> str:
    return f"{url}?utm_source=opportunity-reality-check&utm_medium=referral"


def _https_url(v: Any) -> str | None:
    s = _str(v, 2000)
    if not s:
        return None
    parts = urlsplit(s)
    if parts.scheme != "https" or not parts.netloc:
        return None
    return s


def _base_fields(raw: dict[str, Any]) -> dict[str, Any] | None:
    job_id = _str(raw.get("id"), 80)
    title = _str(raw.get("title"), 300)
    company = _str(raw.get("company"), 200)
    url = _clean_url(raw.get("url"))
    if not (job_id and title and company and url):
        return None
    wp_raw = _str(raw.get("workplace_type"), 40)
    remote = raw.get("remote") is True
    return {
        "id": job_id,
        "title": title,
        "company": company,
        "company_url": _https_url(raw.get("company_url")),
        "location": _str(raw.get("location"), 200),
        "workplace_type": normalize_workplace(wp_raw),
        "workplace_type_raw": wp_raw,
        "employment_type": _str(raw.get("employment_type"), 40),
        "function": _str(raw.get("function"), 40),
        "seniority": _str(raw.get("seniority"), 40),
        "remote": remote,
        "published_at": _str(raw.get("published_at"), 40),
        "url": _with_attribution(url),
    }


def normalize_job_summary(raw: Any) -> JobSummary | None:
    if not isinstance(raw, dict):
        return None
    base = _base_fields(raw)
    return JobSummary(**base) if base else None


def normalize_job_detail(raw: Any) -> JobDetail | None:
    if not isinstance(raw, dict):
        return None
    base = _base_fields(raw)
    if not base:
        return None
    apply = raw.get("apply") if isinstance(raw.get("apply"), dict) else None
    apply_kind = apply.get("kind") if apply and apply.get("kind") in ("onsite", "external") else None
    status = raw.get("status") if raw.get("status") in ("open", "closed") else "open"
    desc = raw.get("description_text")
    desc = desc if isinstance(desc, str) and desc.strip() else None
    return JobDetail(
        **base,
        status=status,
        apply_url=_https_url(apply.get("url")) if apply else None,
        apply_kind=apply_kind,
        comp_summary=_str(raw.get("comp_summary"), 200),
        description_text=desc[:15000] if desc else None,
    )
