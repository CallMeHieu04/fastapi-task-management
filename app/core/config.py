from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration settings."""

    PROJECT_NAME: str = "TaskHub"
    PROJECT_DESCRIPTION: str = "TaskHub API — Task Management System"
    VERSION: str = "0.2.0"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = True
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # Database Configuration (SQLAlchemy 2.x async)
    DATABASE_URL: str = "sqlite+aiosqlite:///./taskhub.db"
    DB_ECHO: bool = False

    # Security Configuration
    SECRET_KEY: str = Field(
        default="taskhub-secret-key-32-chars-long-secure-production-2026-key",
        min_length=32,
        description="JWT Secret key must be at least 32 characters",
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
