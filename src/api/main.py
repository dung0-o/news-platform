"""FastAPI application factory for the News Intelligence Platform."""

from __future__ import annotations

import datetime as dt
import json
import structlog
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import ORJSONResponse
from fastapi.middleware.cors import CORSMiddleware

from database import (
    query_predict,
    query_anomalies,
    check_bigquery_connection,
    update_article_sentiment,
    fetch_articles_for_company,
)
from cache import get_redis_client
from hf_client import query_sentiment, health_check
from schemas import (
    PredictResponse,
    AnomalyResponse,
    HealthResponse,
    ErrorResponse,
)

logger = structlog.get_logger(__name__)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="News Intelligence Platform API",
        version="1.0.0",
        description="Real-time sentiment analysis for financial news.",
    )

    # CORS for Streamlit dashboard
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    redis = get_redis_client()

    # ---- /predict ----
    @app.get(
        "/predict",
        response_model=PredictResponse,
        tags=["sentiment"],
        summary="Get sentiment trend for a company",
    )
    def predict(
        company: str = Query(..., min_length=1, description="Company name (e.g. Tesla)"),
        days: int = Query(7, ge=1, le=90, description="Number of past days to analyze"),
    ) -> PredictResponse:
        """
        Return sentiment trend and latest articles for a company.

        Automatically computes sentiment for articles with NULL scores in the
        requested date range, updates the Gold table, and then returns the fresh data.
        """
        cache_key = f"predict:{company.lower()}:{days}"
        cached = redis.get(cache_key)

        # If cache hit, return directly (no need to re-compute)
        if cached:
            logger.info("Cache hit", cache_key=cache_key)
            return PredictResponse.model_validate_json(cached)

        logger.info("Cache miss — fetching fresh data", cache_key=cache_key)

        # ---- STEP 1: Fetch all articles with null sentiment for this company ----
        null_articles = fetch_articles_for_company(company, days, null_only=True)

        # ---- STEP 2: Compute sentiment for each null article ----
        if null_articles:
            logger.info(
                "Processing null sentiment articles",
                company=company,
                count=len(null_articles)
            )
            for article in null_articles:
                # Use title + description (or full text if available)
                text = article.get("model_input_text") or f"{article['title']}. {article['description']}"
                if not text:
                    continue

                # Call Hugging Face
                score = query_sentiment(text)
                if score:
                    label = "Positive" if score >= 0.5 else "Negative"
                    confidence = score
                    # Update the Gold table
                    update_article_sentiment(
                        article_id=article["article_id"],
                        sentiment_score=score,
                        sentiment_label=label,
                        model_confidence=confidence,
                    )
                    logger.debug("Updated sentiment", article_id=article["article_id"], score=score)
                else:
                    logger.warning("Sentiment failed", article_id=article["article_id"])

        # ---- STEP 3: Query the updated data (trend + latest 5) ----
        bq_result = query_predict(company=company, days=days)

        # ---- STEP 4: Build response ----
        trend = bq_result["trend"]
        latest_articles = bq_result["latest"]

        if trend:
            # Compute overall average from the trend (ignore None)
            valid_scores = [r["avg_sentiment"] for r in trend if r["avg_sentiment"] is not None]
            avg_sent = sum(valid_scores) / len(valid_scores) if valid_scores else None
            sentiment_label = "Positive" if avg_sent is not None and avg_sent >= 0 else "Negative" if avg_sent is not None else None
        else:
            avg_sent = None
            sentiment_label = None

        response = PredictResponse(
            company=company,
            days_analyzed=days,
            average_sentiment=round(avg_sent, 4) if avg_sent is not None else None,
            sentiment_label=sentiment_label,
            trend=trend,
            latest_articles=latest_articles,
            cache_hit=False,
        )

        # ---- STEP 5: Cache the response ----
        redis.set(cache_key, response.model_dump_json(), ttl=21600)  # 6 hours

        logger.info(
            "Predict completed",
            company=company,
            days=days,
            trend_len=len(trend),
            articles_len=len(latest_articles),
            null_processed=len(null_articles),
        )
        return response

    # ---- /anomalies ----
    @app.get(
        "/anomalies",
        response_model=AnomalyResponse,
        tags=["sentiment"],
        summary="Get anomalous sentiment shifts",
    )
    def anomalies(
        days: int = Query(24, ge=1, le=7, description="Lookback window in days"),
        threshold: float = Query(0.5, ge=0.1, le=5.0, description="Sentiment change threshold"),
    ) -> AnomalyResponse:
        """Return articles with extreme sentiment shifts (breaking news)."""
        cache_key = f"anomalies:{days}:{threshold}"
        cached = redis.get(cache_key)

        if cached:
            logger.info("Cache hit", cache_key=cache_key)
            return AnomalyResponse.model_validate_json(cached)

        logger.info("Cache miss — fetching anomalies", cache_key=cache_key)

        results = query_anomalies(days=days, threshold=threshold)
        enriched = []
        for anomaly in results:
            enriched.append({
                "article_id": f"agg_{anomaly['date']}",
                "title": f"Sentiment shift detected on {anomaly['date']}",
                "source": "aggregate",
                "published_at": str(anomaly["date"]),
                "sentiment_score": anomaly["previous_7day_avg"],
                "previous_7day_avg": anomaly["previous_7day_avg"],
                "delta": anomaly["delta"],
            })

        response = AnomalyResponse(
            lookback_days=days,
            threshold=threshold,
            anomalies=enriched,
        )

        redis.set(cache_key, response.model_dump_json(), ttl=21600)
        logger.info("Anomalies completed", days=days, threshold=threshold, count=len(enriched))
        return response

    # ---- /health ----
    @app.get(
        "/health",
        response_model=HealthResponse,
        tags=["system"],
        summary="Health check",
    )
    def health() -> HealthResponse:
        """Check connectivity to all backend services."""
        try:
            bq_connect = check_bigquery_connection()
            bq_status = "connected" if bq_connect else "disconnected"
        except Exception:
            bq_status = "disconnected"

        try:
            redis_client = get_redis_client()
            redis_client.get("health:test")
            redis_status = "connected"
        except Exception:
            redis_status = "disconnected"

        try:
            hf_ready = health_check()
            hf_status = "ready" if hf_ready else "loading"
        except Exception:
            hf_status = "error"

        return HealthResponse(
            status="healthy",
            timestamp=dt.datetime.utcnow().isoformat() + "Z",
            bigquery=bq_status,
            redis=redis_status,
            huggingface=hf_status,
        )

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8000)
