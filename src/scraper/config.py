import os

from dotenv import load_dotenv
load_dotenv()

NEWS_API_KEY = os.getenv('NEWS_API_KEY')
RSS_FEED_URL = os.getenv('RSS_FEED_URL')
