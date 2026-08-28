import logging
import asyncio
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
)

from config import TELEGRAM_BOT_TOKEN, DB_PATH, VS_CURRENCY, ALERT_CHECK_INTERVAL
from market_api import MarketDataClient
from signal_engine import SignalEngine
from watchlist import WatchlistDatabase

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize components
market_client = MarketDataClient()
db = WatchlistDatabase(DB_PATH)


class HealthCheckHandler(BaseHTTPRequestHandler):
    """Dummy HTTP Health Check Handler for Render Free Web Service."""
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Crypto Telegram Bot is active!")

    def log_message(self, format, *args):
        return  # Silence HTTP server logs


def start_health_check_server():
    """Starts a background HTTP health check server for Render compatibility."""
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    logger.info(f"Health check HTTP server listening on port {port}")
    server.serve_forever()


def format_price(price: float) -> str:
    """Formats price with appropriate precision based on size."""
    if price >= 1.0:
        return f"${price:,.2f}"
    elif price >= 0.0001:
        return f"${price:.4f}"
    else:
        return f"${price:.8f}"


def format_signal_message(analysis: Dict) -> str:
    """Formats signal analysis dictionary into clean HTML Telegram message."""
    symbol = analysis["symbol"]
    name = analysis["name"]
    price = format_price(analysis["current_price"])
    color = analysis["action_color"]
    signal = analysis["signal"]
    confidence = analysis["confidence"]
    change_24h = analysis["change_24h"]
    change_1h = analysis["change_1h"]
    change_7d = analysis["change_7d"]
    rsi = f"{analysis['rsi']:.1f}" if analysis["rsi"] is not None else "N/A"
    score = analysis["score"]
    
    fng = analysis.get("fng_index", {})
    fng_str = f"{fng.get('value', 50)}/100 ({fng.get('classification', 'Neutral')})"
    
    change_24h_str = f"+{change_24h:.2f}% 🚀" if change_24h > 0 else f"{change_24h:.2f}% 🔻"
    reasons_text = "\n".join([f"• {r}" for r in analysis["reasons"]])
    levels = analysis["trade_levels"]
    rr_ratio = f"{levels['rr_ratio']:.2f}:1"
    
    msg = (
        f"<b>{color} TRADER SIGNAL & SUGGESTION: {symbol}</b>\n"
        f"<i>{name}</i>\n\n"
        f"📈 <b>Signal:</b> <u>{color} {signal}</u> (Confidence: {confidence})\n"
        f"📊 <b>Trader Score:</b> <code>{score:+d}</code> / +10\n"
        f"🌐 <b>Global Sentiment:</b> {fng_str}\n\n"
        f"💵 <b>Current Price:</b> <code>{price}</code> ({change_24h_str})\n"
        f"📈 <b>Price Action:</b> 1h: {change_1h:.2f}% | 24h: {change_24h:.2f}% | 7d: {change_7d:.2f}%\n\n"
        f"🔍 <b>Technical Breakdown:</b>\n"
        f"• RSI (14): <b>{rsi}</b>\n"
        f"{reasons_text}\n\n"
        f"🎯 <b>Strict Risk-Managed Trade Setup:</b>\n"
        f"• <b>Suggested Entry:</b> <code>{format_price(levels['entry'])}</code>\n"
        f"• <b>Take Profit 1 (+TP):</b> <code>{format_price(levels['tp1'])}</code>\n"
        f"• <b>Take Profit 2 (+TP):</b> <code>{format_price(levels['tp2'])}</code>\n"
        f"• <b>Stop Loss (-SL):</b> <code>{format_price(levels['stop_loss'])}</code>\n"
        f"• <b>Risk/Reward Ratio:</b> <code>{rr_ratio}</code>\n\n"
        f"💡 <i>Tip: Use <code>/risk &lt;capital&gt; {symbol}</code> to calculate exact position sizing for your budget!</i>"
    )
    return msg


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends welcome message and menu on /start."""
    welcome_text = (
        "🤖 <b>Welcome to Professional Crypto Advisor & Signal Bot!</b>\n\n"
        "I provide institutional-grade trading suggestions using RSI, MACD, Moving Averages, Multi-timeframe trend scoring, and Market Sentiment.\n\n"
        "⚡ <b>Available Commands:</b>\n"
        "• <code>/signal &lt;token&gt;</code> - Get instant Buy/Sell trading signal for any token (e.g. <code>/signal btc</code>)\n"
        "• <code>/risk &lt;capital&gt; &lt;token&gt;</code> - Calculate exact position size and dollar risk (e.g. <code>/risk 5000 btc</code>)\n"
        "• <code>/top</code> - Scan top crypto assets for active signals\n"
        "• <code>/watchlist</code> - View your saved watchlist\n"
        "• <code>/add &lt;token&gt;</code> / <code>/remove &lt;token&gt;</code> - Manage saved tokens\n"
        "• <code>/alert &lt;token&gt; &lt;price&gt;</code> - Set target price alert\n"
        "• <code>/disclaimer</code> - Financial risk management advice\n\n"
        "<i>Try typing <code>/signal btc</code> or <code>/risk 5000 btc</code> right now!</i>"
    )
    await update.message.reply_text(welcome_text, parse_mode="HTML")


async def signal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /signal <token> command."""
    if not context.args:
        await update.message.reply_text("❌ Usage: <code>/signal &lt;token&gt;</code>\nExample: <code>/signal btc</code>", parse_mode="HTML")
        return

    query = " ".join(context.args)
    status_msg = await update.message.reply_text(f"🔍 Analyzing technical indicators & multi-timeframe trends for <b>{query.upper()}</b>...", parse_mode="HTML")

    coin_info = market_client.resolve_coin_id(query)
    if not coin_info:
        await status_msg.edit_text(f"❌ Could not find token matching '<b>{query}</b>'. Check the symbol and try again.", parse_mode="HTML")
        return

    coin_id = coin_info["id"]
    market_data = market_client.get_coin_market_data(coin_id, VS_CURRENCY)
    if not market_data:
        await status_msg.edit_text(f"❌ Failed to retrieve market data for {coin_info['name']}. Please try again later.")
        return

    ohlc_data = market_client.get_ohlc(coin_id, VS_CURRENCY, days=30)
    fng_data = market_client.get_fear_and_greed_index()
    analysis = SignalEngine.analyze_token(market_data, ohlc_data, fng_data)

    formatted_msg = format_signal_message(analysis)

    keyboard = [
        [
            InlineKeyboardButton("➕ Add to Watchlist", callback_data=f"add_{coin_id}_{analysis['symbol']}"),
            InlineKeyboardButton("🔄 Refresh Signal", callback_data=f"refresh_{coin_id}"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await status_msg.edit_text(formatted_msg, parse_mode="HTML", reply_markup=reply_markup)


async def risk_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /risk <capital> <token> [risk_pct] command."""
    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ <b>Position Calculator Usage:</b>\n"
            "<code>/risk &lt;total_capital&gt; &lt;token&gt; [risk_percent]</code>\n\n"
            "<b>Example:</b> <code>/risk 5000 btc</code> (Risks 1.5% of $5,000 portfolio on BTC)\n"
            "<b>Example:</b> <code>/risk 10000 sol 2</code> (Risks 2.0% of $10,000 portfolio on SOL)",
            parse_mode="HTML"
        )
        return

    try:
        capital = float(context.args[0].replace("$", "").replace(",", ""))
    except ValueError:
        await update.message.reply_text("❌ Invalid portfolio capital amount.")
        return

    query = context.args[1]
    risk_pct = 1.5
    if len(context.args) >= 3:
        try:
            risk_pct = float(context.args[2].replace("%", ""))
        except ValueError:
            pass

    coin_info = market_client.resolve_coin_id(query)
    if not coin_info:
        await update.message.reply_text(f"❌ Token '{query}' not found.")
        return

    coin_id = coin_info["id"]
    market_data = market_client.get_coin_market_data(coin_id, VS_CURRENCY)
    if not market_data:
        await update.message.reply_text("❌ Unable to fetch current market price.")
        return

    ohlc_data = market_client.get_ohlc(coin_id, VS_CURRENCY, days=30)
    analysis = SignalEngine.analyze_token(market_data, ohlc_data)
    entry_price = analysis["trade_levels"]["entry"]
    stop_loss_price = analysis["trade_levels"]["stop_loss"]

    calc = SignalEngine.calculate_position_size(capital, risk_pct, entry_price, stop_loss_price)
    if "error" in calc:
        await update.message.reply_text(f"❌ Calculation error: {calc['error']}")
        return

    msg = (
        f"🛡️ <b>POSITION SIZING & RISK CALCULATOR</b>\n"
        f"Token: <b>{coin_info['name']} ({coin_info['symbol']})</b>\n\n"
        f"💼 <b>Total Portfolio Capital:</b> <code>${capital:,.2f}</code>\n"
        f"⚠️ <b>Risk Tolerance per Trade:</b> <code>{risk_pct:.1f}%</code> (Max Loss: <code>${calc['max_risk_dollars']:,.2f}</code>)\n\n"
        f"📥 <b>Entry Price:</b> <code>{format_price(entry_price)}</code>\n"
        f"🛑 <b>Strict Stop-Loss Price:</b> <code>{format_price(stop_loss_price)}</code>\n\n"
        f"🎯 <b>YOUR RECOMMENDED TRADE ALLOCATION:</b>\n"
        f"• <b>Buy Quantity:</b> <code>{calc['coin_quantity']:.4f} {coin_info['symbol']}</code>\n"
        f"• <b>Total Dollar Value to Buy:</b> <code>${calc['position_dollar_value']:,.2f}</code> ({calc['portfolio_exposure_pct']:.1f}% of total portfolio)\n\n"
        f"<i>By purchasing exactly {calc['coin_quantity']:.4f} {coin_info['symbol']}, if the price hits your Stop-Loss at {format_price(stop_loss_price)}, your loss will be EXACTLY ${calc['max_risk_dollars']:,.2f} ({risk_pct:.1f}% of portfolio). This protects your account from liquidation!</i>"
    )
    await update.message.reply_text(msg, parse_mode="HTML")


async def top_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /top command showing top 10 market tokens with signals."""
    status_msg = await update.message.reply_text("📊 Fetching top market crypto signals...", parse_mode="HTML")
    movers = market_client.get_top_movers(VS_CURRENCY, limit=10)

    if not movers:
        await status_msg.edit_text("❌ Unable to fetch top crypto data right now.")
        return

    lines = ["🏆 <b>Top Crypto Trader Signals</b>\n"]
    for coin in movers:
        symbol = coin["symbol"].upper()
        price = format_price(coin["current_price"])
        change_24h = coin["price_change_percentage_24h"] or 0.0
        
        if change_24h < -6.0:
            tag = "🟢 ACCUMULATE"
        elif change_24h > 12.0:
            tag = "🔴 TAKE PROFIT"
        elif change_24h > 0:
            tag = "🟢 BULLISH"
        else:
            tag = "🟡 HOLD"
            
        change_str = f"+{change_24h:.1f}%" if change_24h > 0 else f"{change_24h:.1f}%"
        lines.append(f"• <b>{symbol}</b>: <code>{price}</code> ({change_str}) | {tag}")

    lines.append("\n<i>Type <code>/signal &lt;symbol&gt;</code> for full technical setup.</i>")
    await status_msg.edit_text("\n".join(lines), parse_mode="HTML")


async def add_watchlist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /add <token> command."""
    if not context.args:
        await update.message.reply_text("❌ Usage: <code>/add &lt;token&gt;</code> (e.g. <code>/add sol</code>)", parse_mode="HTML")
        return

    query = " ".join(context.args)
    coin_info = market_client.resolve_coin_id(query)
    if not coin_info:
        await update.message.reply_text(f"❌ Token '{query}' not found.")
        return

    user_id = update.effective_user.id
    success = db.add_to_watchlist(user_id, coin_info["id"], coin_info["symbol"], coin_info["name"])
    if success:
        await update.message.reply_text(f"✅ Added <b>{coin_info['name']} ({coin_info['symbol']})</b> to your watchlist!", parse_mode="HTML")
    else:
        await update.message.reply_text("❌ Failed to add to watchlist.")


async def remove_watchlist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /remove <token> command."""
    if not context.args:
        await update.message.reply_text("❌ Usage: <code>/remove &lt;token&gt;</code> (e.g. <code>/remove sol</code>)", parse_mode="HTML")
        return

    query = " ".join(context.args)
    coin_info = market_client.resolve_coin_id(query)
    if not coin_info:
        await update.message.reply_text(f"❌ Token '{query}' not found.")
        return

    user_id = update.effective_user.id
    db.remove_from_watchlist(user_id, coin_info["id"])
    await update.message.reply_text(f"🗑️ Removed <b>{coin_info['name']}</b> from your watchlist.", parse_mode="HTML")


async def watchlist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /watchlist command."""
    user_id = update.effective_user.id
    items = db.get_user_watchlist(user_id)

    if not items:
        await update.message.reply_text("📋 Your watchlist is currently empty.\nAdd tokens with <code>/add &lt;token&gt;</code>!", parse_mode="HTML")
        return

    lines = ["⭐ <b>Your Crypto Watchlist</b>\n"]
    for item in items:
        lines.append(f"• <b>{item['name']} ({item['symbol']})</b> — /signal_{item['symbol'].lower()}")

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def alert_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /alert <token> <target_price> command."""
    if len(context.args) < 2:
        await update.message.reply_text("❌ Usage: <code>/alert &lt;token&gt; &lt;target_price&gt;</code>\nExample: <code>/alert btc 95000</code>", parse_mode="HTML")
        return

    query = context.args[0]
    try:
        target_price = float(context.args[1].replace(",", ""))
    except ValueError:
        await update.message.reply_text("❌ Invalid target price format. Please enter a valid number.")
        return

    coin_info = market_client.resolve_coin_id(query)
    if not coin_info:
        await update.message.reply_text(f"❌ Token '{query}' not found.")
        return

    market_data = market_client.get_coin_market_data(coin_info["id"], VS_CURRENCY)
    current_price = market_data.get("current_price", 0.0) if market_data else 0.0

    condition = "ABOVE" if target_price >= current_price else "BELOW"
    user_id = update.effective_user.id

    db.set_price_alert(user_id, coin_info["id"], coin_info["symbol"], target_price, condition)

    await update.message.reply_text(
        f"🔔 <b>Price Alert Set!</b>\n"
        f"Token: <b>{coin_info['name']} ({coin_info['symbol']})</b>\n"
        f"Current Price: {format_price(current_price)}\n"
        f"Target Alert: Notify when price goes <b>{condition} {format_price(target_price)}</b>",
        parse_mode="HTML"
    )


async def disclaimer_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends financial risk disclaimer."""
    disclaimer_text = (
        "⚠️ <b>Risk Management & Financial Disclaimer</b>\n\n"
        "Trading cryptocurrencies involves substantial risk of loss. The recommendations produced by this bot are generated via quantitative algorithms (RSI, MACD, ATR Volatility, Market Sentiment) for informational purposes.\n\n"
        "• Always use a strict Stop-Loss on every trade.\n"
        "• Never risk more than 1%-2% of your total capital on a single position.\n"
        "• Use <code>/risk &lt;capital&gt; &lt;token&gt;</code> to manage position sizing."
    )
    await update.message.reply_text(disclaimer_text, parse_mode="HTML")


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles inline button clicks."""
    query = update.callback_query
    await query.answer()

    data = query.data
    user_id = query.from_user.id

    if data.startswith("add_"):
        parts = data.split("_")
        coin_id = parts[1]
        symbol = parts[2]
        db.add_to_watchlist(user_id, coin_id, symbol, symbol)
        await query.edit_message_caption(caption=f"✅ Added {symbol} to Watchlist!") if query.message.caption else await query.message.reply_text(f"✅ Added {symbol} to Watchlist!")

    elif data.startswith("refresh_"):
        coin_id = data.split("_")[1]
        market_data = market_client.get_coin_market_data(coin_id, VS_CURRENCY)
        if market_data:
            ohlc_data = market_client.get_ohlc(coin_id, VS_CURRENCY, days=30)
            fng_data = market_client.get_fear_and_greed_index()
            analysis = SignalEngine.analyze_token(market_data, ohlc_data, fng_data)
            new_text = format_signal_message(analysis)
            try:
                await query.edit_message_text(new_text, parse_mode="HTML", reply_markup=query.message.reply_markup)
            except Exception:
                pass


async def check_alerts_job(context: ContextTypes.DEFAULT_TYPE):
    """Background task to check active user price alerts."""
    alerts = db.get_active_alerts()
    if not alerts:
        return

    for alert in alerts:
        coin_id = alert["coin_id"]
        market_data = market_client.get_coin_market_data(coin_id, VS_CURRENCY)
        if not market_data:
            continue

        current_price = market_data.get("current_price", 0.0)
        target_price = alert["target_price"]
        condition = alert["condition"]

        triggered = False
        if condition == "ABOVE" and current_price >= target_price:
            triggered = True
        elif condition == "BELOW" and current_price <= target_price:
            triggered = True

        if triggered:
            user_id = alert["user_id"]
            symbol = alert["symbol"]
            msg = (
                f"🚨 <b>PRICE ALERT TRIGGERED!</b> 🚨\n\n"
                f"Token: <b>{symbol}</b>\n"
                f"Target Price: <code>{format_price(target_price)}</code>\n"
                f"Current Price: <code>{format_price(current_price)}</code>\n\n"
                f"<i>Condition met ({condition}). Use <code>/signal {symbol}</code> to analyze next move!</i>"
            )
            try:
                await context.bot.send_message(chat_id=user_id, text=msg, parse_mode="HTML")
                db.deactivate_alert(alert["id"])
            except Exception as e:
                logger.error(f"Failed to send alert notification to {user_id}: {e}")


def main():
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        print("\n" + "=" * 60)
        print("❌ TELEGRAM_BOT_TOKEN is missing!")
        print("Please set your TELEGRAM_BOT_TOKEN in the .env file or environment.")
        print("See README.md for instructions on getting a free token from @BotFather.")
        print("=" * 60 + "\n")

    # Start HTTP Health Check Server in a background thread for Render Free Web Service support
    t = threading.Thread(target=start_health_check_server, daemon=True)
    t.start()

    app = Application.builder().token(TELEGRAM_BOT_TOKEN if TELEGRAM_BOT_TOKEN else "DUMMY_TOKEN").build()

    # Handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", start_command))
    app.add_handler(CommandHandler("signal", signal_command))
    app.add_handler(CommandHandler("risk", risk_command))
    app.add_handler(CommandHandler("top", top_command))
    app.add_handler(CommandHandler("add", add_watchlist_command))
    app.add_handler(CommandHandler("remove", remove_watchlist_command))
    app.add_handler(CommandHandler("watchlist", watchlist_command))
    app.add_handler(CommandHandler("alert", alert_command))
    app.add_handler(CommandHandler("disclaimer", disclaimer_command))
    app.add_handler(CallbackQueryHandler(callback_handler))

    if app.job_queue:
        app.job_queue.run_repeating(check_alerts_job, interval=ALERT_CHECK_INTERVAL, first=10)

    print("🚀 Starting Professional Crypto Financial Suggestion Bot...")
    app.run_polling()


if __name__ == "__main__":
    main()
