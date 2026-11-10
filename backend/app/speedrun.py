"""Client for the public, read-only speedrun talent network API.

Verified against https://speedrun-talent-network.com/api/v1/openapi.json
(snapshot in docs/speedrun-openapi-snapshot.json, API version 1.4.0).

Only two endpoints are used: ``GET /api/v1/jobs`` and ``GET /api/v1/jobs/{id}``.
The host is fixed; callers can never make this service fetch an arbitrary URL.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any
from urllib.parse import quote

import httpx

from .cache import TTLCache
from .config import SPEEDRUN_BASE_URL, Settings
from .models import JobDetail, JobListResponse
from .normalize import normalize_job_detail, normalize_job_summary

log = logging.getLogger("orc.speedrun")

# Job UUID, 8-hex prefix, or canonical slug (see OpenAPI `id` parameter).
JOB_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{5,159}$")
WORKPLACE_VALUES = {"remote", "hybrid", "onsite"}


class SpeedrunError(Exception):
    """Base error for upstream problems."""

    status_code = 502


class SpeedrunNotFound(SpeedrunError):
    status_code = 404


class SpeedrunRateLimited(SpeedrunError):
    status_code = 503


class SpeedrunTimeout(SpeedrunError):
    status_code = 504


class SpeedrunBadData(SpeedrunError):
    status_code = 502


class InvalidJobId(ValueError):
    pass


def validate_job_id(job_id: str) -> str:
    job_id = job_id.strip()
    if not JOB_ID_RE.match(job_id):
        raise InvalidJobId("Job id must be a UUID, an 8-character prefix, or a job slug.")
    return job_id


class SpeedrunClient:
    def __init__(self, settings: Settings, http: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self._http = http or httpx.AsyncClient(
            base_url=SPEEDRUN_BASE_URL,
            timeout=httpx.Timeout(settings.speedrun_timeout_s),
            headers={
                # The API sits behind Cloudflare and rejects requests without a UA.
                "User-Agent": f"{settings.speedrun_source}/0.1 (+independent demo)",
                "Accept": "application/json",
            },
            follow_redirects=False,
        )
        self._list_cache: TTLCache[JobListResponse] = TTLCache(
            settings.jobs_cache_ttl_s, settings.cache_max_entries
        )
        self._detail_cache: TTLCache[JobDetail] = TTLCache(
            settings.detail_cache_ttl_s, settings.cache_max_entries
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _get_json(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        params = {**params, "source": self.settings.speedrun_source}
        attempts = self.settings.speedrun_max_retries + 1
        last_exc: Exception | None = None
        for attempt in range(attempts):
            try:
                resp = await self._http.get(path, params=params)
            except httpx.TimeoutException:
                last_exc = SpeedrunTimeout("The speedrun API timed out.")
                log.warning("speedrun timeout path=%s attempt=%d", path, attempt + 1)
            except httpx.HTTPError as exc:
                last_exc = SpeedrunError(f"Could not reach the speedrun API ({type(exc).__name__}).")
                log.warning("speedrun network error path=%s attempt=%d err=%s", path, attempt + 1, type(exc).__name__)
            else:
                if resp.status_code == 404:
                    raise SpeedrunNotFound("No job with that id.")
                if resp.status_code == 429:
                    raise SpeedrunRateLimited("The speedrun API is rate limiting requests. Try again shortly.")
                if resp.status_code >= 500:
                    last_exc = SpeedrunError(f"The speedrun API returned {resp.status_code}.")
                    log.warning("speedrun %d path=%s attempt=%d", resp.status_code, path, attempt + 1)
                elif resp.status_code >= 400:
                    raise SpeedrunError(f"The speedrun API rejected the request ({resp.status_code}).")
                else:
                    try:
                        data = resp.json()
                    except ValueError as exc:
                        raise SpeedrunBadData("The speedrun API returned invalid JSON.") from exc
                    if not isinstance(data, dict):
                        raise SpeedrunBadData("Unexpected response shape from the speedrun API.")
                    return data
            if attempt < attempts - 1:
                await asyncio.sleep(0.4 * (attempt + 1))
        assert last_exc is not None
        raise last_exc

    async def list_jobs(
        self, q: str | None = None, page: int = 0, workplace: str | None = None
    ) -> JobListResponse:
        q = (q or "").strip()[:120] or None
        page = max(0, min(int(page), 200))
        params: dict[str, Any] = {"page": page}
        if q:
            params["q"] = q
        if workplace:
            if workplace not in WORKPLACE_VALUES:
                raise ValueError("workplace must be remote, hybrid or onsite")
            params["wp"] = workplace
        key = f"{q}|{page}|{workplace}"
        cached = self._list_cache.get(key)
        if cached is not None:
            return cached

        data = await self._get_json("/api/v1/jobs", params)
        raw_jobs = data.get("jobs")
        if not isinstance(raw_jobs, list):
            raise SpeedrunBadData("The speedrun API response is missing the jobs list.")
        jobs = []
        for raw in raw_jobs:
            job = normalize_job_summary(raw)
            if job is not None:
                jobs.append(job)
            else:
                log.info("skipping malformed job record")
        result = JobListResponse(
            jobs=jobs,
            total=_as_int(data.get("total"), len(jobs)),
            page=_as_int(data.get("page"), page),
            total_pages=_as_int(data.get("total_pages"), 1),
            query=q,
        )
        self._list_cache.set(key, result)
        return result

    async def get_job(self, job_id: str) -> JobDetail:
        job_id = validate_job_id(job_id)
        cached = self._detail_cache.get(job_id)
        if cached is not None:
            return cached
        data = await self._get_json(f"/api/v1/jobs/{quote(job_id, safe='')}", {})
        raw = data.get("job")
        if not isinstance(raw, dict):
            raise SpeedrunBadData("The speedrun API response is missing the job object.")
        job = normalize_job_detail(raw)
        if job is None:
            raise SpeedrunBadData("The job record is missing required fields.")
        self._detail_cache.set(job_id, job)
        return job


def _as_int(v: Any, default: int) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default
