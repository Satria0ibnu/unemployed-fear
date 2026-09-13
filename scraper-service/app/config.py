import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
DATABASE_URL = os.environ["DATABASE_URL"]
REDIS_URL = os.environ["REDIS_URL"]

# Identitas scraper — jujur, bukan menyamar sebagai browser biasa
USER_AGENT = "unemployed-fear-bot/0.1 (+https://unemployed-fear.poedinglabs.fyi/about)"

# Jeda antar-request ke situs yang sama, dalam detik.
# Dimulai konservatif (aman untuk RAM & etika crawling), bisa disesuaikan
# setelah lihat apakah situs sumber punya Crawl-delay eksplisit di robots.txt.
DEFAULT_REQUEST_DELAY_SECONDS = 3

# Timeout HTTP request, dalam detik.
REQUEST_TIMEOUT_SECONDS = 15