"""Application configuration loaded from environment variables."""
from __future__ import annotations

from functools import lru_cache
from typing import Annotated, List

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # General
    ENVIRONMENT: str = "development"
    PROJECT_NAME: str = "TradingView AI Assistant"
    API_V1_PREFIX: str = "/api/v1"
    BACKEND_CORS_ORIGINS: Annotated[List[str], NoDecode] = ["http://localhost:5173", "http://localhost:3000", "*"]

    # Security
    SECRET_KEY: str = "insecure-dev-secret-change-me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"
    CREDENTIAL_ENCRYPTION_KEY: str = ""
    RATE_LIMIT_PER_MINUTE: int = 60

    # Database
    DATABASE_URL: str = "postgresql://trade_views_db_user:mn70C4maOIJ5kCiGk8wXFOvUp26R6WE9@dpg-d9ad0fmrnols73a2pim0-a.oregon-postgres.render.com/trade_views_db"

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # LLM
    LLM_PROVIDER: str = "openai"
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_TEMPERATURE: float = 0.2
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-6"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1"

    # News
    NEWS_API_KEY: str = ""

    # Playwright
    PLAYWRIGHT_HEADLESS: bool = True
    PLAYWRIGHT_TIMEOUT_MS: int = 45000
    # Use a system browser channel (e.g. "chrome" or "msedge") instead of the
    # bundled Chromium. Leave blank to use Playwright's downloaded Chromium.
    PLAYWRIGHT_CHANNEL: str = ""
    SCREENSHOT_DIR: str = "/data/screenshots"
    TRADINGVIEW_USERNAME: str = ""
    TRADINGVIEW_PASSWORD: str = ""

    # Email
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "no-reply@tvai.app"
    FRONTEND_RESET_URL: str = "http://localhost:5173/reset-password"

    # Seed admin
    FIRST_ADMIN_EMAIL: str = "admin@tvai.app"
    FIRST_ADMIN_PASSWORD: str = "Admin@12345"

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, v):
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
