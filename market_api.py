import logging
import requests
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Common ticker to CoinGecko ID mappings for fast lookups
COMMON_SYMBOLS = {
    "btc": "bitcoin",
    "bitcoin": "bitcoin",
    "eth": "ethereum",
    "ethereum": "ethereum",
    "sol": "solana",
    "solana": "solana",
    "bnb": "binancecoin",
    "binancecoin": "binancecoin",
    "xrp": "ripple",
    "ripple": "ripple",
    "ada": "cardano",
    "cardano": "cardano",
    "doge": "dogecoin",
    "dogecoin": "dogecoin",
    "shib": "shiba-inu",
    "dot": "polkadot",
    "polkadot": "polkadot",
    "avax": "avalanche-2",
    "avalanche": "avalanche-2",
    "link": "chainlink",
    "chainlink": "chainlink",
    "sui": "sui",
    "pepe": "pepe",
    "near": "near",
    "matic": "matic-network",
    "polygon": "matic-network",
    "ton": "the-open-network",
    "trx": "tron",
    "ltc": "litecoin",
}

class MarketDataClient:
    def __init__(self, api_key: Optional[str] = None):
        self.base_url = "https://api.coingecko.com/api/v3"
        self.fng_url = "https://api.alternative.me/fng/"
        self.headers = {"accept": "application/json"}
        if api_key:
            self.headers["x-cg-demo-api-key"] = api_key
        self.symbol_cache: Dict[str, str] = dict(COMMON_SYMBOLS)

    def resolve_coin_id(self, query: str) -> Optional[Dict[str, str]]:
        """
        Resolves a search term or symbol (e.g. 'btc' or 'solana') to coin info.
        Returns dict with id, symbol, name or None.
        """
        query_clean = query.strip().lower()
        if query_clean in self.symbol_cache:
            coin_id = self.symbol_cache[query_clean]
            return {"id": coin_id, "symbol": query_clean.upper(), "name": coin_id.capitalize()}

        # Use CoinGecko search API if not in fast cache
        try:
            url = f"{self.base_url}/search?query={query_clean}"
            res = requests.get(url, headers=self.headers, timeout=10)
            if res.status_code == 200:
                data = res.json()
                coins = data.get("coins", [])
                if coins:
                    best_match = coins[0]
                    coin_id = best_match["id"]
                    symbol = best_match["symbol"].upper()
                    name = best_match["name"]
                    self.symbol_cache[query_clean] = coin_id
                    self.symbol_cache[symbol.lower()] = coin_id
                    return {"id": coin_id, "symbol": symbol, "name": name}
        except Exception as e:
            logger.error(f"Error resolving coin ID for '{query}': {e}")

        return None

    def get_coin_market_data(self, coin_id: str, vs_currency: str = "usd") -> Optional[Dict]:
        """
        Fetches detailed market data for a given coin ID.
        """
        try:
            url = (
                f"{self.base_url}/coins/markets"
                f"?vs_currency={vs_currency}&ids={coin_id}"
                f"&order=market_cap_desc&per_page=1&page=1&sparkline=false&price_change_percentage=1h,24h,7d"
            )
            res = requests.get(url, headers=self.headers, timeout=10)
            if res.status_code == 200:
                data = res.json()
                if data:
                    return data[0]
        except Exception as e:
            logger.error(f"Error fetching market data for {coin_id}: {e}")
        return None

    def get_ohlc(self, coin_id: str, vs_currency: str = "usd", days: int = 30) -> Optional[List[List[float]]]:
        """
        Fetches OHLC (Open, High, Low, Close) candlestick data.
        Returns list of [timestamp, open, high, low, close]
        """
        try:
            url = f"{self.base_url}/coins/{coin_id}/ohlc?vs_currency={vs_currency}&days={days}"
            res = requests.get(url, headers=self.headers, timeout=10)
            if res.status_code == 200:
                return res.json()
        except Exception as e:
            logger.error(f"Error fetching OHLC for {coin_id}: {e}")
        return None

    def get_fear_and_greed_index(self) -> Optional[Dict]:
        """
        Fetches global Crypto Fear & Greed Index from Alternative.me API.
        Returns dict with value, classification (e.g. Extreme Fear, Greed) or None.
        """
        try:
            res = requests.get(self.fng_url, timeout=5)
            if res.status_code == 200:
                data = res.json()
                fng = data.get("data", [])[0]
                return {
                    "value": int(fng.get("value", 50)),
                    "classification": fng.get("value_classification", "Neutral")
                }
        except Exception as e:
            logger.error(f"Error fetching Fear & Greed Index: {e}")
        return {"value": 50, "classification": "Neutral"}

    def get_top_movers(self, vs_currency: str = "usd", limit: int = 10) -> List[Dict]:
        """
        Fetches top market cap coins with market info.
        """
        try:
            url = (
                f"{self.base_url}/coins/markets"
                f"?vs_currency={vs_currency}&order=market_cap_desc"
                f"&per_page={limit}&page=1&sparkline=false&price_change_percentage=24h"
            )
            res = requests.get(url, headers=self.headers, timeout=10)
            if res.status_code == 200:
                return res.json()
        except Exception as e:
            logger.error(f"Error fetching top movers: {e}")
        return []
