"""FastAPI entrypoint for Opportunity Reality Check."""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .analysis import analyze
from .cache import TTLCache
from .clarity import evaluate_clarity
from .config import Settings, get_settings
from .extraction.llm import LLMExtractor
from .extraction.pipeline import run_extraction
from .models import (
    AnalysisResponse,
    AnalyzeRequest,
    ClarityRequest,
    ClarityResponse,
    ExtractionReport,
    JobDetail,
    JobListResponse,
    JobSummary,
)
from .ratelimit import RateLimiter
from .speedrun import InvalidJobId, SpeedrunClient, SpeedrunError

log = logging.getLogger("orc.api")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {"level": record.levelname, "logger": record.name, "msg": record.getMessage()}
        for key in ("request_id", "path", "status", "duration_ms", "event"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload)


def _configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    # uvicorn's access log records client IPs and query strings; keep it off.
    logging.getLogger("uvicorn.access").disabled = True


def create_app(
    settings: Settings | None = None,
    speedrun: SpeedrunClient | None = None,
    llm: LLMExtractor | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    _configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        await app.state.speedrun.aclose()

    app = FastAPI(
        title="Opportunity Reality Check API",
        version="0.1.0",
        description="Independent demo. Not affiliated with a16z speedrun.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.speedrun = speedrun or SpeedrunClient(settings)
    app.state.llm = llm if llm is not None else LLMExtractor(settings)
    app.state.analysis_cache = TTLCache[AnalysisResponse](settings.analysis_cache_ttl_s, settings.cache_max_entries)
    # Extraction (the only step that may call the LLM) doesn't depend on
    # preferences, so it is cached per job: varying preferences can't drive spend.
    app.state.extraction_cache = TTLCache[ExtractionReport](settings.analysis_cache_ttl_s, settings.cache_max_entries)
    app.state.limiter_jobs = RateLimiter(settings.rate_limit_jobs_per_min, 60)
    app.state.limiter_analyze = RateLimiter(settings.rate_limit_analyze_per_min, 60)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_origin_regex=r"https://([a-z0-9-]+\.)?opportunity-reality-check\.pages\.dev",
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.middleware("http")
    async def request_log(request: Request, call_next):
        # Privacy: log only method/path/status/timing. Never bodies, query
        # strings, or client IPs (candidate preferences live in the body).
        rid = uuid.uuid4().hex[:12]
        start = time.perf_counter()
        response = await call_next(request)
        log.info(
            "request",
            extra={
                "request_id": rid,
                "path": f"{request.method} {request.url.path}",
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - start) * 1000),
            },
        )
        response.headers["X-Request-Id"] = rid
        return response

    @app.exception_handler(SpeedrunError)
    async def _speedrun_error(_: Request, exc: SpeedrunError):
        return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})

    @app.exception_handler(InvalidJobId)
    async def _invalid_id(_: Request, exc: InvalidJobId):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    def _client_key(request: Request) -> str:
        # X-Forwarded-For is client-controlled unless a trusted proxy sets it.
        # Only when configured, use the right-most hop (appended by our proxy).
        ip = request.client.host if request.client else "unknown"
        if settings.trust_x_forwarded_for:
            hops = [h.strip() for h in request.headers.get("x-forwarded-for", "").split(",") if h.strip()]
            if hops:
                ip = hops[-1]
        return hashlib.sha256(ip.encode()).hexdigest()[:16]

    def _limit(limiter: RateLimiter, request: Request) -> None:
        if not limiter.allow(_client_key(request)):
            raise HTTPException(status_code=429, detail="Too many requests. Please wait a minute and try again.")

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "llm_extraction": "enabled" if app.state.llm.enabled else "disabled",
            "version": app.version,
        }

    @app.get("/api/jobs", response_model=JobListResponse)
    async def list_jobs(
        request: Request,
        q: str | None = Query(default=None, max_length=120),
        page: int = Query(default=0, ge=0, le=200),
        workplace: Literal["remote", "hybrid", "onsite"] | None = None,
    ):
        _limit(app.state.limiter_jobs, request)
        return await app.state.speedrun.list_jobs(q=q, page=page, workplace=workplace)

    @app.get("/api/jobs/{job_id}", response_model=JobDetail)
    async def get_job(job_id: str, request: Request):
        _limit(app.state.limiter_jobs, request)
        return await app.state.speedrun.get_job(job_id)

    @app.post("/api/analyze", response_model=AnalysisResponse)
    async def analyze_job(body: AnalyzeRequest, request: Request):
        _limit(app.state.limiter_analyze, request)
        job = await app.state.speedrun.get_job(body.job_id)
        if job.status == "closed":
            raise HTTPException(status_code=410, detail="This listing is closed and can no longer be analyzed.")
        key = hashlib.sha256(f"{job.id}|{body.preferences.model_dump_json()}".encode()).hexdigest()
        cached = app.state.analysis_cache.get(key)
        if cached is not None:
            return cached
        report = app.state.extraction_cache.get(job.id)
        if report is None:
            report = await run_extraction(job, app.state.llm)
            app.state.extraction_cache.set(job.id, report)
        result = await analyze(job, body.preferences, app.state.llm, report=report)
        app.state.analysis_cache.set(key, result)
        log.info("analysis", extra={"event": "analysis_complete", "status": result.extraction.llm_status})
        return result

    @app.post("/api/listing-clarity", response_model=ClarityResponse)
    async def listing_clarity(body: ClarityRequest, request: Request):
        _limit(app.state.limiter_analyze, request)
        summary: JobSummary | None = None
        if body.job_id:
            job = await app.state.speedrun.get_job(body.job_id)
            summary = JobSummary(**job.model_dump(include=set(JobSummary.model_fields)))
        elif body.description_text and body.description_text.strip():
            job = JobDetail(
                id="pasted",
                title="Pasted listing",
                company="Your company",
                url="https://speedrun-talent-network.com/jobs",
                location=(body.location or None),
                workplace_type_raw=body.workplace_type or None,
                employment_type=body.employment_type or None,
                description_text=body.description_text,
            )
        else:
            raise HTTPException(status_code=422, detail="Provide either job_id or description_text.")
        # Clarity uses deterministic extraction only: no LLM spend on pasted text.
        report = await run_extraction(job, None)
        items = evaluate_clarity(job, report)
        clear = sum(1 for i in items if i.status == "clear")
        return ClarityResponse(
            items=items,
            clear_count=clear,
            total=len(items),
            extraction=report,
            job=summary,
            note="This reports what the listing communicates. It never assumes your company's actual policies.",
        )

    return app


app = create_app()
