import feedparser
import datetime
import os
from bs4 import BeautifulSoup
from googlenewsdecoder import new_decoderv1

from config import RSS_FEED_URL
from enrichment import enrich_articles

def scrape_google_news():
    feed = feedparser.parse(RSS_FEED_URL)

    output = []
    for entry in feed.entries:
        # --- Basic fields ---
        title = entry.get('title', '')
        redirect_url = entry.get('link', '')
        published_at = entry.get('published', '')

        # --- Decode the Google News redirect ---
        final_url = redirect_url
        if 'news.google.com' in redirect_url and '/rss/articles/' in redirect_url:
            try:
                decoded = new_decoderv1(redirect_url)
                if decoded and decoded.get('status'):
                    final_url = decoded.get('decoded_url')
            except Exception:
                pass  # keep redirect_url if decoding fails

        # --- Source name ---
        # Prefer the <source> tag from the feed
        source_name = ''
        if 'source' in entry:
            source = entry.source
            if hasattr(source, 'title'):
                source_name = source.title

        # --- Description (HTML -> plain text) ---
        description_html = entry.get('description', '')
        description_text = ''
        if description_html:
            soup = BeautifulSoup(description_html, 'html.parser')
            description_text = soup.get_text(separator=' ', strip=True)
            if not source_name:
                font = soup.find('font')
                if font:
                    source_name = font.get_text(strip=True)

        # --- Build the article dict (matches raw schema) ---
        item = {
            'source_id': entry.get('source', {}).get('id', 'google-news'),
            'source_name': source_name,
            'author': '',
            'title': title,
            'description': description_text,
            'url': final_url,  # now the real article URL
            'url_to_image': '',
            'published_at': published_at,
            'category': entry.get('tags', [{'term': 'general'}])[0]['term'],
            'language': 'en',
            'scraped_at': datetime.datetime.now().isoformat() + 'Z',
            # Enrichment fields (will be filled later)
            'full_text': '',
            'enrichment_attempted': False,
            'enrichment_success': False,
            'enrichment_timestamp': '',
            'parsing_method': '',
        }
        output.append(item)

    # Enrich all articles with full_text via BeautifulSoup
    enrich_articles(output)

    return output
