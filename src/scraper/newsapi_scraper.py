"""Scrape financial news from NewsAPI and return structured records."""

import datetime
import logging
from typing import Any

import requests
from requests.exceptions import HTTPError

from config import NEWS_API_KEY
from enrichment import enrich_articles

logger = logging.getLogger(__name__)

URL = "https://newsapi.org/v2/top-headlines"
PARAMS = {
    "country": "us",
    "apiKey": NEWS_API_KEY,
    "language": "en",
}

def scrape_newsapi() -> list[dict[str, Any]]:
    """Fetch top headlines from NewsAPI and enrich with full article text.

    Returns:
        A list of article dicts containing metadata and enriched full_text.
    """
    try:
        response = requests.get(URL, params=PARAMS, timeout=30)
        response.raise_for_status()
        data = response.json()
    except HTTPError as exc:
        logger.error("NewsAPI returned HTTP %s", exc.response.status_code)
        raise
    except requests.exceptions.RequestException as exc:
        logger.error("Network error while fetching NewsAPI: %s", exc)
        raise

    articles: list[dict[str, Any]] = []
    for article in data["articles"]:
        item: dict[str, Any] = {
            "source_id": article.get("source", {}).get("id", ""),
            "source_name": article.get("source", {}).get("name", ""),
            "author": article.get("author", ""),
            "title": article["title"],
            "description": article.get("description", ""),
            "url": article["url"],
            "url_to_image": article.get("urlToImage", ""),
            "published_at": article["publishedAt"],
            "full_text": "",
            "category": article.get("category", "general"),
            "language": article.get("language", "en"),
            "scraped_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        articles.append(item)

    logger.info("Fetched %d articles from NewsAPI", len(articles))
    enrich_articles(articles)
    return articles
