"""Orchestrator: run scrapers, validate, and upload to GCS."""

import datetime
import json
import logging
import os
import urllib.parse
from typing import Any

import google.auth
import google.cloud.storage

from config import GCS_BUCKET_NAME
from newsapi_scraper import scrape_newsapi
from google_news_scraper import scrape_google_news

logger = logging.getLogger(__name__)

REQUIRED_FIELDS = [
    "source_id",
    "source_name",
    "title",
    "description",
    "url",
    "published_at",
    "scraped_at",
]


# Source ID mapping for auto-detection from URLs
SOURCE_ID_MAP: dict[str, str] = {
    "reuters.com": "reuters",
    "bbc.com": "bbc",
    "apnews.com": "ap",
    "washingtonpost.com": "washington-post",
    "wsj.com": "wsj",
    "hollywoodreporter.com": "hollywood-reporter",
    "kcci.com": "kcci",
    "mlb.com": "mlb",
    "cbsnews.com": "cbs-news",
    "cnn.com": "cnn",
    "nbcnews.com": "nbc-news",
    "nytimes.com": "ny-times",
    "bloomberg.com": "bloomberg",
}


def _gcs_client() -> google.cloud.storage.Client:
    """Return a GCS client authenticated via Application Default Credentials."""
    _, project = google.auth.default()
    return google.cloud.storage.Client(project=project)


def _upload_jsonl(records: list[dict[str, Any]], date: str, hour: str) -> None:
    """Upload a JSONL file to GCS under the Bronze path.

    Args:
        records: List of validated record dicts.
        date: Date string in YYYY-MM-DD format.
        hour: Hour string in HH-MM format.
    """
    bucket = _gcs_client().bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(f"ingest_date={date}/{hour}.jsonl")
    blob.upload_from_string(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n",
        content_type="application/jsonl",
    )
    logger.info("Uploaded %d records to gcs://%s", len(records), GCS_BUCKET_NAME)


def set_source_id(item: dict[str, Any]) -> None:
    """Auto-detect source_id from URL if not already set.

    Args:
        item: Article dict to potentially populate source_id on.
    """
    if item.get("source_id"):
        return

    url = item.get("url", "")
    if "://" not in url:
        return

    parsed = urllib.parse.urlparse(url)
    domain = parsed.netloc.lower()
    if ":" in domain:
        domain = domain.split(":")[0]
    if domain.startswith("www."):
        domain = domain[4:]
    item["source_id"] = SOURCE_ID_MAP.get(domain, domain)


def validate_schema(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate all records against the required schema fields.

    Logs warnings for records with missing required fields and returns
    the list of validated records.

    Args:
        records: List of article dicts to validate.

    Returns:
        The same list with warnings logged for any issues found.
    """
    validated = []
    for i, record in enumerate(records):
        record_num = i + 1
        issues: list[str] = []

        for field in REQUIRED_FIELDS:
            if not record.get(field):
                issues.append(f"{field}: null/empty")

        if record.get("enrichment_attempted"):
            if not record.get("full_text"):
                issues.append("full_text: null/empty (enrichment attempted)")
            if not record.get("parsing_method"):
                issues.append("parsing_method: null/empty")

        if issues:
            logger.warning(
                "Record %d: missing fields - %s", record_num, ", ".join(issues)
            )

        validated.append(record)

    return validated


def main() -> None:
    """Run the full scraping pipeline: fetch → enrich → validate → upload."""
    current_datetime = datetime.datetime.now()
    ingest_date = current_datetime.strftime("%Y-%m-%d")
    ingest_hour = current_datetime.strftime("%H-%M")

    newsapi_output = scrape_newsapi()
    google_news_output = scrape_google_news()

    output = newsapi_output + google_news_output

    # Auto-detect source_id for records that don't have it
    for item in output:
        set_source_id(item)

    # Validate all records before writing
    validated_output = validate_schema(output)

    logger.info(
        "Pipeline: %d raw → %d uploaded", len(output), len(validated_output)
    )

    # Write JSONL to a local temp file first, then upload to GCS
    local_path = f"raw_data/ingest_date={ingest_date}/batch_{ingest_hour}.jsonl"
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    with open(local_path, "w", encoding="utf-8") as f:
        for item in validated_output:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    _upload_jsonl(validated_output, ingest_date, ingest_hour)


if __name__ == "__main__":
    main()
