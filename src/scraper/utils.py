import datetime
import logging
import urllib.parse
from email.utils import parsedate_to_datetime
from typing import Any

logger = logging.getLogger(__name__)

# ============================================================
# Source ID mapping
# ============================================================
SOURCE_ID_MAP: dict[str, str] = {
    'reuters.com': 'reuters',
    'bbc.com': 'bbc',
    'apnews.com': 'ap',
    'washingtonpost.com': 'washington-post',
    'wsj.com': 'wsj',
    'hollywoodreporter.com': 'hollywood-reporter',
    'kcci.com': 'kcci',
    'mlb.com': 'mlb',
    'cbsnews.com': 'cbs-news',
    'cnn.com': 'cnn',
    'nbcnews.com': 'nbc-news',
    'nytimes.com': 'ny-times',
    'bloomberg.com': 'bloomberg',
    'aljazeera.com': 'al-jazeera-english',
    'channelnewsasia.com': 'cna',
    'straitstimes.com': 'straits-times',
    'marketwatch.com': 'marketwatch',
}

# ============================================================
# Schema validation
# ============================================================
REQUIRED_FIELDS = [
    'source_id', 'source_name', 'title', 'description',
    'url', 'published_at', 'scraped_at'
]


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


def normalize_timestamp(timestamp_str: str) -> str:
    """
    Converts various timestamp formats to ISO 8601 UTC (YYYY-MM-DDTHH:MM:SSZ).
    Handles: RFC 2822 (RSS), ISO 8601 (NewsAPI), and fallback.
    """
    if not timestamp_str:
        return ""

    ts = timestamp_str.strip()

    # 1. Try parsing RFC 2822 (e.g., "Tue, 01 Sep 2026 22:00:00 GMT")
    try:
        dt = parsedate_to_datetime(ts)
        return dt.strftime('%Y-%m-%dT%H:%M:%SZ')
    except (TypeError, ValueError):
        pass

    # 2. Try parsing ISO 8601 (e.g., "2026-09-01T03:24:09Z")
    try:
        if ts.endswith('Z'):
            ts = ts[:-1] + '+00:00'
        dt = datetime.datetime.fromisoformat(ts)
        return dt.strftime('%Y-%m-%dT%H:%M:%SZ')
    except (TypeError, ValueError):
        pass

    # 3. Fallback: return the original string (and let dbt handle it as a last resort)
    logger.debug(f"Unrecognized timestamp format: {ts}")
    return ts
