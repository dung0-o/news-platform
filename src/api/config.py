"""Application configuration from environment variables."""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """FastAPI application settings loaded from environment variables."""

    # --- Google Cloud ---
    gcp_project_id: str = Field(..., env="GCP_PROJECT_ID")
    bq_dataset_name: str = Field(..., env="BQ_DATASET_NAME")

    # --- Upstash Redis ---
    upstash_redis_url: str = Field(..., env="UPSTASH_REDIS_URL")
    upstash_redis_token: str = Field(..., env="UPSTASH_REDIS_TOKEN")

    # --- Hugging Face ---
    huggingface_api_key: str = Field(..., env="HUGGINGFACE_API_KEY")
    huggingface_model_id: str = Field(
        "distilbert/distilbert-base-uncased-finetuned-sst-2-english",
        env="HUGGINGFACE_MODEL_ID"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"


settings = Settings()
