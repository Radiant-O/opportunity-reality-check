from __future__ import annotations

import httpx
import pytest
import respx

from app.config import SPEEDRUN_BASE_URL, Settings
from app.speedrun import (
    InvalidJobId,
    SpeedrunBadData,
    SpeedrunClient,
    SpeedrunError,
    SpeedrunNotFound,
    SpeedrunRateLimited,
    SpeedrunTimeout,
)

from .conftest import raw_job

LIST_URL = f"{SPEEDRUN_BASE_URL}/api/v1/jobs"


def list_payload(jobs, total=None, page=0, total_pages=1):
    return {
        "jobs": jobs,
        "total": total if total is not None else len(jobs),
        "page": page,
        "page_size": 50,
        "total_pages": total_pages,
        "facets": {},
        "source": "opportunity-reality-check",
    }


@pytest.fixture
def client():
    s = Settings(speedrun_max_retries=2, _env_file=None)
    return SpeedrunClient(s)


@respx.mock
async def test_list_jobs_success_sends_source_and_user_agent(client):
    route = respx.get(LIST_URL).mock(return_value=httpx.Response(200, json=list_payload([raw_job()], total=2477, total_pages=50)))
    res = await client.list_jobs(q="engineer", page=0)
    assert res.total == 2477 and res.total_pages == 50
    assert res.jobs[0].title == "Senior Software Engineer"
    assert res.jobs[0].workplace_type == "hybrid"
    req = route.calls.last.request
    assert req.url.params["source"] == "opportunity-reality-check"
    assert req.url.params["q"] == "engineer"
    assert "opportunity-reality-check" in req.headers["user-agent"]


@respx.mock
async def test_list_jobs_pagination_and_workplace_filter(client):
    route = respx.get(LIST_URL).mock(return_value=httpx.Response(200, json=list_payload([], page=3, total_pages=5)))
    res = await client.list_jobs(q=None, page=3, workplace="remote")
    params = route.calls.last.request.url.params
    assert params["page"] == "3" and params["wp"] == "remote" and "q" not in params
    assert res.page == 3


async def test_list_jobs_rejects_unknown_workplace(client):
    with pytest.raises(ValueError):
        await client.list_jobs(workplace="moon")


@respx.mock
async def test_malformed_records_are_skipped(client):
    bad = {"id": "x", "title": None}  # missing required fields
    respx.get(LIST_URL).mock(return_value=httpx.Response(200, json=list_payload([bad, raw_job(), "nope"])))
    res = await client.list_jobs()
    assert len(res.jobs) == 1


@respx.mock
async def test_missing_jobs_list_is_bad_data(client):
    respx.get(LIST_URL).mock(return_value=httpx.Response(200, json={"total": 0}))
    with pytest.raises(SpeedrunBadData):
        await client.list_jobs()


@respx.mock
async def test_invalid_json_is_bad_data(client):
    respx.get(LIST_URL).mock(return_value=httpx.Response(200, text="<html>oops</html>"))
    with pytest.raises(SpeedrunBadData):
        await client.list_jobs()


@respx.mock
async def test_retries_on_5xx_then_succeeds(client):
    route = respx.get(LIST_URL).mock(
        side_effect=[httpx.Response(500), httpx.Response(502), httpx.Response(200, json=list_payload([raw_job()]))]
    )
    res = await client.list_jobs()
    assert len(res.jobs) == 1
    assert route.call_count == 3


@respx.mock
async def test_persistent_5xx_raises_after_bounded_retries(client):
    route = respx.get(LIST_URL).mock(return_value=httpx.Response(500))
    with pytest.raises(SpeedrunError):
        await client.list_jobs()
    assert route.call_count == 3  # 1 + 2 retries, never unbounded


@respx.mock
async def test_timeout_maps_to_speedrun_timeout(client):
    respx.get(LIST_URL).mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(SpeedrunTimeout):
        await client.list_jobs()


@respx.mock
async def test_network_error(client):
    respx.get(LIST_URL).mock(side_effect=httpx.ConnectError("down"))
    with pytest.raises(SpeedrunError):
        await client.list_jobs()


@respx.mock
async def test_rate_limited_is_not_retried(client):
    route = respx.get(LIST_URL).mock(return_value=httpx.Response(429))
    with pytest.raises(SpeedrunRateLimited):
        await client.list_jobs()
    assert route.call_count == 1


@respx.mock
async def test_list_results_are_cached(client):
    route = respx.get(LIST_URL).mock(return_value=httpx.Response(200, json=list_payload([raw_job()])))
    await client.list_jobs(q="eng")
    await client.list_jobs(q="eng")
    assert route.call_count == 1


@respx.mock
async def test_get_job_detail_normalizes_fields(client):
    respx.get(f"{LIST_URL}/ce7c0aae").mock(return_value=httpx.Response(200, json={"job": raw_job(workplace_type="OnSite")}))
    job = await client.get_job("ce7c0aae")
    assert job.workplace_type == "onsite"
    assert job.workplace_type_raw == "OnSite"
    assert job.apply_url == "https://jobs.example.com/acme/123"
    # canonical link: tracking params stripped, our attribution added
    assert job.url.startswith("https://speedrun-talent-network.com/jobs/senior-software-engineer-acme-ce7c0aae?")
    assert "utm_source=opportunity-reality-check" in job.url


@respx.mock
async def test_get_job_404(client):
    respx.get(f"{LIST_URL}/deadbeef").mock(return_value=httpx.Response(404, json={"error": "not found"}))
    with pytest.raises(SpeedrunNotFound):
        await client.get_job("deadbeef")


@respx.mock
async def test_get_job_missing_job_object(client):
    respx.get(f"{LIST_URL}/deadbeef").mock(return_value=httpx.Response(200, json={"source": "x"}))
    with pytest.raises(SpeedrunBadData):
        await client.get_job("deadbeef")


@respx.mock
async def test_closed_job_has_no_description(client):
    respx.get(f"{LIST_URL}/deadbeef").mock(
        return_value=httpx.Response(200, json={"job": raw_job(status="closed", description_text=None, apply=None)})
    )
    job = await client.get_job("deadbeef")
    assert job.status == "closed" and job.description_text is None and job.apply_url is None


@pytest.mark.parametrize(
    "bad_id",
    ["../../etc/passwd", "https://evil.example.com", "abc", "a b c d e f", "x" * 300, "id?x=1", "%2e%2e/"],
)
async def test_rejects_ids_that_could_reach_other_urls(client, bad_id):
    with pytest.raises(InvalidJobId):
        await client.get_job(bad_id)
