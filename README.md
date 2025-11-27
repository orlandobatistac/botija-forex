# Botija Forex - AI-Powered Forex Trading Bot

Automated Forex trading bot with OANDA integration and AI validation.

## Features

- 📊 **Forex Trading** with OANDA API (Demo & Live)
- 🤖 **AI Validation** with OpenAI GPT
- 📈 **Technical Indicators**: EMA, RSI, MACD, Bollinger Bands
- 📱 **Telegram Alerts** in real-time
- 🛡️ **Risk Management**: Stop Loss, Take Profit, Trailing Stop
- 🔄 **Multi-Timeframe Analysis**: H1 + H4 confirmation
- 📋 **Web Dashboard** with Alpine.js + TailwindCSS
- 🚀 **Auto-Deploy** via GitHub Actions

## Live Demo

🌐 **https://botija-forex.orlandobatista.dev**

## Project Structure

```
botija-forex/
├── backend/
│   ├── app/
│   │   ├── config.py         # Configuration
│   │   ├── database.py       # SQLite/PostgreSQL
│   │   ├── main.py           # FastAPI app
│   │   ├── models.py         # SQLAlchemy models
│   │   ├── scheduler.py      # APScheduler (4h cycles)
│   │   ├── schemas.py        # Pydantic schemas
│   │   ├── routers/          # API endpoints
│   │   └── services/         # Business logic
│   └── tests/
├── frontend/
│   ├── index.html            # Main dashboard
│   ├── components/           # Alpine.js components
│   ├── stores/               # Global state (auth, app)
│   └── utils/                # API helpers
└── .github/workflows/        # CI/CD
```

## Installation

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Configuration

Create a `.env` file:

```env
# OANDA
OANDA_API_KEY=your_api_key
OANDA_ACCOUNT_ID=your_account_id
OANDA_ENVIRONMENT=demo
OANDA_GRANULARITY=H4

# OpenAI
OPENAI_API_KEY=your_openai_key

# Telegram (optional)
TELEGRAM_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Trading
TRADING_MODE=DEMO
DEFAULT_INSTRUMENT=EUR_USD
STOP_LOSS_PIPS=50
TAKE_PROFIT_PIPS=100
TRAILING_STOP_PIPS=30
```

## Running

```bash
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

## API Docs

- Swagger UI: http://localhost:8001/docs
- ReDoc: http://localhost:8001/redoc

## Tests

```bash
cd backend
python -m pytest -v
```

## Deployment

Auto-deploy is configured via GitHub Actions. Every push to `main` triggers:
1. SSH to VPS
2. Pull latest code
3. Install dependencies
4. Restart service

## License

MIT
