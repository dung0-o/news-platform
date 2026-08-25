import requests
import datetime
import os

from config import NEWS_API_KEY
from enrichment import enrich_articles

def scrape_newsapi():
    url = 'https://newsapi.org/v2/top-headlines'
    params = {
        'country': 'us',
        'apiKey': NEWS_API_KEY,
        'language': 'en'
    }

    response = requests.get(url, params=params)
    data = response.json()

    output = []
    for article in data['articles']:
        item = {
            'source_id': article.get('source', {}).get('id', ''),
            'source_name': article.get('source', {}).get('name', ''),
            'author': article.get('author', ''),
            'title': article['title'],
            'description': article['description'],
            'url': article['url'],
            'url_to_image': article.get('urlToImage', ''),
            'published_at': article['publishedAt'],
            'full_text': '',
            'category': article.get('category', 'general'),
            'language': article.get('language', 'en'),
            'scraped_at': datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
        }
        output.append(item)

    # Enrich all articles with full_text via BeautifulSoup
    enrich_articles(output)

    return output
