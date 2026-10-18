"""SeeGuide Configuration Management
Loads centralized configuration settings using Pydantic Settings with .env file support.
"""

from functools import lru_cache
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration settings loaded from environment or .env file."""

    ENVIRONMENT: str = "local"
    LOG_LEVEL: str = "INFO"
    USE_MOCK_STORAGE: bool = True
    AWS_REGION: str = "us-east-1"
    DYNAMODB_TRACE_TABLE: str = "seeguide-traces"
    S3_BUCKET_NAME: str = "seeguide-assets"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )


@lru_cache
def get_settings() -> Settings:
    """Returns a cached singleton instance of application Settings."""
    return Settings()
