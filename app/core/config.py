
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    PROJECT_NAME: str = "TaskHub"
    PROJECT_DESCRIPTION: str = "TaskHub — Hệ thống quản lý công việc (Task Management API)"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = True

    # Database: defaults to sqlite async for instant local dev & testing;
    # Can be overridden via env to postgresql+asyncpg://user:pass@localhost:5432/taskhub
    DATABASE_URL: str = "sqlite+aiosqlite:///./taskhub.db"

    # Redis Cache
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_DEFAULT_TTL_SECONDS: int = 120  # 2 minutes default cache

    # Security & JWT
    SECRET_KEY: str = "taskhub-secret-key-32-chars-long-secure-production-2026-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    BACKEND_CORS_ORIGINS: list[str] = ["*"]

    # Email / Notification
    SMTP_HOST: str | None = "localhost"
    SMTP_PORT: int | None = 1025
    EMAILS_FROM_EMAIL: str = "noreply@taskhub.local"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
