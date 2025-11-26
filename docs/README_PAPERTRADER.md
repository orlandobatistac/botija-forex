# Paper Trading Layer — Kraken AI Trading Bot

## 📌 Overview

This module adds a **fully realistic Paper Trading system** to the Kraken AI Trading Bot.  
It allows the bot to run in two modes:

- **REAL MODE** → Executes actual trades using Kraken Spot API  
- **PAPER MODE** → Simulates trades locally, using real market data  

The trading logic, indicators, AI signals, trailing stop, and alerts remain identical in both modes. Only the execution layer changes.

This feature allows safe testing, debugging, and strategy validation without risking real funds.

---

## 🎯 Objectives

The Paper Trading layer must:

1. **Simulate trading operations with real Kraken market data.**
2. **Mirror Kraken Spot trading behavior** as closely as possible.
3. Allow switching modes by changing a single setting:
   ```python
   MODE = "PAPER"
   ```
4. Maintain a persistent **virtual wallet**:
   - USD balance  
   - BTC balance  
   - Last Buy Price  
   - Trailing Stop  
5. Log every simulated trade with timestamps.
6. Be 100% compatible with:
   - Buy signals  
   - Sell signals  
   - Dynamic trailing stop  
   - Telegram alerts  
   - AI signal validation  

---

## 📁 Required Files

### 1. `trading_mode.py`
Controls the active execution mode.

```python
MODE = "PAPER"   # or "REAL"
```

---

### 2. `paper_wallet.json`

Persistent storage for simulated balances.

```json
{
  "usd_balance": 100.00,
  "btc_balance": 0.0,
  "last_buy_price": null,
  "trailing_stop": null
}
```

---

### 3. `paper_trades.csv`

Log file for simulated trades:

```
timestamp,type,price,volume
2025-01-01 09:00:00,BUY,95000,0.00065
2025-01-01 11:30:00,SELL,98000,0.00065
```

---

## 🧩 Architecture

### Base Class (Interface)

A generic TradingEngine interface used by both REAL and PAPER modes:

```python
class TradingEngine:
    def load_balances(self): pass
    def buy(self, price, usd_amount): pass
    def sell(self, price): pass
    def update_trailing(self, price): pass
```

---

### Real Mode Implementation

`modes/real.py`

Handles:

- Kraken Spot API buy orders  
- Kraken Spot API sell orders  
- Reading real balances  
- No local wallet files  

---

### Paper Mode Implementation

`modes/paper.py`

Handles:

- Reading/writing `paper_wallet.json`
- Logging simulated trades to `paper_trades.csv`
- Fully simulated BUY/SELL operations

#### BUY Simulation:

```
volume = usd_amount / price
usd_balance -= usd_amount
btc_balance += volume
last_buy_price = price
trailing_stop = price * 0.99
```

#### SELL Simulation:

```
usd_balance += btc_balance * price
btc_balance = 0
trailing_stop = null
```

#### Trailing Stop Simulation:

```
new_stop = max(old_stop, price * 0.99)
if price <= trailing_stop → SELL
```

---

## 🔧 Mode Selection

The bot automatically chooses between engines:

```python
from trading_mode import MODE
from modes.real import KrakenTradingReal
from modes.paper import KrakenTradingPaper

engine = KrakenTradingReal() if MODE == "REAL" else KrakenTradingPaper()
```

No other code modifications required.

---

## 🔄 Bot Workflow With Paper Mode

1. Load MODE (REAL or PAPER)
2. Load real or simulated balances
3. Fetch real Kraken OHLC data
4. Compute indicators (EMA20, EMA50, RSI14)
5. Ask OpenAI for BUY / SELL / HOLD signal
6. If BUY conditions match:
   - REAL MODE → Place Kraken limit order  
   - PAPER MODE → Simulate BUY in local wallet  
7. If SELL conditions match:
   - REAL MODE → Execute real sell  
   - PAPER MODE → Simulate SELL  
8. Update trailing stop in both modes
9. Send Telegram alerts
10. Log trades (real or paper)

---

## 📡 Telegram Alerts

Paper Trading sends the same alerts as Real Trading:

- “BUY executed (paper mode)”  
- “SELL executed (paper mode)”  
- “Trailing stop updated”  
- “Trailing stop hit — sold (paper mode)”  

This ensures the bot behaves identically from the user's perspective.

---

## 🛡 Benefits of the Paper Trading Layer

- Safe testing with **zero financial risk**
- Uses real-time Kraken data for realistic behavior
- Reproduces the exact logic used in live trading
- Trains trailing stop and signal logic without losses
- Makes strategy tuning and debugging much easier
- Activates instantly by changing one variable

---

## 🚀 Expected Outcome

After implementation, the bot can:

- Switch freely between REAL and PAPER mode  
- Simulate BTC swing trading with high fidelity  
- Manage a virtual wallet with correct BTC/USD behavior  
- Apply dynamic trailing stops in simulation  
- Produce logs identical to real trading  
- Provide Telegram updates for full visibility  
- Allow safe, risk-free development and testing  

---

This feature enables a complete end-to-end paper trading environment identical to the real operating mode, ensuring safety and stability before deploying with real funds.
