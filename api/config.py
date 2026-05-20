from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # ignore NEXT_PUBLIC_* and other frontend-only vars
    )

    # /tmp is the only writable directory on Vercel serverless functions.
    # For production set DATABASE_URL to a PostgreSQL connection string.
    DATABASE_URL: str = "sqlite+aiosqlite:////tmp/orders.db"

    # OpenAI for PDF patient extraction
    OPENAI_API_KEY: str = ""

    # API key auth — set a strong value in production
    API_KEY: str = "dev-api-key-change-me"

    # App metadata
    APP_NAME: str = "MedOrders API"
    VERSION: str = "1.0.0"
    DEBUG: bool = False

    # CORS origins; use comma-separated list in env or wildcard for dev
    ALLOWED_ORIGINS: List[str] = ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
