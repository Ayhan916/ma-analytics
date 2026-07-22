from __future__ import annotations
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "MA Analytics"
    DEBUG: bool = False

    DATABASE_URL: str = "postgresql://ma_analytics:ma_analytics@localhost:5434/ma_analytics"
    REDIS_URL: str = "redis://localhost:6380/0"

    SECRET_KEY: str = "change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    CORS_ORIGINS: list[str] = ["http://localhost:3002", "http://localhost:5173"]

    GROQ_API_KEY: str = ""
    RESEND_API_KEY: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
