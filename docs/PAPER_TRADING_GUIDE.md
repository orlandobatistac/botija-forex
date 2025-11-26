# Paper Trading System Guide

## 📋 Overview

The **Paper Trading Mode** allows you to test trading strategies **without financial risk**. It simulates real trading using:
- Real-time Kraken market data (prices)
- Simulated wallet (JSON persistence)
- Trade logs (CSV format)
- Same trading logic as REAL mode

Perfect for:
- ✅ Testing strategies before enabling real trading
- ✅ Debugging bot behavior
- ✅ Validating indicator signals
- ✅ Practicing manual trades via API

## 🎮 Switching Modes

### PAPER Mode (Default & Safe)
```python
# backend/app/services/trading_mode.py
MODE = "PAPER"  # Simulated trading
```

### REAL Mode (Live Trading)
```python
# backend/app/services/trading_mode.py
MODE = "REAL"  # Live Kraken API trading
```

**⚠️ WARNING**: Only set to REAL after thoroughly testing in PAPER mode!

## 🏦 Paper Wallet System

### Wallet File
```
backend/data/paper_wallet.json
```

Structure:
```json
{
  "usd_balance": 1000.0,
  "btc_balance": 0.0,
  "last_buy_price": null,
  "trailing_stop": null,
  "timestamps": {
    "created": "2024-01-15T10:30:00Z",
    "last_update": "2024-01-15T10:35:42Z"
  }
}
```

- **usd_balance**: Available USD for buying
- **btc_balance**: Current BTC position
- **last_buy_price**: Entry price of current position
- **trailing_stop**: Dynamic stop-loss price
- **timestamps**: Track operation times

### Initial Balance
Default: **$1,000 USD** and **0.0 BTC**

Reset anytime via API:
```bash
curl -X POST http://localhost:8001/api/v1/paper/reset?initial_usd=5000
```

## 📊 Trade Logging

### Trade Log File
```
backend/data/paper_trades.csv
```

Format:
```csv
timestamp,type,price,volume,balance_usd,balance_btc
2024-01-15T10:35:42Z,BUY,50000.0,0.004,800.0,0.004
2024-01-15T10:45:10Z,SELL,51000.0,0.004,1004.0,0.0
```

Fields:
- **timestamp**: ISO 8601 format
- **type**: BUY or SELL
- **price**: Execution price (no slippage simulation)
- **volume**: BTC amount
- **balance_usd**: USD after trade
- **balance_btc**: BTC after trade

## 🎯 API Endpoints (Paper Trading)

### Get Wallet Status
```bash
GET /api/v1/paper/wallet
```

Response:
```json
{
  "usd_balance": 1000.0,
  "btc_balance": 0.0,
  "last_buy_price": null,
  "trailing_stop": null,
  "timestamps": {...}
}
```

### Get Recent Trades
```bash
GET /api/v1/paper/trades?limit=20
```

Response:
```json
{
  "trades": [
    {
      "timestamp": "2024-01-15T10:35:42Z",
      "type": "BUY",
      "price": "50000.0",
      "volume": "0.004",
      "balance_usd": "800.0",
      "balance_btc": "0.004"
    }
  ],
  "total": 1
}
```

### Simulate BUY Order
```bash
POST /api/v1/paper/simulate-buy
Content-Type: application/json

{
  "price": 50000.0,
  "usd_amount": 200.0
}
```

Response:
```json
{
  "success": true,
  "message": "Paper buy: 0.00400000 BTC at $50,000.00 | USD: $800.00 | BTC: 0.00400000",
  "wallet": {...}
}
```

### Simulate SELL Order
```bash
POST /api/v1/paper/simulate-sell
Content-Type: application/json

{
  "price": 51000.0,
  "btc_amount": 0.004
}
```

Response:
```json
{
  "success": true,
  "message": "Paper sell: 0.00400000 BTC at $51,000.00 | P/L: $+4.00 | USD: $1004.00 | BTC: 0.00000000",
  "wallet": {...}
}
```

### Reset Wallet
```bash
POST /api/v1/paper/reset?initial_usd=5000
```

Response:
```json
{
  "message": "Paper wallet reset to $5000.00",
  "wallet": {
    "usd_balance": 5000.0,
    "btc_balance": 0.0,
    ...
  }
}
```

### Get Statistics
```bash
GET /api/v1/paper/stats
```

Response:
```json
{
  "wallet": {...},
  "stats": {
    "total_trades": 5,
    "buy_trades": 3,
    "sell_trades": 2,
    "position_open": false
  }
}
```

## 🤖 Automated Paper Trading

The trading bot automatically uses paper mode when `MODE = "PAPER"`:

```bash
# Start the API (scheduler runs in background)
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

The scheduler will:
1. Execute a trading cycle every **1 hour** (configurable in `.env`)
2. Fetch real Kraken price data
3. Calculate indicators (EMA20, EMA50, RSI14)
4. Get AI signal from OpenAI
5. Execute buy/sell in **simulated wallet**
6. Log trades to CSV
7. Send Telegram alerts (if configured)

### Configuration

Edit `.env`:
```bash
# Trading settings
TRADING_INTERVAL=3600         # Seconds between cycles (1 hour)
TRADE_AMOUNT_USD=100          # USD per trade
MIN_BALANCE_USD=65            # Minimum USD to trade
TRAILING_STOP_PERCENTAGE=0.99 # Stop at 99% of peak

# Optional: Set to PAPER or REAL
TRADING_MODE=PAPER            # Use in app/services/trading_mode.py
```

## 🧪 Testing Paper Trading

Run the test suite:
```bash
cd backend
python -m pytest tests/test_paper_trading.py -v
```

Tests include:
- ✅ Buy/sell execution
- ✅ Balance validation
- ✅ Trailing stop logic
- ✅ Wallet persistence
- ✅ Trade logging
- ✅ Factory pattern (mode switching)

All tests pass:
```
======================== 15 passed in 0.78s ========================
```

## 💡 Example Workflow

### 1. Start with Paper Mode
```bash
# backend/app/services/trading_mode.py
MODE = "PAPER"  # ← Safe for testing
```

### 2. Run Some Trades
```bash
# Simulate a buy
curl -X POST http://localhost:8001/api/v1/paper/simulate-buy \
  -H "Content-Type: application/json" \
  -d '{"price": 50000, "usd_amount": 200}'

# Simulate a sell (after price goes up)
curl -X POST http://localhost:8001/api/v1/paper/simulate-sell \
  -H "Content-Type: application/json" \
  -d '{"price": 51000, "btc_amount": 0.004}'
```

### 3. Check Results
```bash
# View wallet
curl http://localhost:8001/api/v1/paper/wallet

# View trades
curl http://localhost:8001/api/v1/paper/trades

# View stats
curl http://localhost:8001/api/v1/paper/stats
```

### 4. Run Full Test Cycle
```bash
# Let bot run automatically (check logs)
tail -f logs/bot.log

# Or trigger manual cycle
curl -X POST http://localhost:8001/api/v1/bot/cycle
```

### 5. Only Then Go REAL
```bash
# After validating strategy:
# backend/app/services/trading_mode.py
MODE = "REAL"  # ← Live Kraken trading

# Restart the bot
python -m uvicorn app.main:app --reload
```

## ⚙️ Under the Hood

### Factory Pattern
The bot automatically selects the correct trading engine:

```python
# backend/app/services/modes/factory.py
def get_trading_engine(kraken_client=None):
    if MODE == "PAPER":
        return PaperTradingEngine()      # Simulated
    elif MODE == "REAL":
        return RealTradingEngine(kraken_client)  # Live
```

### Both Engines Implement Same Interface
```python
# backend/app/services/modes/base.py
class TradingEngine(ABC):
    @abstractmethod
    def buy(price: float, usd_amount: float) -> (bool, str): ...
    
    @abstractmethod
    def sell(price: float, btc_amount: float) -> (bool, str): ...
    
    @abstractmethod
    def update_trailing_stop(current_price: float) -> dict: ...
```

So the trading logic is **identical** in both modes:
- Same indicator calculations
- Same AI validation
- Same order execution (just different backend)

## 🚀 When to Switch to REAL Mode

✅ **After confirming all of these:**
1. Strategy passed at least 10 trades in paper mode
2. P/L is consistently positive
3. Trailing stop logic triggered correctly
4. Telegram alerts are working
5. Indicator signals align with expectations
6. You understand the risks

⚠️ **NEVER go REAL if:**
- Tests are failing
- Trades are losing money
- You don't understand the strategy
- Market conditions are unusual
- You haven't tested with different price movements

## 📝 Notes

- Paper trading **uses real Kraken prices** but simulated execution
- **No slippage simulation** (assumes exact price execution)
- **No partial fills** (assumes full volume execution)
- Wallet persists between sessions (JSON file)
- Trade history is permanent (CSV append-only)

## 🆘 Troubleshooting

### Wallet shows $0 USD
```bash
# Reset to initial balance
curl -X POST http://localhost:8001/api/v1/paper/reset?initial_usd=1000
```

### Trades not appearing in CSV
```bash
# Check file exists and has headers
cat backend/data/paper_trades.csv

# If missing, create new
touch backend/data/paper_trades.csv
echo "timestamp,type,price,volume,balance_usd,balance_btc" > backend/data/paper_trades.csv
```

### Mode not switching
```bash
# Verify MODE variable
grep "^MODE" backend/app/services/trading_mode.py

# Should be "PAPER" or "REAL"
# Changes take effect on next restart
```

## 📚 Related Files

- **Configuration**: `.env.example`
- **Trading Logic**: `backend/app/services/trading_bot.py`
- **Indicators**: `backend/app/services/technical_indicators.py`
- **AI Validation**: `backend/app/services/ai_validator.py`
- **Database Models**: `backend/app/models.py`
