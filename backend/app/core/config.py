from __future__ import annotations
from pydantic_settings import BaseSettings
from pydantic import model_validator


class Settings(BaseSettings):
    APP_NAME: str = "MA Analytics"
    DEBUG: bool = False

    DATABASE_URL: str = "postgresql://ma_analytics:ma_analytics@localhost:5434/ma_analytics"
    ASYNC_DATABASE_URL: str = ""
    REDIS_URL: str = "redis://localhost:6380/0"

    # Worker DB pool
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30

    SECRET_KEY: str = "change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    COOKIE_SECURE: bool = False

    CORS_ORIGINS: list[str] = ["http://localhost:3002", "http://localhost:5173"]

    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-haiku-4-5-20251001"
    GROQ_API_KEY: str = ""
    GROQ_API_KEY_2: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    RESEND_API_KEY: str = ""
    FRONTEND_URL: str = "http://localhost:3002"
    EMAIL_FROM: str = "noreply@ma-analytics.app"

    # Scraping rate limits per user
    SCRAPE_MAX_PER_HOUR: int = 5
    SCRAPE_MAX_REVIEWS: int = 250000

    class Config:
        env_file = ".env"

    @model_validator(mode="after")
    def derive_async_url(self) -> "Settings":
        if not self.ASYNC_DATABASE_URL:
            base = self.DATABASE_URL
            if base.startswith("postgresql+asyncpg://"):
                self.ASYNC_DATABASE_URL = base
            else:
                self.ASYNC_DATABASE_URL = base.replace(
                    "postgresql://", "postgresql+asyncpg://", 1
                )
        return self

    def validate_production(self) -> None:
        if self.SECRET_KEY == "change-me-in-production":
            raise RuntimeError(
                "SECRET_KEY is still the default value. "
                "Set a secure SECRET_KEY environment variable before running in production."
            )


settings = Settings()
