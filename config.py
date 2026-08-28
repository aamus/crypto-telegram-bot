import os
from dotenv import load_dotenv

# Load environment variables from .env file if available
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY", None)
VS_CURRENCY = os.getenv("VS_CURRENCY", "usd").lower()
ALERT_CHECK_INTERVAL = int(os.getenv("ALERT_CHECK_INTERVAL", "60"))

# Database path for user watchlists and alerts
DB_PATH = os.path.join(os.path.dirname(__file__), "crypto_bot.db")
