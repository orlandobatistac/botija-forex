# API_DOCS.md

## Documentación de API - Kraken AI Trading Bot

### Base URL
```
http://localhost:8001/api/v1
```

### 🏥 Health & Status

#### Get API Status
```
GET /status
```

Response:
```json
{
  "api_version": "1.0.0",
  "status": "active"
}
```

#### Get Bot Status
```
GET /bot/status
```

Response:
```json
{
  "id": 1,
  "is_running": true,
  "btc_balance": 0.5,
  "usd_balance": 1000.00,
  "last_check": "2025-11-14T10:30:00",
  "last_trade_id": "12345",
  "error_count": 0,
  "updated_at": "2025-11-14T10:30:00"
}
```

### 💰 Trades

#### Get All Trades
```
GET /trades/?skip=0&limit=10
```

Response:
```json
[
  {
    "id": 1,
    "trade_id": "TR001",
    "order_type": "BUY",
    "symbol": "BTCUSD",
    "entry_price": 45000.00,
    "exit_price": null,
    "quantity": 0.01,
    "profit_loss": null,
    "status": "OPEN",
    "trailing_stop": 44550.00,
    "created_at": "2025-11-14T10:00:00",
    "closed_at": null
  }
]
```

#### Get Single Trade
```
GET /trades/{trade_id}
```

#### Create Trade
```
POST /trades/
Content-Type: application/json

{
  "order_type": "BUY",
  "symbol": "BTCUSD",
  "entry_price": 45000.00,
  "quantity": 0.01,
  "status": "OPEN"
}
```

### 🤖 Bot Control

#### Start Bot
```
POST /bot/start
```

Response:
```json
{
  "message": "Bot started",
  "status": "running"
}
```

#### Stop Bot
```
POST /bot/stop
```

Response:
```json
{
  "message": "Bot stopped",
  "status": "stopped"
}
```

#### Get Recent Signals
```
GET /bot/signals?limit=10
```

Response:
```json
[
  {
    "id": 1,
    "timestamp": "2025-11-14T10:15:00",
    "ema20": 45100.00,
    "ema50": 45500.00,
    "rsi14": 52.5,
    "ai_signal": "BUY",
    "confidence": 0.85,
    "action_taken": "LIMIT_ORDER_PLACED"
  }
]
```

### 📊 Status Codes

| Code | Meaning |
|------|---------|
| 200 | OK - Request successful |
| 201 | Created - Resource created |
| 400 | Bad Request - Invalid input |
| 401 | Unauthorized - Authentication required |
| 404 | Not Found - Resource doesn't exist |
| 500 | Server Error - Internal error |

### 🔐 Authentication

Currently no authentication required for development.

For production, add JWT Bearer token:
```
Authorization: Bearer YOUR_TOKEN
```

### 📚 OpenAPI Documentation

Disponible automáticamente en:
- Swagger UI: `/docs`
- ReDoc: `/redoc`

### 🧪 Test Requests

```bash
# Check health
curl http://localhost:8001/health

# Get API status
curl http://localhost:8001/api/v1/status

# Get bot status
curl http://localhost:8001/api/v1/bot/status

# Create a trade
curl -X POST http://localhost:8001/api/v1/trades/ \
  -H "Content-Type: application/json" \
  -d '{
    "order_type": "BUY",
    "symbol": "BTCUSD",
    "entry_price": 45000,
    "quantity": 0.01,
    "status": "OPEN"
  }'

# Get recent signals
curl http://localhost:8001/api/v1/bot/signals
```

---

Para API interactiva, visita: http://localhost:8001/docs
