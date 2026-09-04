"""BigQuery connection and query helpers for FastAPI backend."""

from __future__ import annotations

import structlog
from google.cloud import bigquery
from google.api_core import exceptions as gcp_exceptions

from config import settings

logger = structlog.get_logger(__name__)

# ============================================================
# Client Initialization (uses ADC)
# ============================================================

def get_bigquery_client() -> bigquery.Client:
    """
    Return a BigQuery client using Application Default Credentials (ADC).
    On Cloud Run, this uses the service account attached to the instance.
    Locally, it uses gcloud auth application-default login or env vars.
    """
    try:
        client = bigquery.Client(project=settings.gcp_project_id)
        logger.info(
            "BigQuery client initialized",
            project=settings.gcp_project_id,
            dataset=settings.bq_dataset_name,
        )
        return client
    except Exception as exc:
        logger.error("Failed to initialize BigQuery client", error=str(exc))
        raise


# ============================================================
# Query: /predict
# ============================================================

def query_predict(company: str, days: int) -> dict:
    """
    Execute the /predict BigQuery query.

    Returns:
        {
            "trend": [{"date": "...", "avg_sentiment": 0.72, "article_count": 12}, ...],
            "latest": [{"title": "...", "source": "...", "publish_date": "...", "sentiment": 0.92, "url": "..."}, ...]
        }
    """
    client = get_bigquery_client()
    table_id = f"{settings.gcp_project_id}.{settings.bq_dataset_name}.gold_article_features"

    # --- Query 1: Sentiment trend per day ---
    trend_query = f"""
    SELECT
        CAST(publish_date AS STRING) AS date,
        ROUND(AVG(sentiment_score), 4) AS avg_sentiment,
        COUNT(*) AS article_count
    FROM `{table_id}`
    WHERE LOWER(title) LIKE CONCAT('%', LOWER(@company), '%')
        AND publish_date >= DATE_SUB(CURRENT_DATE(), INTERVAL @days DAY)
    GROUP BY publish_date
    ORDER BY publish_date ASC
    """

    trend_job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("company", "STRING", company),
            bigquery.ScalarQueryParameter("days", "INT64", days),
        ]
    )

    trend_results = list(client.query(trend_query, job_config=trend_job_config).result())

    trend = [
        {
            "date": row.date,
            "avg_sentiment": float(row.avg_sentiment) if row.avg_sentiment is not None else None,
            "article_count": row.article_count,
        }
        for row in trend_results
    ]

    # --- Query 2: Latest 5 articles for this company ---
    articles_query = f"""
    SELECT
        title,
        source_name AS source,
        CAST(publish_date AS STRING) AS publish_date,
        ROUND(sentiment_score, 4) AS sentiment,
        url
    FROM `{table_id}`
    WHERE LOWER(title) LIKE CONCAT('%', LOWER(@company), '%')
    ORDER BY publish_date DESC
    LIMIT 5
    """

    articles_job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("company", "STRING", company),
        ]
    )

    articles_results = list(client.query(articles_query, job_config=articles_job_config).result())

    latest = [
        {
            "title": row.title,
            "source": row.source,
            "publish_date": row.publish_date,
            "sentiment": float(row.sentiment) if row.sentiment is not None else None,
            "url": row.url,
        }
        for row in articles_results
    ]

    logger.info(
        "Predict query completed",
        company=company,
        days=days,
        trend_len=len(trend),
        articles_len=len(latest),
    )

    return {"trend": trend, "latest": latest}


# ============================================================
# Query: /anomalies
# ============================================================

def query_anomalies(days: int, threshold: float) -> list[dict]:
    """
    Find articles with extreme sentiment shifts in the lookback window.
    """
    client = get_bigquery_client()
    table_id = f"{settings.gcp_project_id}.{settings.bq_dataset_name}.gold_article_features"

    # Use a CTE to compute day-over-day sentiment shifts per company
    query = f"""
    WITH company_daily AS (
        SELECT
            company_entity,
            publish_date,
            ROUND(AVG(sentiment_score), 4) AS daily_avg,
            COUNT(*) AS article_count
        FROM `{table_id}`
        GROUP BY company_entity, publish_date
    ),
    with_shift AS (
        SELECT
            company_entity,
            publish_date,
            daily_avg,
            article_count,
            LAG(daily_avg, 1) OVER (
                PARTITION BY company_entity
                ORDER BY publish_date
            ) AS prev_day_avg,
            ROUND(
                ABS(daily_avg - LAG(daily_avg, 1) OVER (
                    PARTITION BY company_entity
                    ORDER BY publish_date
                )),
                4
            ) AS sentiment_shift
        FROM company_daily
    )
    SELECT
        company_entity AS company,
        CAST(publish_date AS STRING) AS date,
        prev_day_avg AS previous_7day_avg,
        daily_avg AS current_avg,
        sentiment_shift AS delta,
        article_count
    FROM with_shift
    WHERE sentiment_shift >= @threshold
        AND publish_date >= DATE_SUB(CURRENT_DATE(), INTERVAL @days DAY)
    ORDER BY sentiment_shift DESC
    LIMIT 50
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("days", "INT64", days),
            bigquery.ScalarQueryParameter("threshold", "FLOAT64", threshold),
        ]
    )

    results = list(client.query(query, job_config=job_config).result())

    anomalies = [
        {
            "company": row.company,
            "date": row.date,
            "previous_7day_avg": float(row.previous_7day_avg) if row.previous_7day_avg is not None else None,
            "current_avg": float(row.current_avg) if row.current_avg is not None else None,
            "delta": float(row.delta),
            "article_count": row.article_count,
        }
        for row in results
    ]

    logger.info(
        "Anomalies query completed",
        days=days,
        threshold=threshold,
        anomalies_found=len(anomalies),
    )

    return anomalies


# ============================================================
# Helper Functions
# ============================================================

def fetch_articles_for_company(company: str, days: int, null_only: bool = True) -> list[dict]:
    """
    Fetch articles for a company in the given date range.
    If null_only=True, only return articles where sentiment_score IS NULL.
    """
    client = get_bigquery_client()
    table_id = f"{settings.gcp_project_id}.{settings.bq_dataset_name}.gold_article_features"

    null_filter = "AND sentiment_score IS NULL" if null_only else ""
    query = f"""
    SELECT
        article_id,
        title,
        description,
        model_input_text,
        sentiment_score
    FROM `{table_id}`
    WHERE LOWER(title) LIKE CONCAT('%', LOWER(@company), '%')
        AND publish_date >= DATE_SUB(CURRENT_DATE(), INTERVAL @days DAY)
        {null_filter}
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("company", "STRING", company),
            bigquery.ScalarQueryParameter("days", "INT64", days),
        ]
    )
    results = list(client.query(query, job_config=job_config).result())
    return [dict(row) for row in results]


def update_article_sentiment(
    article_id: str,
    sentiment_score: float,
    sentiment_label: str,
    model_confidence: float,
) -> None:
    """Update the Gold table with the computed sentiment for a single article."""
    client = get_bigquery_client()
    table_id = f"{settings.gcp_project_id}.{settings.bq_dataset_name}.gold_article_features"

    query = f"""
    UPDATE `{table_id}`
    SET
        sentiment_score = @score,
        sentiment_label = @label,
        model_confidence = @confidence
    WHERE article_id = @article_id
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("score", "FLOAT64", sentiment_score),
            bigquery.ScalarQueryParameter("label", "STRING", sentiment_label),
            bigquery.ScalarQueryParameter("confidence", "FLOAT64", model_confidence),
            bigquery.ScalarQueryParameter("article_id", "STRING", article_id),
        ]
    )
    client.query(query, job_config=job_config).result()
    logger.debug("Updated sentiment", article_id=article_id, score=sentiment_score, label=sentiment_label)


# ============================================================
# Health check
# ============================================================

def check_bigquery_connection() -> bool:
    """Verify BigQuery connectivity by running a simple query."""
    try:
        client = get_bigquery_client()
        query = f"SELECT 1 as test FROM `{settings.gcp_project_id}.{settings.bq_dataset_name}.gold_article_features` LIMIT 1"
        results = list(client.query(query).result())
        return len(results) > 0
    except gcp_exceptions.NotFound:
        logger.warning("Gold table not found (empty dataset?)", dataset=settings.bq_dataset_name)
        return True  # Not an error, just empty
    except Exception as exc:
        logger.error("BigQuery health check failed", error=str(exc))
        return False
