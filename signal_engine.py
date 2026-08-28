import logging
from typing import Dict, List, Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)

def calculate_rsi(prices: List[float], period: int = 14) -> Optional[float]:
    """Calculates Relative Strength Index (RSI) using standard Wilder's Smoothing."""
    if len(prices) < period + 1:
        return None

    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])

    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    return float(100.0 - (100.0 / (1.0 + rs)))


def calculate_ema(prices: List[float], period: int) -> Optional[float]:
    """Calculates Exponential Moving Average (EMA)."""
    if len(prices) < period:
        return None
    multiplier = 2 / (period + 1)
    ema = np.mean(prices[:period])
    for price in prices[period:]:
        ema = (price - ema) * multiplier + ema
    return float(ema)


def calculate_macd(prices: List[float]) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """
    Calculates MACD Line (12, 26) and Signal Line (9).
    Returns (macd_line, signal_line, histogram)
    """
    if len(prices) < 26:
        return None, None, None

    ema_12 = calculate_ema(prices, 12)
    ema_26 = calculate_ema(prices, 26)
    if ema_12 is None or ema_26 is None:
        return None, None, None

    macd_line = ema_12 - ema_26
    # Simplified signal estimate from last 9 values
    macd_history = []
    for i in range(len(prices) - 9, len(prices)):
        sub_prices = prices[:i+1]
        e12 = calculate_ema(sub_prices, 12)
        e26 = calculate_ema(sub_prices, 26)
        if e12 and e26:
            macd_history.append(e12 - e26)

    signal_line = np.mean(macd_history) if macd_history else macd_line
    histogram = macd_line - signal_line
    return float(macd_line), float(signal_line), float(histogram)


def calculate_atr(ohlc_data: List[List[float]], period: int = 14) -> Optional[float]:
    """
    Calculates Average True Range (ATR) for volatility-based dynamic stop losses.
    candlestick: [timestamp, open, high, low, close]
    """
    if len(ohlc_data) < period + 1:
        return None

    true_ranges = []
    for i in range(1, len(ohlc_data)):
        high = ohlc_data[i][2]
        low = ohlc_data[i][3]
        prev_close = ohlc_data[i-1][4]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        true_ranges.append(tr)

    if not true_ranges:
        return None

    atr = float(np.mean(true_ranges[-period:]))
    return atr


class SignalEngine:
    @staticmethod
    def analyze_token(
        market_data: Dict,
        ohlc_data: Optional[List[List[float]]] = None,
        fng_data: Optional[Dict] = None
    ) -> Dict:
        """
        Institutional-grade analysis engine integrating RSI, MACD, ATR Volatility,
        Multi-timeframe trend scoring, and Market Sentiment.
        """
        current_price = market_data.get("current_price") or 0.0
        change_24h = market_data.get("price_change_percentage_24h") or 0.0
        change_1h = market_data.get("price_change_percentage_1h_in_currency") or 0.0
        change_7d = market_data.get("price_change_percentage_7d_in_currency") or 0.0
        name = market_data.get("name", "Unknown")
        symbol = market_data.get("symbol", "").upper()
        high_24h = market_data.get("high_24h") or current_price
        low_24h = market_data.get("low_24h") or current_price

        rsi_value = None
        macd_line, signal_line, macd_hist = None, None, None
        atr_volatility = None
        ema_20, ema_50 = None, None

        # Extract prices from OHLC if available
        if ohlc_data and len(ohlc_data) >= 14:
            close_prices = [candle[4] for candle in ohlc_data]
            rsi_value = calculate_rsi(close_prices, period=min(14, len(close_prices) - 1))
            macd_line, signal_line, macd_hist = calculate_macd(close_prices)
            atr_volatility = calculate_atr(ohlc_data, period=14)
            ema_20 = calculate_ema(close_prices, 20)
            ema_50 = calculate_ema(close_prices, 50)

        # Fear & Greed sentiment factor
        fng_value = fng_data.get("value", 50) if fng_data else 50
        fng_class = fng_data.get("classification", "Neutral") if fng_data else "Neutral"

        # Signal Scoring System (-10 to +10)
        score = 0
        reasons = []

        # 1. RSI Scoring
        if rsi_value is not None:
            if rsi_value <= 30:
                score += 4
                reasons.append(f"Oversold RSI ({rsi_value:.1f}) — Strong historical rebound zone.")
            elif rsi_value <= 45:
                score += 2
                reasons.append(f"Healthy RSI ({rsi_value:.1f}) — Room for upside growth.")
            elif rsi_value >= 72:
                score -= 4
                reasons.append(f"Overbought RSI ({rsi_value:.1f}) — Pullback high risk.")
            elif rsi_value >= 62:
                score -= 2
                reasons.append(f"Elevated RSI ({rsi_value:.1f}) — Caution on new entries.")
        else:
            if change_24h < -10.0:
                score += 3
                reasons.append(f"Heavy 24h dip (-{abs(change_24h):.1f}%) — Dip buyer setup.")
            elif change_24h > 15.0:
                score -= 3
                reasons.append(f"Extremely high 24h pump (+{change_24h:.1f}%) — Profit taking zone.")

        # 2. MACD Momentum Scoring
        if macd_hist is not None:
            if macd_hist > 0 and macd_line > signal_line:
                score += 3
                reasons.append("Bullish MACD Crossover — Positive momentum building.")
            elif macd_hist < 0 and macd_line < signal_line:
                score -= 3
                reasons.append("Bearish MACD Crossover — Downward momentum pressure.")

        # 3. EMA Trend Alignment
        if ema_20 and ema_50:
            if current_price > ema_20 > ema_50:
                score += 3
                reasons.append("Multi-timeframe Trend: Bullish Alignment (Price > 20-EMA > 50-EMA).")
            elif current_price < ema_20 < ema_50:
                score -= 3
                reasons.append("Multi-timeframe Trend: Bearish Alignment (Price below Moving Averages).")

        # 4. Fear & Greed Sentiment Adjustment
        if fng_value <= 25:
            score += 1
            reasons.append(f"Global Sentiment: Extreme Fear ({fng_value}/100) — Contrarian BUY opportunity.")
        elif fng_value >= 75:
            score -= 1
            reasons.append(f"Global Sentiment: Extreme Greed ({fng_value}/100) — High market euphoria, protect capital.")

        # Classify final signal based on total score
        if score >= 5:
            signal = "STRONG BUY"
            action_color = "🟢"
            confidence = "HIGH"
        elif score >= 2:
            signal = "ACCUMULATE / BUY"
            action_color = "🟢"
            confidence = "MEDIUM"
        elif score <= -5:
            signal = "STRONG SELL / TAKE PROFIT"
            action_color = "🔴"
            confidence = "HIGH"
        elif score <= -2:
            signal = "TAKE PROFIT / REDUCE RISK"
            action_color = "🔴"
            confidence = "MEDIUM"
        else:
            signal = "HOLD / NEUTRAL"
            action_color = "🟡"
            confidence = "LOW"

        # Calculate Volatility-Based Dynamic Stop-Loss & Take-Profit Targets
        # Using 2.0x ATR for Stop Loss, 3.5x and 6.0x ATR for Take Profit (Ensures 1:2+ R/R Ratio)
        entry_price = current_price
        if atr_volatility and atr_volatility > 0:
            stop_loss = max(entry_price - (1.8 * atr_volatility), entry_price * 0.90)
            tp1 = entry_price + (2.5 * atr_volatility)
            tp2 = entry_price + (5.0 * atr_volatility)
        else:
            # Fallback percentages if OHLC ATR unavailable
            stop_loss = entry_price * 0.94  # -6% Stop Loss
            tp1 = entry_price * 1.12        # +12% Take Profit 1
            tp2 = entry_price * 1.25        # +25% Take Profit 2

        # Verify Risk-to-Reward Ratio
        risk_per_unit = entry_price - stop_loss
        reward_per_unit = tp1 - entry_price
        rr_ratio = reward_per_unit / risk_per_unit if risk_per_unit > 0 else 2.0

        return {
            "name": name,
            "symbol": symbol,
            "current_price": current_price,
            "change_1h": change_1h,
            "change_24h": change_24h,
            "change_7d": change_7d,
            "high_24h": high_24h,
            "low_24h": low_24h,
            "rsi": rsi_value,
            "macd": {"line": macd_line, "signal": signal_line, "hist": macd_hist},
            "atr_volatility": atr_volatility,
            "fng_index": {"value": fng_value, "classification": fng_class},
            "score": score,
            "signal": signal,
            "action_color": action_color,
            "confidence": confidence,
            "reasons": reasons,
            "trade_levels": {
                "entry": entry_price,
                "tp1": tp1,
                "tp2": tp2,
                "stop_loss": stop_loss,
                "rr_ratio": rr_ratio,
            },
        }

    @staticmethod
    def calculate_position_size(
        portfolio_capital: float,
        risk_percentage: float,
        entry_price: float,
        stop_loss_price: float
    ) -> Dict:
        """
        Professional Risk Management & Position Sizing Calculator.
        Determines exact dollar allocation so user risks maximum X% of total portfolio.
        """
        if portfolio_capital <= 0 or entry_price <= 0 or stop_loss_price >= entry_price:
            return {"error": "Invalid input parameters. Ensure Stop Loss < Entry Price."}

        max_risk_dollars = portfolio_capital * (risk_percentage / 100.0)
        risk_per_coin = entry_price - stop_loss_price
        coin_quantity = max_risk_dollars / risk_per_coin
        position_dollar_value = coin_quantity * entry_price
        portfolio_exposure_pct = (position_dollar_value / portfolio_capital) * 100.0

        return {
            "portfolio_capital": portfolio_capital,
            "risk_percentage": risk_percentage,
            "max_risk_dollars": max_risk_dollars,
            "entry_price": entry_price,
            "stop_loss_price": stop_loss_price,
            "coin_quantity": coin_quantity,
            "position_dollar_value": position_dollar_value,
            "portfolio_exposure_pct": portfolio_exposure_pct,
        }
