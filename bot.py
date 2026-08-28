import logging
import asyncio
import os
from aiohttp import web

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    filters,
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


async def handle_health_check(request):
    """Health check endpoint for Render/Koyeb web services."""
    return web.Response(text="Crypto Telegram Bot is active and running 24/7!", content_type="text/plain")


def format_price(price: float) -> str:
    """Formats price with appropriate precision based on size."""
    if price >= 1.0:
        return f"${price:,.2f}"
    elif price >= 0.0001:
        return f"${price:.4f}"
    else:
        return f"${price:.8f}"


def get_persistent_menu_keyboard() -> ReplyKeyboardMarkup:
    """Creates a persistent bottom reply keyboard always visible at the bottom of Telegram screen."""
    keyboard = [
        ["🚀 BTC Signal", "📈 ETH Signal", "☀️ SOL Signal"],
        ["🏆 Top Signals", "⭐ My Watchlist"],
        ["🛡️ Risk Calculator", "⚠️ Disclaimer"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Creates an interactive inline keyboard menu for quick command access."""
    keyboard = [
        [
            InlineKeyboardButton("🚀 BTC Signal", callback_data="cmd_sig_btc"),
            InlineKeyboardButton("📈 ETH Signal", callback_data="cmd_sig_eth"),
            InlineKeyboardButton("☀️ SOL Signal", callback_data="cmd_sig_sol"),
        ],
        [
            InlineKeyboardButton("🏆 Top 10 Signals", callback_data="cmd_top"),
            InlineKeyboardButton("⭐ My Watchlist", callback_data="cmd_watchlist"),
        ],
        [
            InlineKeyboardButton("🛡️ Position Risk Calculator", callback_data="cmd_risk_help"),
            InlineKeyboardButton("⚠️ Risk Disclaimer", callback_data="cmd_disclaimer"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def format_signal_message(analysis: dict) -> str:
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
    """Sends welcome message with persistent bottom keyboard + interactive inline buttons."""
    welcome_text = (
        "🤖 <b>Welcome to Professional Crypto Advisor & Signal Bot!</b>\n\n"
        "Permanent menu buttons have been activated at the bottom of your screen!\n\n"
        "Click any button below to get live signals, market rankings, and risk calculations instantly:"
    )
    if update.callback_query:
        await update.callback_query.message.reply_text(welcome_text, parse_mode="HTML", reply_markup=get_main_menu_keyboard())
    else:
        await update.message.reply_text(welcome_text, parse_mode="HTML", reply_markup=get_persistent_menu_keyboard())
        await update.message.reply_text("⚡ <b>Quick Action Menu:</b>", parse_mode="HTML", reply_markup=get_main_menu_keyboard())


async def signal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /signal <token> command."""
    if not context.args:
        if update.message:
            await update.message.reply_text(
                "❌ Usage: <code>/signal &lt;token&gt;</code>\nExample: <code>/signal btc</code>\n\nOr click a quick signal button below:",
                parse_mode="HTML",
                reply_markup=get_main_menu_keyboard()
            )
        return

    query = " ".join(context.args)
    if update.message:
        status_msg = await update.message.reply_text(f"🔍 Analyzing technical indicators & multi-timeframe trends for <b>{query.upper()}</b>...", parse_mode="HTML")
    elif update.callback_query:
        status_msg = await update.callback_query.message.reply_text(f"🔍 Analyzing technical indicators & multi-timeframe trends for <b>{query.upper()}</b>...", parse_mode="HTML")
    else:
        return

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
        ],
        [
            InlineKeyboardButton("⭐ My Watchlist", callback_data="cmd_watchlist"),
            InlineKeyboardButton("🔙 Main Menu", callback_data="cmd_menu")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await status_msg.edit_text(formatted_msg, parse_mode="HTML", reply_markup=reply_markup)


async def risk_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /risk <capital> <token> [risk_pct] command."""
    if len(context.args) < 2:
        msg_text = (
            "🛡️ <b>Position Calculator Usage:</b>\n"
            "<code>/risk &lt;total_capital&gt; &lt;token&gt; [risk_percent]</code>\n\n"
            "<b>Example:</b> <code>/risk 5000 btc</code> (Risks 1.5% of $5,000 portfolio on BTC)\n"
            "<b>Example:</b> <code>/risk 10000 sol 2</code> (Risks 2.0% of $10,000 portfolio on SOL)"
        )
        if update.message:
            await update.message.reply_text(msg_text, parse_mode="HTML", reply_markup=get_main_menu_keyboard())
        elif update.callback_query:
            await update.callback_query.message.reply_text(msg_text, parse_mode="HTML", reply_markup=get_main_menu_keyboard())
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
    await update.message.reply_text(msg, parse_mode="HTML", reply_markup=get_main_menu_keyboard())


async def top_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /top command showing top 10 market tokens with signals."""
    if update.message:
        status_msg = await update.message.reply_text("📊 Fetching top market crypto signals...", parse_mode="HTML")
    elif update.callback_query:
        status_msg = await update.callback_query.message.reply_text("📊 Fetching top market crypto signals...", parse_mode="HTML")
    else:
        return

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

    lines.append("\n<i>Click any button below to generate full signal analysis:</i>")
    await status_msg.edit_text("\n".join(lines), parse_mode="HTML", reply_markup=get_main_menu_keyboard())


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
        await update.message.reply_text(f"✅ Added <b>{coin_info['name']} ({coin_info['symbol']})</b> to your watchlist!", parse_mode="HTML", reply_markup=get_main_menu_keyboard())
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
    await update.message.reply_text(f"🗑️ Removed <b>{coin_info['name']}</b> from your watchlist.", parse_mode="HTML", reply_markup=get_main_menu_keyboard())


async def watchlist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /watchlist command with 1-click Signal and Remove buttons."""
    user_id = update.effective_user.id if update.effective_user else update.callback_query.from_user.id
    items = db.get_user_watchlist(user_id)

    if not items:
        msg_text = "📋 <b>Your Watchlist is Empty!</b>\n\nAdd tokens by typing <code>/add &lt;token&gt;</code> (e.g. <code>/add sol</code>)!"
        if update.message:
            await update.message.reply_text(msg_text, parse_mode="HTML", reply_markup=get_main_menu_keyboard())
        elif update.callback_query:
            await update.callback_query.message.reply_text(msg_text, parse_mode="HTML", reply_markup=get_main_menu_keyboard())
        return

    keyboard = []
    for item in items:
        symbol = item["symbol"].upper()
        coin_id = item["coin_id"]
        keyboard.append([
            InlineKeyboardButton(f"🔍 {symbol} Signal", callback_data=f"cmd_sig_{symbol.lower()}"),
            InlineKeyboardButton(f"🗑️ Remove {symbol}", callback_data=f"del_{coin_id}_{symbol}")
        ])

    keyboard.append([InlineKeyboardButton("🔙 Main Menu", callback_data="cmd_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    lines = ["⭐ <b>YOUR SAVED CRYPTO WATCHLIST</b>\n", "Click 🔍 to see signal, or 🗑️ to remove a token:\n"]
    for item in items:
        lines.append(f"• <b>{item['name']} ({item['symbol'].upper()})</b>")

    if update.message:
        await update.message.reply_text("\n".join(lines), parse_mode="HTML", reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.message.reply_text("\n".join(lines), parse_mode="HTML", reply_markup=reply_markup)


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
        parse_mode="HTML",
        reply_markup=get_main_menu_keyboard()
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
    if update.message:
        await update.message.reply_text(disclaimer_text, parse_mode="HTML", reply_markup=get_main_menu_keyboard())
    elif update.callback_query:
        await update.callback_query.message.reply_text(disclaimer_text, parse_mode="HTML", reply_markup=get_main_menu_keyboard())


async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles text messages sent by user or persistent keyboard button taps."""
    text = update.message.text.strip()
    if text == "🚀 BTC Signal":
        context.args = ["btc"]
        await signal_command(update, context)
    elif text == "📈 ETH Signal":
        context.args = ["eth"]
        await signal_command(update, context)
    elif text == "☀️ SOL Signal":
        context.args = ["sol"]
        await signal_command(update, context)
    elif text == "🏆 Top Signals":
        await top_command(update, context)
    elif text == "⭐ My Watchlist":
        await watchlist_command(update, context)
    elif text == "🛡️ Risk Calculator":
        await risk_command(update, context)
    elif text == "⚠️ Disclaimer":
        await disclaimer_command(update, context)
    else:
        # Treat single word inputs (e.g. 'btc', 'solana', 'pepe') as signal requests!
        if len(text.split()) == 1 and not text.startswith("/"):
            context.args = [text]
            await signal_command(update, context)


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles inline button clicks."""
    query = update.callback_query
    await query.answer()

    data = query.data
    user_id = query.from_user.id

    if data.startswith("cmd_sig_"):
        symbol_target = data.replace("cmd_sig_", "")
        context.args = [symbol_target]
        await signal_command(update, context)
    elif data == "cmd_top":
        await top_command(update, context)
    elif data == "cmd_watchlist":
        await watchlist_command(update, context)
    elif data == "cmd_risk_help":
        await risk_command(update, context)
    elif data == "cmd_disclaimer":
        await disclaimer_command(update, context)
    elif data == "cmd_menu":
        await start_command(update, context)
    elif data.startswith("del_"):
        parts = data.split("_")
        coin_id = parts[1]
        symbol = parts[2]
        db.remove_from_watchlist(user_id, coin_id)
        await query.message.reply_text(f"🗑️ Removed <b>{symbol}</b> from Watchlist!", parse_mode="HTML")
        await watchlist_command(update, context)
    elif data.startswith("add_"):
        parts = data.split("_")
        coin_id = parts[1]
        symbol = parts[2]
        db.add_to_watchlist(user_id, coin_id, symbol, symbol)
        try:
            await query.message.reply_text(f"✅ Added {symbol} to Watchlist!", reply_markup=get_main_menu_keyboard())
        except Exception:
            pass
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


async def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN", TELEGRAM_BOT_TOKEN)
    if not token or token == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        logger.error("TELEGRAM_BOT_TOKEN is missing!")
        return

    # Build Telegram Bot Application
    app = Application.builder().token(token).build()

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
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler))

    # Initialize and start bot polling
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    logger.info("🤖 Telegram Bot Polling Started Successfully!")

    # Start Aiohttp Web Server for Cloud Health Checks
    port = int(os.environ.get("PORT", 8080))
    server_app = web.Application()
    server_app.router.add_get("/", handle_health_check)
    server_app.router.add_get("/health", handle_health_check)

    runner = web.AppRunner(server_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"🌐 Cloud Health Check Web Server running on port {port}")

    # Keep async loop running continuously
    try:
        await asyncio.Event().wait()
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
