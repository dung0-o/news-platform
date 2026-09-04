"""Pydantic request/response models for the FastAPI backend."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class PredictResponse(BaseModel):
    """Response body for the /predict endpoint."""

    company: str
    days_analyzed: int
    average_sentiment: Optional[float] = None
    sentiment_label: Optional[str] = None
    trend: list[dict[str, object]] = []
    latest_articles: list[dict[str, object]] = []
    cache_hit: bool = False


class AnomalyResponse(BaseModel):
    """Response body for the /anomalies endpoint."""

    lookback_days: int
    threshold: float
    anomalies: list[dict[str, object]] = []


class HealthResponse(BaseModel):
    """Response body for the /health endpoint."""

    status: str = "healthy"
    timestamp: str = ""
    bigquery: str = "disconnected"
    redis: str = "disconnected"
    huggingface: str = "not_ready"


class ErrorResponse(BaseModel):
    """Standard error response."""

    detail: str
