# Project Architecture: Real-Time News Intelligence Platform

## One-Sentence Summary
An automated platform that scrapes financial news, processes it through a data lake + warehouse, analyzes sentiment via a fine-tuned BERT model, and serves insights via an interactive dashboard.

## Data Flow (High-Level)
1. **Scrape & Enrich** → GitHub Actions (cron) runs Python script to fetch news from NewsAPI and RSS feeds. Then, using `requests` and `BeautifulSoup`, it visits the article URLs to extract the **full HTML body text** (enrichment), augmenting the raw metadata with long-form content.
2. **Land** → Raw JSONL is stored in Google Cloud Storage (GCS) as the Bronze layer, partitioned by date.
3. **Transform (ELT)** → dbt (Data Build Tool) runs SQL in BigQuery to:
   - Clean and deduplicate raw data (Silver layer).
   - Aggregate and extract features (Gold layer: company entities, word counts, and a concatenated `model_input_text` using the enriched full text).
4. **Serve** → FastAPI backend on Google Cloud Run exposes endpoints:
   - `/predict?company=X&days=Y` → Returns sentiment trend and average score.
   - `/anomalies` → Returns articles with unusual sentiment shifts.
5. **Cache** → Upstash (Redis) caches model predictions for 6 hours to reduce API calls.
6. **Visualize** → Streamlit dashboard (deployed on Streamlit Cloud) queries FastAPI and BigQuery to display KPI tiles, time-series charts, and entity word clouds.

## Technology Stack
| Layer | Tool | Hosting |
| :--- | :--- | :--- |
| Orchestration | GitHub Actions (cron schedule) | GitHub (free) |
| Data Extraction (APIs) | `requests`, `feedparser`, `beautifulsoup4` | GitHub Runner |
| Data Lake (Bronze) | Google Cloud Storage (GCS) | GCP Free Tier (5 GB) |
| Data Warehouse (Silver/Gold) | Google BigQuery | GCP Free Tier (10 GB storage + 1 TB queries/mo) |
| Transformations | dbt Core | Runs locally, executes in BigQuery |
| Backend API | FastAPI | Google Cloud Run (2M requests/mo free) |
| Model Serving | Hugging Face Inference API | Hugging Face (free tier) |
| Cache | Upstash Redis | Upstash Free Tier (10k commands/day) |
| Dashboard | Streamlit | Streamlit Cloud (free) |
| Containerization | Docker | Local build, deployed to Cloud Run |

## Deployment Goal
The final output is a public-facing, interactive web application that allows users to:
- Search for any company and view its 30-day sentiment trend.
- Detect breaking news spikes and anomalous sentiment drops.
- Export filtered data as CSV for deeper analysis.