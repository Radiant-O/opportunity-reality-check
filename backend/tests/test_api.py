from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.speedrun import SpeedrunError, SpeedrunTimeout

from .conftest import FakeSpeedrun, raw_job

BODY = {
    "job_id": "ce7c0aae",
    "preferences": {"country": "Nigeria", "work_arrangement": "remote", "relocation": "yes", "sponsorship": "yes", "skills": ["Python"]},
}


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["llm_extraction"] == "disabled"


def test_list_jobs(client):
    r = client.get("/api/jobs", params={"q": "engineer"})
    assert r.status_code == 200
    data = r.json()
    assert data["jobs"][0]["company"] == "Acme"
    assert "speedrun" in data["attribution"]


def test_list_jobs_validates_workplace(client):
    assert client.get("/api/jobs", params={"workplace": "space"}).status_code == 422


def test_get_job(client):
    r = client.get("/api/jobs/ce7c0aae")
    assert r.status_code == 200 and r.json()["title"] == "Senior Software Engineer"


def test_get_job_not_found(client):
    assert client.get("/api/jobs/deadbeef").status_code == 404


def test_get_job_invalid_id(client):
    assert client.get("/api/jobs/a b").status_code == 422


def test_analyze_success(client):
    r = client.post("/api/analyze", json=BODY)
    assert r.status_code == 200, r.text
    data = r.json()
    assert set(data) >= {"job", "extraction", "technical", "location", "authorization", "assessment", "next_steps", "draft_inquiry", "disclaimer"}
    assert data["authorization"]["label"] == "not_specified"
    assert data["location"]["status"] == "conflict"  # remote pref vs hybrid
    assert data["technical"]["matched"][0]["skill"] == "Python"


def test_analyze_rejects_unknown_fields_and_bad_values(client):
    assert client.post("/api/analyze", json={**BODY, "url": "https://evil"}).status_code == 422
    bad = {**BODY, "preferences": {**BODY["preferences"], "sponsorship": "maybe"}}
    assert client.post("/api/analyze", json=bad).status_code == 422
    many = {**BODY, "preferences": {**BODY["preferences"], "skills": ["x"] * 21}}
    assert client.post("/api/analyze", json=many).status_code == 422


def test_analyze_upstream_errors(settings):
    fake = FakeSpeedrun({"ce7c0aae": raw_job()})
    c = TestClient(create_app(settings=settings, speedrun=fake))  # type: ignore[arg-type]
    fake.fail_with = SpeedrunTimeout("The speedrun API timed out.")
    assert c.post("/api/analyze", json=BODY).status_code == 504
    fake.fail_with = SpeedrunError("The speedrun API returned 500.")
    r = c.post("/api/analyze", json=BODY)
    assert r.status_code == 502 and "speedrun" in r.json()["detail"]


def test_analyze_closed_job(settings):
    fake = FakeSpeedrun({"ce7c0aae": raw_job(status="closed", description_text=None)})
    c = TestClient(create_app(settings=settings, speedrun=fake))  # type: ignore[arg-type]
    assert c.post("/api/analyze", json=BODY).status_code == 410


def test_analyze_is_cached(settings):
    fake = FakeSpeedrun({"ce7c0aae": raw_job()})
    c = TestClient(create_app(settings=settings, speedrun=fake))  # type: ignore[arg-type]
    c.post("/api/analyze", json=BODY)
    c.post("/api/analyze", json=BODY)
    assert len(c.app.state.analysis_cache) == 1


def test_rate_limit_on_analyze():
    s = Settings(anthropic_api_key=None, rate_limit_analyze_per_min=2, _env_file=None)
    c = TestClient(create_app(settings=s, speedrun=FakeSpeedrun({"ce7c0aae": raw_job()})))  # type: ignore[arg-type]
    codes = [c.post("/api/analyze", json=BODY).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_listing_clarity_pasted(client):
    r = client.post("/api/listing-clarity", json={
        "description_text": "Hybrid role, 3 days a week in our SF office. Full-time position. We use Python.",
        "location": "San Francisco, CA",
    })
    assert r.status_code == 200, r.text
    data = r.json()
    items = {i["dimension"]: i["status"] for i in data["items"]}
    assert items["sponsorship"] == "missing"
    assert items["relocation"] == "missing"
    assert items["work_arrangement"] == "clear"
    assert items["location"] == "clear"
    assert data["clear_count"] == 3 and data["total"] == 5


def test_listing_clarity_by_job_id(client):
    r = client.post("/api/listing-clarity", json={"job_id": "ce7c0aae"})
    assert r.status_code == 200 and r.json()["job"]["company"] == "Acme"


def test_listing_clarity_requires_input(client):
    assert client.post("/api/listing-clarity", json={}).status_code == 422
    assert client.post("/api/listing-clarity", json={"description_text": "x" * 15001}).status_code == 422


def test_logs_do_not_contain_preferences(client, caplog):
    import logging

    with caplog.at_level(logging.INFO):
        client.post("/api/analyze", json=BODY)
    text = " ".join(r.getMessage() + str(r.__dict__) for r in caplog.records)
    assert "Nigeria" not in text
    assert "sponsorship" not in text.lower() or "llm" in text.lower() and "Nigeria" not in text


def test_cors_allows_configured_origin(client):
    r = client.options("/api/jobs", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"
