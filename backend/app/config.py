from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# The ONLY upstream host this service talks to (besides the optional LLM API).
SPEEDRUN_BASE_URL = "https://speedrun-talent-network.com"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # speedrun API
    speedrun_source: str = "opportunity-reality-check"
    speedrun_timeout_s: float = 12.0
    speedrun_max_retries: int = 2

    # Caching (seconds)
    jobs_cache_ttl_s: int = 120
    detail_cache_ttl_s: int = 600
    analysis_cache_ttl_s: int = 600
    cache_max_entries: int = 512

    # Rate limiting (per client IP, per minute)
    rate_limit_jobs_per_min: int = 60
    rate_limit_analyze_per_min: int = 12

    # Optional LLM extraction (Anthropic). Disabled when no key is set.
    anthropic_api_key: str | None = None
    llm_enabled: bool = True
    llm_model: str = "claude-opus-5-5"
    llm_effort: str = "low"
    llm_timeout_s: float = 25.0
    llm_max_tokens: int = 4000
    llm_max_input_chars: int = 12000
    llm_max_concurrency: int = 2
    llm_daily_call_cap: int = 300

    # CORS
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    log_level: str = "INFO"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def llm_active(self) -> bool:
        return bool(self.llm_enabled and self.anthropic_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
