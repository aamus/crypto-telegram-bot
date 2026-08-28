# 🤖 Professional Crypto Advisor & Signal Telegram Bot

A high-performance, quantitative Telegram bot built for crypto traders. It provides **real-time financial suggestions**, **institutional multi-indicator signals (BUY/SELL/HOLD)**, **Fear & Greed Index sentiment integration**, **volatility-based trade setups (Entry, Take-Profit, Stop-Loss)**, and a **Position Sizing Risk Calculator**.

---

## 🌟 Key Trader Features

- 🧠 **Institutional Scoring Engine (-10 to +10)**: Combines **RSI (14)**, **MACD Crossover**, **EMA Trend Alignment (20/50)**, 24h momentum, and **Crypto Fear & Greed Index** into a single Trader Score.
- 🛡️ **Position Sizing & Risk Calculator (`/risk`)**: Calculates the **exact dollar amount** and **exact coin quantity** to buy so you never risk more than 1.5% - 2% of your total portfolio on any single trade.
- 📈 **ATR Volatility Stop-Loss & Target Placement**: Dynamically calculates Stop-Loss and Take-Profit prices using 14-period Average True Range (ATR), ensuring a minimum **1:2+ Risk-to-Reward ratio**.
- 🏆 **Top Crypto Radar (`/top`)**: Scans top crypto assets and highlights accumulation zones or profit-taking targets.
- ⭐ **Personal Watchlist (`/watchlist`)**: Save your favorite coins for 1-click signal refreshing.
- 🔔 **Automated Price Target Alerts (`/alert`)**: Monitors target price levels in the background and sends instant Telegram notifications when crossed.

---

## 📜 Telegram Bot Commands

| Command | Usage / Description |
| :--- | :--- |
| `/start` / `/help` | Welcome guide and overview of commands |
| `/signal <token>` | Get instant institutional trade signal & score for any coin (e.g. `/signal btc`, `/signal sol`) |
| `/risk <capital> <token> [risk%]` | Calculate exact position size and dollar risk (e.g. `/risk 5000 btc` or `/risk 10000 sol 2`) |
| `/top` | Scan top cryptocurrencies for active signals |
| `/watchlist` | View your saved watchlist of coins |
| `/add <token>` / `/remove <token>` | Add/remove coins from your watchlist |
| `/alert <token> <price>` | Set a custom price alert (e.g., `/alert btc 95000`) |
| `/disclaimer` | View risk management rules and financial disclaimer |

---

## 💡 Example Command: `/risk 5000 btc`

```html
🛡️ POSITION SIZING & RISK CALCULATOR
Token: Bitcoin (BTC)

💼 Total Portfolio Capital: $5,000.00
⚠️ Risk Tolerance per Trade: 1.5% (Max Loss: $75.00)

📥 Entry Price: $95,000.00
🛑 Strict Stop-Loss Price: $89,300.00

🎯 YOUR RECOMMENDED TRADE ALLOCATION:
• Buy Quantity: 0.0132 BTC
• Total Dollar Value to Buy: $1,250.00 (25.0% of total portfolio)

By purchasing exactly 0.0132 BTC, if the price hits your Stop-Loss at $89,300, your loss will be EXACTLY $75.00 (1.5% of portfolio). This protects your account from liquidation!
```

---

## 🛠️ Step-by-Step Setup Guide

### Step 1: Get a Telegram Bot Token (Free)
1. Open Telegram and search for `@BotFather`.
2. Click **Start** and send `/newbot`.
3. Choose a name and username for your bot.
4. Copy your **API Token**.

### Step 2: Install Python Dependencies
```bash
pip install -r requirements.txt
```

### Step 3: Configure `.env`
Create a `.env` file in the project folder and paste your Bot Token:
```env
TELEGRAM_BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN_HERE
```

### Step 4: Run the Bot
```bash
python bot.py
```

---

## 🧪 Automated Tests
Run the standalone test suite to verify technical indicator formulas, position calculator, and database alerts:
```bash
python test_bot.py
```
