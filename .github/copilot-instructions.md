# GitHub Copilot Instructions - Kraken AI Trading Bot

## Project Context
- **Name**: Kraken AI Trading Bot
- **Technologies**: FastAPI + Alpine.js + TailwindCSS + Kraken API + OpenAI
- **Architecture**: Trading Bot with Web Monitoring Dashboard
- **Database**: SQLite (dev) / PostgreSQL (prod)
- **Deployment**: VPS with Nginx
- **Core Purpose**: Automated BTC swing trading with AI validation

## Communication Style
- **Language**: **RESPONDE EN ESPAÑOL** siempre con el desarrollador
- **Response Length**: **RESPUESTAS CORTAS Y DIRECTAS** - este es crítico
  - Default: Respuestas breves (1-3 oraciones máximo)
  - Solo detalles cuando se pide ("dame más detalles", "explícame mejor")
- **Code**: Inglés para nombres, funciones, clases y comentarios
- **Documentation**: Español para docs de usuario, Inglés para docs técnicas
- **Commit messages**: Inglés

## Code Style
- **Python**: Type hints, docstrings, PEP8
- **JavaScript**: ES6+, funcional cuando sea posible
- **FastAPI**: RESTful, Pydantic schemas, status codes apropiados
- **Frontend**: Alpine.js components, sin build process

## Trading Bot Patterns
1. **API Integration**: Kraken krakenex library
2. **Indicators**: pandas, ta (EMA20, EMA50, RSI14)
3. **AI Signals**: OpenAI API
4. **Telegram Alerts**: Bot notifications
5. **Trailing Stop**: Dynamic price protection
6. **Order Management**: OCO orders, market sells

## Development Workflow
- Local dev en devcontainer
- Feature branch → PR → merge → auto-deploy
- CI/CD con GitHub Actions
- Tests: pytest para backend
- Deploy: SSH automated to VPS

## Useful Commands
```bash
# Start API
cd backend && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001

# Run tests
cd backend && python -m pytest

# Check bot status
curl http://localhost:8001/api/v1/bot/status

# Access dashboard
http://localhost:8001 (frontend)
```

## Key Files
- `backend/app/main.py` - FastAPI app
- `backend/app/models.py` - SQLAlchemy models
- `frontend/index.html` - Main dashboard
- `.env.example` - Configuration template
- `manifest.json` - Project metadata

## Developer Preferences
- **NO documentation files**: Respuestas resumidas EN CHAT SOLAMENTE
- No crear guías, tutoriales, ni markdown files de documentation
- Mantener el proyecto limpio (solo código funcional)
- Prefers SHORT responses
- Values working solutions first
- Likes clean, maintainable code
- Focuses on practical results
