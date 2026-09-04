# Document 5: FastAPI Backend Specification

## Overview
FastAPI serves as the RESTful middleware between the dashboard (frontend) and the data warehouse + ML model. It handles authentication (optional for portfolio), caching, and orchestrates BigQuery queries and Hugging Face inference.

## Deployment Target
- Containerized with Docker, deployed on **Google Cloud Run** (free tier).
- Exposes a public HTTPS endpoint (e.g., `https://my-api-xxxx-uc.a.run.app`).

---

## Endpoint 1: `GET /predict`

**Description**: Returns sentiment trend and average score for a specific company over a given number of days.

**Request Parameters** (Query String):

| Parameter | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `company` | String | Yes | N/A | Company name (case-insensitive). Must match `company_entity` in Gold table. |
| `days` | Integer | No | 7 | Number of past days to analyze (max 90). |

**Example Request**:
```
GET /predict?company=Tesla&days=30
```

**Caching Logic (Upstash Redis)**:
- Cache Key: `predict:{company}:{days}` (e.g., `predict:tesla:30`).
- Cache TTL: **6 hours (21600 seconds)**.
- On cache miss: Query BigQuery → Call Hugging Face → Store result → Return.
- On cache hit: Return stored JSON directly (~5ms).

**Response Body (JSON)**:

```json
{
  "company": "Tesla",
  "days_analyzed": 30,
  "average_sentiment": 0.72,
  "sentiment_label": "Positive",
  "trend": [
    {"date": "2026-07-22", "avg_sentiment": 0.65, "article_count": 12},
    {"date": "2026-07-23", "avg_sentiment": 0.70, "article_count": 8},
    {"date": "2026-07-24", "avg_sentiment": 0.62, "article_count": 15}
    // ... continues for all 30 days
  ],
  "latest_articles": [
    {
      "title": "Tesla shares surge on record EV deliveries in Q3",
      "source": "Reuters",
      "published_at": "2026-08-21T14:30:00Z",
      "sentiment": 0.92,
      "url": "https://reuters.com/..."
    }
  ],
  "cache_hit": false
}
```

**Error Response (400)**:
```json
{
  "detail": "Company 'InvalidCo' not found in the last 90 days."
}
```

---

## Endpoint 2: `GET /anomalies`

**Description**: Returns articles with extreme sentiment shifts (high volatility) detected in the last N days. Useful for "breaking news" alerts.

**Request Parameters** (Query String):

| Parameter | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `days` | Integer | No | 1 | Lookback window in days. |
| `threshold` | Float | No | 0.5 | Sentiment change threshold to flag as anomaly. |

**Example Request**:
```
GET /anomalies?days=1&threshold=0.6
```

**Caching Logic**:
- Cache Key: `anomalies:{days}:{threshold}`.
- Cache TTL: **6 hours (21600 seconds)**.

**Response Body (JSON)**:

```json
{
  "lookback_days": 12,
  "anomalies": [
    {
      "article_id": "abc123",
      "title": "Apple faces supply chain disruption in China",
      "source": "Bloomberg",
      "published_at": "2026-08-21T10:00:00Z",
      "sentiment_score": -0.85,
      "previous_7day_avg": 0.45,
      "delta": -1.30
    }
  ]
}
```

---

## Endpoint 3: `GET /health`

**Description**: Simple health check for Cloud Run monitoring.

**Response**:
```json
{
  "status": "healthy",
  "timestamp": "2026-08-21T15:00:00Z",
  "bigquery": "connected",
  "redis": "connected",
  "huggingface": "ready"
}
```

---

## Environment Variables (Required for Deployment)

| Variable | Description |
| :--- | :--- |
| `GCP_PROJECT_ID` | Your Google Cloud project ID. |
| `BIGQUERY_DATASET` | Dataset name (e.g., `gold`). |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to service account JSON key. |
| `UPSTASH_REDIS_URL` | Full Redis connection string from Upstash. |
| `HUGGINGFACE_API_KEY` | API key for Hugging Face inference. |
| `HUGGINGFACE_MODEL_ID` | Model ID (e.g., `your-username/financial-bert-sentiment`). |

---

## BigQuery Query Logic (Pseudo-SQL for AI)

When `/predict` is called, the FastAPI backend executes:

```sql
SELECT 
  publish_date,
  AVG(sentiment_score) AS avg_sentiment,
  COUNT(*) AS article_count
FROM `my_project.gold.article_features`
WHERE LOWER(company_entity) = LOWER(@company)
  AND publish_date >= DATE_SUB(CURRENT_DATE(), INTERVAL @days DAY)
GROUP BY publish_date
ORDER BY publish_date ASC;
```

Then, for the latest 5 articles, run a separate query:

```sql
SELECT title, source_name, published_at, sentiment_score, url
FROM `my_project.gold.article_features`
WHERE LOWER(company_entity) = LOWER(@company)
ORDER BY published_at DESC
LIMIT 5;
```