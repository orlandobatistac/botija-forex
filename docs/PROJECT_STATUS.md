# 🤖 Kraken AI Trading Bot - State Summary

## 📊 Proyecto Completo (Paper Trading Implementado)

### ✅ Implementación Completada

**Fase 1: Scaffolding del Proyecto (31 archivos)**
- ✅ Estructura FastAPI + SQLAlchemy 
- ✅ Base de datos (SQLite/PostgreSQL)
- ✅ Modelos de datos (Trade, Signal, BotStatus)
- ✅ Frontend Alpine.js + TailwindCSS
- ✅ GitHub Actions CI/CD
- ✅ Devcontainer configurado

**Fase 2: Core Trading Modules (8 servicios)**
- ✅ `kraken_client.py` - Integración Kraken API (8 métodos)
- ✅ `technical_indicators.py` - Indicadores técnicos (5 tipos)
- ✅ `ai_validator.py` - Validación OpenAI GPT-3.5
- ✅ `telegram_alerts.py` - Sistema de alertas (6 tipos)
- ✅ `trailing_stop.py` - Gestor de stop dinámico
- ✅ `trading_bot.py` - Orquestador principal
- ✅ `config.py` - Gestión de configuración (20+ settings)
- ✅ API routers: bot.py, trades.py, indicators.py

**Fase 3: Paper Trading System (6 archivos + tests)**
- ✅ `trading_mode.py` - Selector de modo (PAPER/REAL)
- ✅ `modes/base.py` - Interfaz abstracta TradingEngine
- ✅ `modes/paper.py` - Simulador con wallet JSON + CSV logging
- ✅ `modes/real.py` - Engine real con Kraken API
- ✅ `modes/factory.py` - Factory pattern para selección de engine
- ✅ `paper.py` router - 6 endpoints API para paper trading
- ✅ `test_paper_trading.py` - 15 tests (todos pasando ✅)

**Fase 4: Scheduler & Automatización**
- ✅ `scheduler.py` - APScheduler para ciclos automáticos
- ✅ Ciclos cada hora (configurable via TRADING_INTERVAL)
- ✅ Graceful startup/shutdown con FastAPI lifespan events
- ✅ Manejo de credenciales faltantes (dev-friendly)

**Fase 5: API & Dashboard Integration**
- ✅ GET `/api/v1/bot/dashboard` - Estado unificado
- ✅ GET `/api/v1/paper/wallet` - Estado de wallet
- ✅ GET `/api/v1/paper/trades` - Historial de trades
- ✅ POST `/api/v1/paper/simulate-buy` - Compra manual
- ✅ POST `/api/v1/paper/simulate-sell` - Venta manual
- ✅ GET `/api/v1/paper/stats` - Estadísticas
- ✅ POST `/api/v1/paper/reset` - Reset de wallet
- ✅ Frontend integrado para polling cada 30 segundos

---

## 🎯 Funcionalidades Core

### Trading Engine (Modo PAPER)
```
Wallet JSON: backend/data/paper_wallet.json
├── USD Balance: $1,000 (inicial, configurable)
├── BTC Balance: 0.0 (comienza sin posición)
├── Entry Price: null (se establece en compra)
├── Trailing Stop: null (se calcula en compra)
└── Timestamps: Tracking automático

Trade Log CSV: backend/data/paper_trades.csv
├── timestamp: ISO 8601
├── type: BUY/SELL
├── price: Precio de ejecución
├── volume: BTC tradado
├── balance_usd: Saldo USD después
└── balance_btc: Saldo BTC después
```

### Flujo de Operación BUY
1. Indicadores técnicos validan (EMA20 > EMA50, RSI 45-60)
2. OpenAI confirma signal (BUY)
3. Ejecuta compra en modo paper:
   - Valida balance USD
   - Calcula volumen BTC = USD / precio
   - Decrementa USD, incrementa BTC
   - Establece trailing_stop = precio * 0.99
   - Registra en CSV

### Flujo de Operación SELL
1. Por Trailing Stop:
   - Si precio ≤ trailing_stop → venta automática
2. Por Signal AI:
   - OpenAI retorna SELL, EMA20 < EMA50, RSI < 40 → venta
3. Ejecución:
   - Calcula P/L = (precio_venta - precio_entrada) * volumen
   - Incrementa USD, decrementa BTC
   - Limpia trailing_stop
   - Registra en CSV con P/L

### Trailing Stop Logic
```python
new_trailing = max(old_trailing, current_price * 0.99)
```
- Solo sube cuando precio sube
- Nunca baja (asegura ganancias)
- Vende automáticamente si se toca

---

## 📈 Indicadores Técnicos

| Indicador | Periodo | Uso |
|-----------|---------|-----|
| EMA20 | 20 velas | Tendencia corta |
| EMA50 | 50 velas | Tendencia media |
| RSI14 | 14 velas | Sobreventa/Sobrecompra |
| MACD | 12/26/9 | Momentum |
| Bollinger | 20/2 | Volatilidad |

**Condiciones BUY:**
- EMA20 > EMA50
- RSI 45-60 (no extremo)
- OpenAI: BUY
- USD >= $65
- Sin posición BTC abierta

**Condiciones SELL:**
- Trailing Stop hit, O
- OpenAI: SELL + EMA20 < EMA50 + RSI < 40

---

## 🧪 Test Suite

**Papers Trading Tests (15 tests, todos ✅)**
```
✅ test_paper_engine_initialization
✅ test_paper_engine_buy
✅ test_paper_engine_buy_insufficient_balance
✅ test_paper_engine_sell
✅ test_paper_engine_sell_no_position
✅ test_paper_engine_trailing_stop
✅ test_paper_engine_trailing_stop_triggers_sell
✅ test_paper_engine_reset_wallet
✅ test_paper_engine_wallet_persistence
✅ test_paper_engine_trade_logging
✅ test_factory_pattern_paper_mode
✅ test_get_open_position_none
✅ test_get_open_position_after_buy
✅ test_close_position
✅ test_load_balances
```

Ejecutar:
```bash
cd backend
python -m pytest tests/test_paper_trading.py -v
# Result: ===================== 15 passed in 0.78s =====================
```

---

## 🚀 API Endpoints Activos

### Bot Control
```bash
# Obtener dashboard unificado
GET /api/v1/bot/dashboard

# Iniciar/parar bot
POST /api/v1/bot/start
POST /api/v1/bot/stop

# Ejecutar ciclo manual
POST /api/v1/bot/cycle

# Análisis de mercado
GET /api/v1/bot/analysis
```

### Paper Trading
```bash
# Wallet
GET /api/v1/paper/wallet
POST /api/v1/paper/reset?initial_usd=1000

# Trades
GET /api/v1/paper/trades?limit=20
POST /api/v1/paper/simulate-buy
POST /api/v1/paper/simulate-sell

# Estadísticas
GET /api/v1/paper/stats
```

### Indicadores
```bash
GET /api/v1/indicators/ema
GET /api/v1/indicators/rsi
GET /api/v1/indicators/macd
GET /api/v1/indicators/bollinger
GET /api/v1/indicators/analyze
```

---

## 🎮 Modo de Uso

### 1. Desarrollo (PAPER mode - default)
```python
# backend/app/services/trading_mode.py
MODE = "PAPER"  # ← Seguro, sin dinero real
```

```bash
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

**Dashboard disponible en:** http://localhost:8001

### 2. Testing de Estrategia
```bash
# Probar ciclo manual
curl -X POST http://localhost:8001/api/v1/bot/cycle

# Ver wallet actual
curl http://localhost:8001/api/v1/paper/wallet

# Ver historial de trades
curl http://localhost:8001/api/v1/paper/trades

# Reset si quieres empezar de nuevo
curl -X POST http://localhost:8001/api/v1/paper/reset
```

### 3. Cuando esté listo → REAL
```python
# backend/app/services/trading_mode.py
MODE = "REAL"  # ⚠️ Trading en vivo con Kraken
```

⚠️ **SOLO después de:**
- 10+ trades exitosos en paper
- P/L consistentemente positivo
- Validar alerts y indicadores

---

## 📦 Dependencias Instaladas

```
fastapi==0.104.1
uvicorn==0.24.0
sqlalchemy==2.0.23
pydantic==2.5.0
krakenex==2.2.1          # Kraken API
openai==1.3.5            # GPT-3.5 validation
pandas==2.1.3            # Indicators
ta==0.11.0               # Technical analysis
apscheduler==3.10.4      # Task scheduler
pytest==7.4.3            # Testing
numpy==1.26.2            # Numeric
```

---

## 📁 Estructura Final

```
botija/
├── backend/
│   ├── app/
│   │   ├── main.py                      # FastAPI entry point
│   │   ├── scheduler.py                 # APScheduler init
│   │   ├── models.py                    # SQLAlchemy ORM
│   │   ├── schemas.py                   # Pydantic models
│   │   ├── database.py                  # DB setup
│   │   ├── config.py                    # Configuration
│   │   ├── services/
│   │   │   ├── kraken_client.py         # Kraken wrapper
│   │   │   ├── technical_indicators.py  # EMA, RSI, MACD, etc
│   │   │   ├── ai_validator.py          # OpenAI signal
│   │   │   ├── telegram_alerts.py       # Telegram bot
│   │   │   ├── trailing_stop.py         # Stop logic
│   │   │   ├── trading_bot.py           # Orchestrator
│   │   │   ├── trading_mode.py          # MODE selector
│   │   │   └── modes/
│   │   │       ├── base.py              # Abstract interface
│   │   │       ├── paper.py             # Simulation
│   │   │       ├── real.py              # Kraken live
│   │   │       └── factory.py           # Engine selection
│   │   ├── routers/
│   │   │   ├── bot.py                   # Bot control + dashboard
│   │   │   ├── paper.py                 # Paper trading API
│   │   │   ├── trades.py                # Trade history
│   │   │   └── indicators.py            # Technical analysis
│   │   └── __init__.py
│   ├── data/
│   │   ├── paper_wallet.json            # Wallet state
│   │   └── paper_trades.csv             # Trade log
│   ├── tests/
│   │   ├── test_paper_trading.py        # 15 tests ✅
│   │   ├── test_main.py
│   │   └── __init__.py
│   ├── requirements.txt
│   └── __init__.py
├── frontend/
│   └── index.html                       # Dashboard
├── docs/
│   ├── PAPER_TRADING_GUIDE.md           # Guía completa de paper trading
│   ├── PROJECT_STATUS.md                # Este archivo
│   └── README_PAPERTRADER.md
├── .env.example
├── README.md
└── manifest.json
```

---

## 🔄 Trading Loop (Automático cada 1 hora)

```
1. Fetch Kraken OHLC data para XBTUSDT
   ↓
2. Calcular indicadores (EMA20, EMA50, RSI14, MACD)
   ↓
3. Obtener AI signal from OpenAI GPT-3.5
   ↓
4. Si BUY signal:
   ├─ Validar balances y condiciones
   ├─ Ejecutar buy en paper wallet (o Kraken si REAL)
   ├─ Inicializar trailing stop
   ├─ Registrar en CSV
   └─ Enviar alerta Telegram (si configurado)
   ↓
5. Si posición abierta:
   ├─ Actualizar trailing stop
   └─ Si hit: ejecutar venta automática
   ↓
6. Si SELL signal:
   ├─ Validar condiciones
   ├─ Ejecutar venta
   ├─ Registrar P/L en CSV
   └─ Enviar alerta Telegram con ganancias/pérdidas
   ↓
7. Guardar estado → Siguiente ciclo en 1 hora
```

---

## ✨ Características Destacadas

### 🔒 Seguridad
- **Spot trading only** (sin leverage, sin futures)
- **Paper mode** por defecto (cero riesgo)
- **Trailing stop** automático para lock-in ganancias
- **Balance validations** antes de cada trade

### 🤖 Automatización
- **Scheduler APScheduler** para ciclos automáticos
- **Telegram alerts** para cada evento
- **Dashboard real-time** con polling cada 30s
- **CSV trade log** persistente e inmutable

### 🧪 Testing
- **15 unit tests** para paper trading
- **Factory pattern** para engine switching sin código duplicado
- **Isolated environments** (paper vs real)
- **Comprehensive validation**

### 📊 Observabilidad
- **Trade history** con P/L tracking
- **Wallet persistence** entre sesiones
- **Indicator visualization** en dashboard
- **Confidence scoring** de signals AI

---

## 🚀 Quick Start

```bash
# Clone and setup
git clone <repo>
cd botija/backend

# Install deps (en devcontainer está automático)
pip install -r requirements.txt

# Start API
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001

# En otra terminal - ver logs
tail -f logs/bot.log

# Dashboard
open http://localhost:8001
```

## 🎓 Next Steps

1. ✅ **Paper Trading**: Ya funcionando en modo simulación
2. ✅ **Dashboard**: Integrado y en tiempo real
3. ⏳ **VPS Deployment**: Scripts en `/scripts/deploy.sh`
4. ⏳ **Real Kraken Credentials**: Configurar `.env` con API keys
5. ⏳ **Switch to REAL**: Cambiar `MODE = "REAL"` después de validar

---

## 📞 Support & Debugging

```bash
# Ver todos los tests
cd backend && python -m pytest tests/ -v

# Test específico
python -m pytest tests/test_paper_trading.py::test_paper_engine_buy -v

# Ver logs en vivo
python -m uvicorn app.main:app --log-level debug

# Reset wallet
curl -X POST http://localhost:8001/api/v1/paper/reset?initial_usd=5000

# Ver wallet actual
curl http://localhost:8001/api/v1/paper/wallet | python -m json.tool

# Ver trades log
curl http://localhost:8001/api/v1/paper/trades | python -m json.tool
```

---

**Proyecto completado con ✅ todas las fases implementadas.**

**Status**: 🟢 Ready for paper trading testing  
**Mode**: 🔒 PAPER (safe default)  
**Tests**: ✅ 15/15 passing  
**API**: 📡 6 paper endpoints + 8 core endpoints  
**Dashboard**: 🎨 Real-time wallet updates  
**Next**: Switch to REAL mode after validation
