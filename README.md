# Kraken AI Trading Bot (Swing Trading + Dynamic Trailing Stop + Telegram Alerts)

## 📌 Project Overview

This project is an **automated swing trading bot for Bitcoin (BTC)** using the **Kraken Spot API**, combined with **AI-based signal validation** (OpenAI), **technical indicators**, **dynamic trailing stop-loss**, and **Telegram alerts**.

The bot runs automatically on a **VPS or local machine**, executes **buy/sell decisions**, and actively manages open positions using a **real-time trailing stop engine**.

The core goal is:
- **Execute safe swing trades**
- **Avoid risky behavior (no leverage, no futures, spot trading only)**
- **Use AI + indicators together to confirm entries**
- **Protect profit with a trailing stop**
- **Send full status alerts to Telegram**

## 🚀 Quick Start

### Local Development

1. **Open in VS Code Devcontainer or Codespaces**
   ```bash
   # Dependencies install automatically
   ```

2. **Install dependencies manually (optional)**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

3. **Start the application**
   ```bash
   cd backend
   python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
   ```

4. **Access the application**
   - Frontend Dashboard: http://localhost:8001/
   - API Docs (Swagger): http://localhost:8001/docs
   - Health Check: http://localhost:8001/health

### Stack

- **Backend**: FastAPI + Python 3.12+ + SQLAlchemy
- **Frontend**: HTML5 + Alpine.js + TailwindCSS (no build required)
- **Database**: SQLite (dev) / PostgreSQL (prod)
- **Deployment**: VPS + Nginx + systemd
- **Trading**: Kraken Spot API + OpenAI + Technical Indicators
- **CI/CD**: GitHub Actions automated deployment

## 📁 Project Structure

```
kraken-ai-trading-bot/
├── .devcontainer/          # VS Code devcontainer config
├── .github/                # GitHub Actions & Copilot instructions
│   └── workflows/deploy.yml
├── .vscode/                # VS Code settings
├── backend/
│   ├── app/
│   │   ├── main.py         # FastAPI app entry point
│   │   ├── database.py     # SQLAlchemy setup
│   │   ├── models.py       # ORM models (Trade, BotStatus, Signal)
│   │   ├── schemas.py      # Pydantic schemas
│   │   └── routers/        # API endpoint groups
│   ├── tests/              # Unit tests with pytest
│   └── requirements.txt
├── frontend/
│   ├── index.html          # Main dashboard
│   ├── components/         # Reusable Alpine.js components
│   │   ├── ui/            # Modal, toast, etc.
│   │   ├── navigation/    # Navbar, sidebar
│   │   ├── forms/         # Form validation
│   │   ├── data/          # Data tables, pagination
│   │   └── layout/        # Header, footer
│   ├── stores/            # Alpine global state (auth, app)
│   ├── utils/             # API helpers, validation
│   ├── pages/             # Specific pages
│   ├── static/
│   │   ├── css/
│   │   ├── js/
│   │   └── img/
│   └── templates/         # Reusable HTML fragments
├── docs/
│   ├── DEVELOPMENT_GUIDE.md
│   ├── DEPLOYMENT_GUIDE.md
│   ├── API_DOCS.md
│   └── private/           # Local notes (not tracked)
├── scripts/
│   ├── start_dev.sh       # Development startup
│   └── deploy.sh          # VPS deployment
├── .env.example           # Environment template
├── .gitignore             # Git exclusions
├── manifest.json          # Project metadata
└── README.md             # This file
```

## 🧠 Trading Strategy Logic

### BUY Conditions (all must be true)
- EMA20 > EMA50
- RSI14 between 45-60
- OpenAI returns BUY signal
- USD balance ≥ $65
- No existing BTC position

**Action**: Place limit BUY order + initialize trailing stop at entry * 0.99

### SELL Conditions

**By Trailing Stop**:
If `current_price <= trailing_stop` → Market SELL

**By AI Signal**:
If OpenAI returns SELL, EMA20 < EMA50, and RSI < 40 → Market SELL

### Trailing Stop Logic
```python
new_trailing = max(old_trailing, current_price * 0.99)
```
- Only moves UP as price rises
- Never lowers (locks in profit)
- Automatically triggers SELL when hit

## 📡 Components & Architecture

- **Kraken API Integration**: Spot trading only, no leverage
- **Technical Indicators**: EMA20, EMA50, RSI14
- **OpenAI Signal Engine**: AI confirmation for entries/exits
- **Dynamic Trailing Stop Manager**: Real-time profit protection
- **Telegram Alert System**: Trade notifications + status updates
- **Web Dashboard**: Real-time monitoring and bot control
- **Database**: Trade history, signals, bot status tracking

## 🎯 Project Goals

1. **Create a fully autonomous BTC swing trading bot**
2. Use **Kraken Spot API** only (no margin, no futures)
3. Use AI signals (OpenAI) for confirmation:
   - BUY
   - SELL
   - HOLD
4. Calculate technical indicators locally:
   - EMA20
   - EMA50
   - RSI14
5. Execute:
   - **OCO BUY orders** (entry + TP + SL)
   - **Market SELL orders** based on trailing stop or AI signal
6. Implement a **dynamic trailing stop** that:
   - Moves ONLY upward as the price rises
   - Never lowers
   - Sells automatically if price hits the trail
7. Send **Telegram alerts** for:
   - Buy signals
   - Sell signals
   - Executed trades
   - Trailing stop updates
   - Trailing stop triggers
   - Daily bot status
8. Run automatically every:
   - **1 hour**, or
   - **Twice per day** (configurable)

## 🧠 Strategy Logic

### BUY Conditions:
Triggered only when:
- EMA20 > EMA50  
- RSI between 45 and 60  
- OpenAI returns **BUY**  
- USD balance ≥ 65  
- No existing BTC position  

Action:
- Execute a **limit BUY** order
- Initialize **trailing stop = entry_price * 0.99**

### SELL Conditions:
Triggered when you already hold BTC.

#### SELL by TRAILING STOP:
If:
```
current_price <= trailing_stop
```
→ Execute **market SELL**, reset trailing file.

#### SELL by AI Signal:
If:
- OpenAI returns **SELL**
- EMA20 < EMA50
- RSI < 40

→ Execute **market SELL**

### Trailing Stop Logic:
```
new_trailing = max(old_trailing, current_price * 0.99)
```

This guarantees:
- Trailing stop only moves UP as price rises
- Never moves down
- Protects accumulated profit

Stored in:
`trailing_stop.txt`

## 📡 Components & Architecture

### 1. Kraken API Integration
### 2. Technical Indicator Engine
### 3. OpenAI Signal Engine
### 4. Dynamic Trailing Stop Manager
### 5. Telegram Alerts System
### 6. Scheduler (cron)

## 🔧 Technologies Used
Python, krakenex, OpenAI SDK, pandas, ta, dotenv, requests

## 📁 Project Files
bot_trading_pro.py  
trailing_stop.txt  
.env  
bot_log.txt  
README.md

## 🔑 Environment Variables
KRAKEN_API_KEY  
KRAKEN_SECRET_KEY  
OPENAI_API_KEY  
TELEGRAM_TOKEN  
TELEGRAM_CHAT_ID

## 🚀 How It Works
Full workflow: indicators → AI → evaluate → buy/sell → trailing → alerts → logs.

## 🛡 Safety Rules
- No leverage  
- No futures  
- AI double validation  
- Caps per trade  
- Trailing stop protection

# Deployment test
# GitHub Actions deployment test
