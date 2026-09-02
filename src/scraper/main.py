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
from utils import set_source_id, validate_schema

logger = logging.getLogger(__name__)


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
