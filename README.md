# Botija Forex - AI-Powered Forex Trading Bot

Bot de trading Forex automatizado con integración OANDA y validación AI.

## Características

- 📊 **Trading Forex** con OANDA API (Demo y Live)
- 🤖 **Validación AI** con OpenAI GPT
- 📈 **Indicadores Técnicos**: EMA, RSI, MACD, Bollinger Bands
- 📱 **Alertas Telegram** en tiempo real
- 🛡️ **Gestión de Riesgo**: Stop Loss, Take Profit, Trailing Stop
- 📋 **Dashboard Web** con Alpine.js + TailwindCSS

## Estructura

```
botija-forex/
├── backend/
│   ├── app/
│   │   ├── config.py         # Configuración
│   │   ├── database.py       # SQLite/PostgreSQL
│   │   ├── main.py           # FastAPI app
│   │   ├── models.py         # SQLAlchemy models
│   │   ├── schemas.py        # Pydantic schemas
│   │   ├── routers/          # API endpoints
│   │   └── services/         # Lógica de negocio
│   └── tests/
├── frontend/
│   └── index.html            # Dashboard
└── requirements.txt
```

## Instalación

```bash
cd backend
pip install -r requirements.txt
```

## Configuración

Crea un archivo `.env`:

```env
# OANDA
OANDA_API_KEY=your_api_key
OANDA_ACCOUNT_ID=your_account_id
OANDA_ENVIRONMENT=demo

# OpenAI
OPENAI_API_KEY=your_openai_key

# Telegram (opcional)
TELEGRAM_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Trading
TRADING_MODE=DEMO
DEFAULT_INSTRUMENT=EUR_USD
```

## Ejecución

```bash
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

## API Docs

- Swagger UI: http://localhost:8001/docs
- ReDoc: http://localhost:8001/redoc
