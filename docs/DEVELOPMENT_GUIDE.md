# DEVELOPMENT_GUIDE.md

## Guía de Desarrollo - Kraken AI Trading Bot

### 🚀 Quick Start

1. **Abrir en Codespaces/DevContainer**
   ```bash
   # El devcontainer instala automáticamente las dependencias
   ```

2. **Ejecutar la aplicación localmente**
   ```bash
   cd backend
   python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
   ```

3. **Acceder a la aplicación**
   - Frontend: http://localhost:8001/
   - API Docs: http://localhost:8001/docs
   - Health Check: http://localhost:8001/health

### 📁 Estructura del Código

```
backend/
├── app/
│   ├── main.py           # FastAPI app principal
│   ├── database.py       # Configuración de BD
│   ├── models.py         # SQLAlchemy ORM models
│   ├── schemas.py        # Pydantic schemas
│   └── routers/
│       ├── trades.py     # Rutas de trades
│       └── bot.py        # Rutas del bot
├── tests/
│   └── test_main.py      # Tests unitarios
└── requirements.txt      # Dependencias

frontend/
├── index.html            # Página principal
├── components/           # Componentes Alpine.js
├── stores/               # Estado global
├── utils/                # Funciones auxiliares
└── static/               # CSS, JS estáticos
```

### 🔧 Desarrollo

#### Backend (FastAPI)

```python
# Crear nueva ruta
@app.get("/api/v1/new-endpoint")
async def new_endpoint():
    return {"message": "Hello"}

# Usar database
from .database import get_db
@app.get("/items")
async def get_items(db: Session = Depends(get_db)):
    items = db.query(models.Item).all()
    return items
```

#### Frontend (Alpine.js)

```html
<div x-data="myComponent()">
    <button @click="action()">Click</button>
    <div x-text="message"></div>
</div>

<script>
function myComponent() {
    return {
        message: 'Hello',
        action() {
            this.message = 'Clicked!';
        }
    }
}
</script>
```

### 📝 Modelo de Datos

#### Trade
```python
- id: int (primary key)
- trade_id: str (unique)
- order_type: str (BUY/SELL)
- entry_price: float
- exit_price: float (nullable)
- quantity: float
- profit_loss: float (nullable)
- status: str (OPEN/CLOSED)
- trailing_stop: float
- created_at: datetime
```

#### BotStatus
```python
- id: int
- is_running: bool
- btc_balance: float
- usd_balance: float
- error_count: int
- updated_at: datetime
```

### 🧪 Testing

```bash
# Run all tests
cd backend && python -m pytest

# Run specific test
cd backend && python -m pytest tests/test_main.py::test_root

# With coverage
cd backend && python -m pytest --cov=app
```

### 📚 API Documentation

FastAPI genera documentación automática:
- Swagger UI: http://localhost:8001/docs
- ReDoc: http://localhost:8001/redoc

### 🔐 Seguridad

- No commitear .env con credenciales reales
- Usar .env.example como template
- Validar inputs en Pydantic schemas
- Rate limiting en endpoints críticos

### 📊 Logging

```python
import logging

logger = logging.getLogger(__name__)
logger.info("Message")
logger.error("Error occurred")
```

---

Más información en `/workspaces/botija/docs/`
