from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.models import CandidatePreferences, JobDetail, JobListResponse
from app.normalize import normalize_job_detail, normalize_job_summary
from app.speedrun import SpeedrunNotFound, SpeedrunTimeout


def raw_job(**overrides: Any) -> dict[str, Any]:
    base = {
        "id": "ce7c0aae-d3cc-4623-bb07-8203c7c9d5df",
        "status": "open",
        "url": "https://speedrun-talent-network.com/jobs/senior-software-engineer-acme-ce7c0aae?utm_source=x",
        "title": "Senior Software Engineer",
        "company": "Acme",
        "company_slug": "acme",
        "company_url": "https://speedrun-talent-network.com/companies/acme",
        "tier": "speedrun",
        "stealth": False,
        "location": "San Francisco, CA",
        "workplace_type": "Hybrid",
        "employment_type": "FullTime",
        "function": "engineering",
        "seniority": "senior",
        "remote": False,
        "comp_summary": None,
        "published_at": "2026-10-01",
        "apply": {"kind": "external", "url": "https://jobs.example.com/acme/123"},
        "description_text": "We build developer tools. You will write Python and TypeScript.",
        "labels": None,
    }
    base.update(overrides)
    return base


def make_job(**overrides: Any) -> JobDetail:
    job = normalize_job_detail(raw_job(**overrides))
    assert job is not None
    return job


def prefs(**kw: Any) -> CandidatePreferences:
    return CandidatePreferences(**kw)


class FakeSpeedrun:
    """In-memory stand-in for SpeedrunClient used by API tests."""

    def __init__(self, jobs: dict[str, dict[str, Any]] | None = None) -> None:
        self.jobs = jobs or {}
        self.fail_with: Exception | None = None
        self.calls = 0

    async def list_jobs(self, q=None, page=0, workplace=None) -> JobListResponse:
        self.calls += 1
        if self.fail_with:
            raise self.fail_with
        items = [normalize_job_summary(j) for j in self.jobs.values()]
        items = [i for i in items if i and (not q or q.lower() in i.title.lower())]
        return JobListResponse(jobs=items, total=len(items), page=page, total_pages=1, query=q)

    async def get_job(self, job_id: str) -> JobDetail:
        from app.speedrun import validate_job_id

        self.calls += 1
        validate_job_id(job_id)
        if self.fail_with:
            raise self.fail_with
        for key, raw in self.jobs.items():
            if raw["id"] == job_id or raw["id"].startswith(job_id) or key == job_id:
                job = normalize_job_detail(raw)
                assert job
                return job
        raise SpeedrunNotFound("No job with that id.")

    async def aclose(self) -> None:
        pass


@pytest.fixture
def settings() -> Settings:
    return Settings(anthropic_api_key=None, rate_limit_analyze_per_min=1000, rate_limit_jobs_per_min=1000, _env_file=None)


@pytest.fixture
def fake_speedrun() -> FakeSpeedrun:
    return FakeSpeedrun({"ce7c0aae": raw_job()})


@pytest.fixture
def client(settings: Settings, fake_speedrun: FakeSpeedrun) -> TestClient:
    app = create_app(settings=settings, speedrun=fake_speedrun)  # type: ignore[arg-type]
    return TestClient(app)


__all__ = ["raw_job", "make_job", "prefs", "FakeSpeedrun", "SpeedrunTimeout"]
