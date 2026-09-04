"""Dashboard-specific configuration loaded from environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Dashboard settings loaded from environment variables."""

    # --- API Backend ---
    api_url: str = Field(..., env="API_URL")

    # --- BigQuery ---
    gcp_project_id: str = Field(..., env="GCP_PROJECT_ID")
    bq_dataset_name: str = Field(..., env="BQ_DATASET_NAME")

    # --- Dashboard Defaults ---
    default_days: int = Field(7, env="DEFAULT_DAYS", ge=7, le=90)
    default_lookback_days: int = Field(1, env="DEFAULT_LOOKBACK_DAYS", ge=1, le=7)
    default_threshold: float = Field(0.5, env="DEFAULT_THRESHOLD", ge=0.1, le=5.0)
    max_companies: int = Field(50, env="MAX_COMPANIES", ge=1, le=200)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"


settings = Settings()
