"""Optional integration tests against the real speedrun API.

Run with:  pytest -m live
They are excluded from the default run and from CI's required checks.
"""

from __future__ import annotations

import pytest

from app.analysis import analyze
from app.config import Settings
from app.models import CandidatePreferences
from app.speedrun import SpeedrunClient

pytestmark = pytest.mark.live


@pytest.fixture
async def live():
    c = SpeedrunClient(Settings(_env_file=None))
    yield c
    await c.aclose()


async def test_live_list_and_detail_shapes(live):
    res = await live.list_jobs(q="engineer")
    assert res.total > 0 and res.jobs
    job = await live.get_job(res.jobs[0].id[:8])
    assert job.title and job.url.startswith("https://speedrun-talent-network.com/")


async def test_live_end_to_end_analysis(live):
    res = await live.list_jobs(q="software engineer")
    job = await live.get_job(res.jobs[0].id)
    out = await analyze(job, CandidatePreferences(country="Nigeria", sponsorship="yes"), None)
    ids = {c.id for c in out.extraction.claims}
    for f in out.location.findings + out.authorization.findings:
        assert set(f.evidence_claim_ids) <= ids
    for c in out.extraction.claims:
        if c.evidence_source == "description":
            assert c.evidence_text in (job.description_text or "")
