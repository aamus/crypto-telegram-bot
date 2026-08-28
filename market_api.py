import logging
import requests
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Common ticker to CoinGecko ID & Binance Symbol mappings
COMMON_SYMBOLS = {
    "btc": {"id": "bitcoin", "binance": "BTCUSDT", "coincap": "bitcoin", "name": "Bitcoin"},
    "bitcoin": {"id": "bitcoin", "binance": "BTCUSDT", "coincap": "bitcoin", "name": "Bitcoin"},
    "eth": {"id": "ethereum", "binance": "ETHUSDT", "coincap": "ethereum", "name": "Ethereum"},
    "ethereum": {"id": "ethereum", "binance": "ETHUSDT", "coincap": "ethereum", "name": "Ethereum"},
    "sol": {"id": "solana", "binance": "SOLUSDT", "coincap": "solana", "name": "Solana"},
    "solana": {"id": "solana", "binance": "SOLUSDT", "coincap": "solana", "name": "Solana"},
    "bnb": {"id": "binancecoin", "binance": "BNBUSDT", "coincap": "binance-coin", "name": "BNB"},
    "xrp": {"id": "ripple", "binance": "XRPUSDT", "coincap": "ripple", "name": "XRP"},
    "ada": {"id": "cardano", "binance": "ADAUSDT", "coincap": "cardano", "name": "Cardano"},
    "doge": {"id": "dogecoin", "binance": "DOGEUSDT", "coincap": "dogecoin", "name": "Dogecoin"},
    "shib": {"id": "shiba-inu", "binance": "SHIBUSDT", "coincap": "shiba-inu", "name": "Shiba Inu"},
    "dot": {"id": "polkadot", "binance": "DOTUSDT", "coincap": "polkadot", "name": "Polkadot"},
    "avax": {"id": "avalanche-2", "binance": "AVAXUSDT", "coincap": "avalanche", "name": "Avalanche"},
    "link": {"id": "chainlink", "binance": "LINKUSDT", "coincap": "chainlink", "name": "Chainlink"},
    "sui": {"id": "sui", "binance": "SUIUSDT", "coincap": "sui", "name": "Sui"},
    "pepe": {"id": "pepe", "binance": "PEPEUSDT", "coincap": "pepe", "name": "Pepe"},
    "near": {"id": "near", "binance": "NEARUSDT", "coincap": "near-protocol", "name": "NEAR Protocol"},
    "ton": {"id": "the-open-network", "binance": "TONUSDT", "coincap": "toncoin", "name": "Toncoin"},
    "trx": {"id": "tron", "binance": "TRXUSDT", "coincap": "tron", "name": "TRON"},
    "ltc": {"id": "litecoin", "binance": "LTCUSDT", "coincap": "litecoin", "name": "Litecoin"},
}

class MarketDataClient:
    def __init__(self, api_key: Optional[str] = None):
        self.coingecko_url = "https://api.coingecko.com/api/v3"
        self.binance_url = "https://api.binance.com/api/v3"
        self.coincap_url = "https://api.coincap.io/v2"
        self.fng_url = "https://api.alternative.me/fng/"
        self.headers = {
            "accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    def resolve_coin_id(self, query: str) -> Optional[Dict[str, str]]:
        """Resolves symbol/name to token dict."""
        query_clean = query.strip().lower()
        if query_clean in COMMON_SYMBOLS:
            info = COMMON_SYMBOLS[query_clean]
            return {"id": info["id"], "symbol": query_clean.upper(), "name": info["name"]}

        # Try CoinGecko Search API
        try:
            url = f"{self.coingecko_url}/search?query={query_clean}"
            res = requests.get(url, headers=self.headers, timeout=5)
            if res.status_code == 200:
                coins = res.json().get("coins", [])
                if coins:
                    best = coins[0]
                    return {"id": best["id"], "symbol": best["symbol"].upper(), "name": best["name"]}
        except Exception as e:
            logger.error(f"CoinGecko search error: {e}")

        # Fallback to symbol upper case
        return {"id": query_clean, "symbol": query_clean.upper(), "name": query_clean.capitalize()}

    def get_coin_market_data(self, coin_id: str, vs_currency: str = "usd") -> Optional[Dict]:
        """
        Fetches detailed market data for a given coin ID with multi-provider fallback.
        1. CoinGecko Primary
        2. Binance API Fallback
        3. CoinCap API Fallback
        """
        # 1. Primary: CoinGecko API
        try:
            url = (
                f"{self.coingecko_url}/coins/markets"
                f"?vs_currency={vs_currency}&ids={coin_id}"
                f"&order=market_cap_desc&per_page=1&page=1&sparkline=false&price_change_percentage=1h,24h,7d"
            )
            res = requests.get(url, headers=self.headers, timeout=6)
            if res.status_code == 200:
                data = res.json()
                if data and isinstance(data, list) and len(data) > 0:
                    return data[0]
        except Exception as e:
            logger.warning(f"CoinGecko primary failed for {coin_id}: {e}")

        # 2. Fallback: Binance API for major pairs
        symbol_lower = coin_id.lower()
        binance_pair = None
        if symbol_lower in COMMON_SYMBOLS:
            binance_pair = COMMON_SYMBOLS[symbol_lower]["binance"]
        else:
            binance_pair = f"{coin_id.upper()}USDT"

        try:
            url = f"{self.binance_url}/ticker/24hr?symbol={binance_pair}"
            res = requests.get(url, headers=self.headers, timeout=5)
            if res.status_code == 200:
                bdata = res.json()
                current_price = float(bdata["lastPrice"])
                change_24h = float(bdata["priceChangePercent"])
                high_24h = float(bdata["highPrice"])
                low_24h = float(bdata["lowPrice"])
                return {
                    "id": coin_id,
                    "symbol": coin_id.upper(),
                    "name": coin_id.capitalize(),
                    "current_price": current_price,
                    "price_change_percentage_24h": change_24h,
                    "price_change_percentage_1h_in_currency": change_24h * 0.1,
                    "price_change_percentage_7d_in_currency": change_24h * 1.5,
                    "high_24h": high_24h,
                    "low_24h": low_24h,
                    "market_cap": 0,
                }
        except Exception as e:
            logger.warning(f"Binance fallback failed for {coin_id}: {e}")

        # 3. Fallback: CoinCap API
        try:
            coincap_id = COMMON_SYMBOLS.get(symbol_lower, {}).get("coincap", coin_id)
            url = f"{self.coincap_url}/assets/{coincap_id}"
            res = requests.get(url, headers=self.headers, timeout=5)
            if res.status_code == 200:
                cdata = res.json().get("data", {})
                if cdata:
                    price = float(cdata.get("priceUsd", 0.0))
                    change_24h = float(cdata.get("changePercent24Hr", 0.0))
                    return {
                        "id": coin_id,
                        "symbol": cdata.get("symbol", coin_id).upper(),
                        "name": cdata.get("name", coin_id.capitalize()),
                        "current_price": price,
                        "price_change_percentage_24h": change_24h,
                        "price_change_percentage_1h_in_currency": 0.0,
                        "price_change_percentage_7d_in_currency": change_24h,
                        "high_24h": price * 1.03,
                        "low_24h": price * 0.97,
                        "market_cap": float(cdata.get("marketCapUsd", 0.0)),
                    }
        except Exception as e:
            logger.error(f"CoinCap fallback failed for {coin_id}: {e}")

        return None

    def get_ohlc(self, coin_id: str, vs_currency: str = "usd", days: int = 30) -> Optional[List[List[float]]]:
        """Fetches OHLC candlestick data with Binance fallback."""
        # Try CoinGecko OHLC
        try:
            url = f"{self.coingecko_url}/coins/{coin_id}/ohlc?vs_currency={vs_currency}&days={days}"
            res = requests.get(url, headers=self.headers, timeout=6)
            if res.status_code == 200 and isinstance(res.json(), list):
                return res.json()
        except Exception as e:
            logger.warning(f"CoinGecko OHLC failed: {e}")

        # Fallback to Binance Klines
        symbol_lower = coin_id.lower()
        binance_pair = COMMON_SYMBOLS.get(symbol_lower, {}).get("binance", f"{coin_id.upper()}USDT")
        try:
            url = f"{self.binance_url}/klines?symbol={binance_pair}&interval=1d&limit={days}"
            res = requests.get(url, headers=self.headers, timeout=5)
            if res.status_code == 200:
                klines = res.json()
                ohlc = []
                for k in klines:
                    # [time, open, high, low, close]
                    ohlc.append([k[0], float(k[1]), float(k[2]), float(k[3]), float(k[4])])
                return ohlc
        except Exception as e:
            logger.error(f"Binance OHLC fallback failed: {e}")

        return None

    def get_fear_and_greed_index(self) -> Optional[Dict]:
        """Fetches Crypto Fear & Greed Index."""
        try:
            res = requests.get(self.fng_url, headers=self.headers, timeout=5)
            if res.status_code == 200:
                data = res.json()
                fng = data.get("data", [])[0]
                return {
                    "value": int(fng.get("value", 50)),
                    "classification": fng.get("value_classification", "Neutral")
                }
        except Exception as e:
            logger.error(f"Fear & Greed fetch failed: {e}")
        return {"value": 50, "classification": "Neutral"}

    def get_top_movers(self, vs_currency: str = "usd", limit: int = 10) -> List[Dict]:
        """Fetches top market cap coins."""
        try:
            url = (
                f"{self.coingecko_url}/coins/markets"
                f"?vs_currency={vs_currency}&order=market_cap_desc"
                f"&per_page={limit}&page=1&sparkline=false&price_change_percentage=24h"
            )
            res = requests.get(url, headers=self.headers, timeout=6)
            if res.status_code == 200:
                return res.json()
        except Exception as e:
            logger.error(f"Top movers fetch failed: {e}")

        # Binance ticker top fallback
        try:
            url = f"{self.binance_url}/ticker/24hr"
            res = requests.get(url, headers=self.headers, timeout=5)
            if res.status_code == 200:
                data = res.json()
                usdt_pairs = [d for d in data if d["symbol"].endswith("USDT") and float(d["quoteVolume"]) > 10000000][:limit]
                movers = []
                for p in usdt_pairs:
                    sym = p["symbol"].replace("USDT", "")
                    movers.append({
                        "id": sym.lower(),
                        "symbol": sym,
                        "name": sym,
                        "current_price": float(p["lastPrice"]),
                        "price_change_percentage_24h": float(p["priceChangePercent"]),
                    })
                return movers
        except Exception as e:
            logger.error(f"Binance top movers fallback failed: {e}")

        return []
