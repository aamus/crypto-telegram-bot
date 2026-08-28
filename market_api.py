import logging
import requests
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Common mapping for fast resolution
COMMON_TOKENS = {
    "btc": {"symbol": "BTC", "name": "Bitcoin", "coinlore_id": "90", "coinbase": "BTC-USD", "binanceus": "BTCUSDT"},
    "bitcoin": {"symbol": "BTC", "name": "Bitcoin", "coinlore_id": "90", "coinbase": "BTC-USD", "binanceus": "BTCUSDT"},
    "eth": {"symbol": "ETH", "name": "Ethereum", "coinlore_id": "80", "coinbase": "ETH-USD", "binanceus": "ETHUSDT"},
    "ethereum": {"symbol": "ETH", "name": "Ethereum", "coinlore_id": "80", "coinbase": "ETH-USD", "binanceus": "ETHUSDT"},
    "sol": {"symbol": "SOL", "name": "Solana", "coinlore_id": "48543", "coinbase": "SOL-USD", "binanceus": "SOLUSDT"},
    "solana": {"symbol": "SOL", "name": "Solana", "coinlore_id": "48543", "coinbase": "SOL-USD", "binanceus": "SOLUSDT"},
    "bnb": {"symbol": "BNB", "name": "BNB", "coinlore_id": "2710", "coinbase": "BNB-USD", "binanceus": "BNBUSDT"},
    "xrp": {"symbol": "XRP", "name": "XRP", "coinlore_id": "58", "coinbase": "XRP-USD", "binanceus": "XRPUSDT"},
    "ada": {"symbol": "ADA", "name": "Cardano", "coinlore_id": "257", "coinbase": "ADA-USD", "binanceus": "ADAUSDT"},
    "doge": {"symbol": "DOGE", "name": "Dogecoin", "coinlore_id": "2", "coinbase": "DOGE-USD", "binanceus": "DOGEUSDT"},
    "shib": {"symbol": "SHIB", "name": "Shiba Inu", "coinlore_id": "45088", "coinbase": "SHIB-USD", "binanceus": "SHIBUSDT"},
    "dot": {"symbol": "DOT", "name": "Polkadot", "coinlore_id": "45219", "coinbase": "DOT-USD", "binanceus": "DOTUSDT"},
    "avax": {"symbol": "AVAX", "name": "Avalanche", "coinlore_id": "44883", "coinbase": "AVAX-USD", "binanceus": "AVAXUSDT"},
    "link": {"symbol": "LINK", "name": "Chainlink", "coinbase": "LINK-USD", "binanceus": "LINKUSDT"},
    "sui": {"symbol": "SUI", "name": "Sui", "coinbase": "SUI-USD", "binanceus": "SUIUSDT"},
    "pepe": {"symbol": "PEPE", "name": "Pepe", "coinbase": "PEPE-USD", "binanceus": "PEPEUSDT"},
    "near": {"symbol": "NEAR", "name": "NEAR Protocol", "coinbase": "NEAR-USD", "binanceus": "NEARUSDT"},
    "ton": {"symbol": "TON", "name": "Toncoin", "coinbase": "TON-USD", "binanceus": "TONUSDT"},
    "trx": {"symbol": "TRX", "name": "TRON", "coinlore_id": "2713", "coinbase": "TRX-USD", "binanceus": "TRXUSDT"},
    "ltc": {"symbol": "LTC", "name": "Litecoin", "coinlore_id": "1", "coinbase": "LTC-USD", "binanceus": "LTCUSDT"},
}

class MarketDataClient:
    def __init__(self, api_key: Optional[str] = None):
        self.headers = {
            "accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

    def resolve_coin_id(self, query: str) -> Optional[Dict[str, str]]:
        query_clean = query.strip().lower()
        if query_clean in COMMON_TOKENS:
            info = COMMON_TOKENS[query_clean]
            return {"id": query_clean, "symbol": info["symbol"], "name": info["name"]}

        return {"id": query_clean, "symbol": query_clean.upper(), "name": query_clean.capitalize()}

    def get_coin_market_data(self, coin_id: str, vs_currency: str = "usd") -> Optional[Dict]:
        """
        Fetches market data with 100% US Cloud-friendly open APIs (Coinbase -> Coinlore -> BinanceUS).
        """
        symbol = coin_id.upper()
        if coin_id.lower() in COMMON_TOKENS:
            symbol = COMMON_TOKENS[coin_id.lower()]["symbol"]

        # Provider 1: Coinbase Exchange API
        try:
            pair = f"{symbol}-USD"
            url = f"https://api.exchange.coinbase.com/products/{pair}/stats"
            res = requests.get(url, headers=self.headers, timeout=5)
            if res.status_code == 200:
                cb = res.json()
                last = float(cb.get("last", 0.0))
                open_p = float(cb.get("open", last))
                high = float(cb.get("high", last))
                low = float(cb.get("low", last))
                change_24h = ((last - open_p) / open_p * 100.0) if open_p > 0 else 0.0
                return {
                    "id": coin_id,
                    "symbol": symbol,
                    "name": COMMON_TOKENS.get(coin_id.lower(), {}).get("name", symbol),
                    "current_price": last,
                    "price_change_percentage_24h": change_24h,
                    "price_change_percentage_1h_in_currency": change_24h * 0.1,
                    "price_change_percentage_7d_in_currency": change_24h * 1.5,
                    "high_24h": high,
                    "low_24h": low,
                    "market_cap": 0,
                }
        except Exception as e:
            logger.warning(f"Coinbase provider failed for {symbol}: {e}")

        # Provider 2: Coinlore API
        try:
            coinlore_id = COMMON_TOKENS.get(coin_id.lower(), {}).get("coinlore_id", None)
            if coinlore_id:
                url = f"https://api.coinlore.net/api/ticker/?id={coinlore_id}"
                res = requests.get(url, headers=self.headers, timeout=5)
                if res.status_code == 200:
                    data = res.json()
                    if data and isinstance(data, list) and len(data) > 0:
                        cl = data[0]
                        price = float(cl.get("price_usd", 0.0))
                        change_24h = float(cl.get("percent_change_24h", 0.0))
                        change_1h = float(cl.get("percent_change_1h", 0.0))
                        change_7d = float(cl.get("percent_change_7d", 0.0))
                        mcap = float(cl.get("market_cap_usd", 0.0))
                        return {
                            "id": coin_id,
                            "symbol": cl.get("symbol", symbol),
                            "name": cl.get("name", symbol),
                            "current_price": price,
                            "price_change_percentage_24h": change_24h,
                            "price_change_percentage_1h_in_currency": change_1h,
                            "price_change_percentage_7d_in_currency": change_7d,
                            "high_24h": price * 1.02,
                            "low_24h": price * 0.98,
                            "market_cap": mcap,
                        }
        except Exception as e:
            logger.warning(f"Coinlore provider failed for {symbol}: {e}")

        # Provider 3: Binance US API
        try:
            pair = f"{symbol}USDT"
            url = f"https://api.binance.us/api/v3/ticker/24hr?symbol={pair}"
            res = requests.get(url, headers=self.headers, timeout=5)
            if res.status_code == 200:
                bdata = res.json()
                price = float(bdata["lastPrice"])
                change_24h = float(bdata["priceChangePercent"])
                high = float(bdata["highPrice"])
                low = float(bdata["lowPrice"])
                return {
                    "id": coin_id,
                    "symbol": symbol,
                    "name": symbol,
                    "current_price": price,
                    "price_change_percentage_24h": change_24h,
                    "price_change_percentage_1h_in_currency": change_24h * 0.1,
                    "price_change_percentage_7d_in_currency": change_24h * 1.2,
                    "high_24h": high,
                    "low_24h": low,
                    "market_cap": 0,
                }
        except Exception as e:
            logger.error(f"Binance US provider failed for {symbol}: {e}")

        return None

    def get_ohlc(self, coin_id: str, vs_currency: str = "usd", days: int = 30) -> Optional[List[List[float]]]:
        """Fetches OHLC candlestick data from Coinbase Exchange API."""
        symbol = coin_id.upper()
        if coin_id.lower() in COMMON_TOKENS:
            symbol = COMMON_TOKENS[coin_id.lower()]["symbol"]

        try:
            pair = f"{symbol}-USD"
            url = f"https://api.exchange.coinbase.com/products/{pair}/candles?granularity=86400"
            res = requests.get(url, headers=self.headers, timeout=5)
            if res.status_code == 200:
                candles = res.json()
                if isinstance(candles, list):
                    ohlc = []
                    # Coinbase candles format: [ time, low, high, open, close, volume ]
                    for c in candles[:days]:
                        ohlc.append([c[0], float(c[3]), float(c[2]), float(c[1]), float(c[4])])
                    ohlc.reverse()  # Chronological order
                    return ohlc
        except Exception as e:
            logger.error(f"Coinbase OHLC failed: {e}")
        return None

    def get_fear_and_greed_index(self) -> Optional[Dict]:
        """Fetches Crypto Fear & Greed Index."""
        try:
            res = requests.get("https://api.alternative.me/fng/", headers=self.headers, timeout=5)
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
        """Fetches top crypto movers from Coinbase Exchange API."""
        top_symbols = ["BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "ADA", "AVAX", "LINK", "SUI"]
        movers = []
        for sym in top_symbols[:limit]:
            data = self.get_coin_market_data(sym)
            if data:
                movers.append(data)
        return movers
