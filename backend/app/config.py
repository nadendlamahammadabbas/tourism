"""Application configuration loaded from environment variables."""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Smriti global settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Core
    APP_ENV: Literal["dev", "test", "prod"] = "dev"
    DATABASE_URL: str = "postgresql+psycopg://smriti:smriti@localhost:5432/smriti"
    STORAGE_DIR: str = "./storage"
    CONTRIBUTOR_TOKEN: str = "change-me"
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # AI Configuration (never hard-code model IDs)
    LLM_MODE: Literal["fake", "live"] = "fake"
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-3.8-flash"
    GEMINI_MODEL_FALLBACK: str = "gemini-3.6-flash"
    EMBED_MODEL: str = "gemini-embedding-2"
    EMBED_MODEL_FALLBACK: str = "gemini-embedding-001"
    EMBED_DIM: int = 768
    PROMPT_VERSION: str = "v1"

    # Feature Flags
    FEATURE_3D: bool = True
    FEATURE_ASK: bool = True

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def storage_path(self) -> Path:
        p = Path(self.STORAGE_DIR)
        p.mkdir(parents=True, exist_ok=True)
        return p


settings = Settings()

