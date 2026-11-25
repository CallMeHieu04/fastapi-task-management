from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration settings."""

    PROJECT_NAME: str = "TaskHub"
    PROJECT_DESCRIPTION: str = "TaskHub API — Task Management System"
    VERSION: str = "0.3.0"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = True
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # Database Configuration (SQLAlchemy 2.x async)
    DATABASE_URL: str = "sqlite+aiosqlite:///./taskhub.db"
    DB_ECHO: bool = False

    # Security & JWT Configuration (No hardcoded default secret key)
    SECRET_KEY: str = Field(
        ...,
        min_length=32,
        description="JWT Secret key must be at least 32 characters",
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Cache Configuration (Redis with graceful in-memory fallback)
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_TTL_SECONDS: int = 120
    CACHE_ENABLED: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()  # type: ignore[call-arg]
