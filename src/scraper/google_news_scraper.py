"""Scrape financial news from Google News RSS feed and return structured records."""

import datetime
import logging
from typing import Any

import feedparser
from bs4 import BeautifulSoup

from config import RSS_FEED_URL
from enrichment import enrich_articles

logger = logging.getLogger(__name__)


def scrape_google_news() -> list[dict[str, Any]]:
    """Fetch articles from Google News RSS feed and enrich with full article text.

    Returns:
        A list of article dicts containing metadata and enriched full_text.
    """
    feed = feedparser.parse(RSS_FEED_URL)
    articles: list[dict[str, Any]] = []

    for entry in feed.entries:
        title = entry.get("title", "")
        redirect_url = entry.get("link", "")
        published_at = entry.get("published", "")

        # Decode the Google News redirect to the real article URL
        final_url = redirect_url
        if "news.google.com" in redirect_url and "/rss/articles/" in redirect_url:
            try:
                from googlenewsdecoder import new_decoderv1  # noqa: F401
                decoded = new_decoderv1(redirect_url)
                if decoded and decoded.get("status"):
                    final_url = decoded.get("decoded_url")
            except Exception:
                logger.debug("Google News decode failed for %s", redirect_url[:80])

        # Source name from the feed
        source_name = ""
        if "source" in entry:
            source = entry.source
            if hasattr(source, "title"):
                source_name = source.title

        # Description: HTML → plain text
        description_html = entry.get("description", "")
        description_text = ""
        if description_html:
            soup = BeautifulSoup(description_html, "html.parser")
            description_text = soup.get_text(separator=" ", strip=True)
            if not source_name:
                font = soup.find("font")
                if font:
                    source_name = font.get_text(strip=True)

        item: dict[str, Any] = {
            "source_id": entry.get("source", {}).get("id", "google-news"),
            "source_name": source_name,
            "author": "",
            "title": title,
            "description": description_text,
            "url": final_url,
            "url_to_image": "",
            "published_at": published_at,
            "category": (
                entry.get("tags", [{"term": "general"}])[0]["term"]
                if entry.get("tags")
                else "general"
            ),
            "language": "en",
            "scraped_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            # Enrichment fields
            "full_text": "",
            "enrichment_attempted": False,
            "enrichment_success": False,
            "enrichment_timestamp": "",
            "parsing_method": "",
        }
        articles.append(item)

    logger.info("Fetched %d articles from Google News RSS", len(articles))
    enrich_articles(articles)
    return articles
