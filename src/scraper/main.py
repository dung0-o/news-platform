from newsapi_scraper import scrape_newsapi
from google_news_scraper import scrape_google_news

import datetime
import json
import os
import logging
import urllib.parse

logger = logging.getLogger(__name__)

REQUIRED_FIELDS = ['source_id', 'source_name', 'title', 'description', 'url', 'published_at', 'scraped_at']


# Source ID mapping for auto-detection from URLs
SOURCE_ID_MAP = {
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
}


def set_source_id(item: dict) -> None:
    """Auto-detect source_id from URL if not already set."""
    if item.get('source_id'):
        return
    url = item.get('url', '')
    if '://' not in url:
        return
    # Get the domain part of the URL
    parsed = urllib.parse.urlparse(url)
    domain = parsed.netloc.lower()
    # Remove port numbers and www prefix
    if ':' in domain:
        domain = domain.split(':')[0]
    if domain.startswith('www.'):
        domain = domain[4:]
    # Try to get a clean source_id
    item['source_id'] = SOURCE_ID_MAP.get(domain, domain)


def validate_schema(records: list[dict]) -> list[dict]:
    """Validate all records against the required schema fields.

    Logs warnings for records with missing required fields and returns
    the list (modifications are logged, not changed).
    """
    validated = []
    for i, record in enumerate(records):
        record_num = i + 1
        issues = []

        # Check required fields
        for field in REQUIRED_FIELDS:
            if not record.get(field):
                issues.append(f"{field}: null/empty")

        # Check enrichment fields if attempted
        if record.get('enrichment_attempted'):
            if not record.get('full_text'):
                issues.append(f"full_text: null/empty (enrichment attempted)")
            if not record.get('parsing_method'):
                issues.append(f"parsing_method: null/empty")

        if issues:
            logger.warning(
                f"Record {record_num}: missing fields - {', '.join(issues)}"
            )

        validated.append(record)

    return validated

def main():
    current_datetime = datetime.datetime.now()
    ingest_date = current_datetime.strftime('%Y-%m-%d')
    ingest_hour = current_datetime.strftime('%H-%M')

    newsapi_output = scrape_newsapi()
    google_news_output = scrape_google_news()

    output = newsapi_output + google_news_output

    # Auto-detect source_id for records that don't have it
    for item in output:
        set_source_id(item)

    # Validate all records before writing
    validated_output = validate_schema(output)

    output_dir = f'raw_data/ingest_date={ingest_date}'
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    output_file = f'{output_dir}/batch_{ingest_hour}.jsonl'
    with open(output_file, 'w', encoding='utf-8') as f:
        for item in validated_output:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')
    print(output_file)

if __name__ == '__main__':
    main()
