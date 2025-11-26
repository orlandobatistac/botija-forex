"""
Kraken AI Trading Bot - FastAPI Application
Generated from AI Agent Master Template
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os
import logging
from contextlib import asynccontextmanager

# Import scheduler
from .scheduler import init_scheduler, shutdown_scheduler
from .services.log_handler import setup_log_handler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Lifespan events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    from .database import engine, Base
    Base.metadata.create_all(bind=engine)  # Create tables
    setup_log_handler()  # Setup in-memory log handler
    init_scheduler()
    logger.info("🚀 Kraken AI Trading Bot iniciado")
    yield
    # Shutdown
    shutdown_scheduler()
    logger.info("🛑 Kraken AI Trading Bot detenido")

# Create FastAPI app
app = FastAPI(
    title="Kraken AI Trading Bot",
    description="Automated swing trading bot for Bitcoin using Kraken Spot API with AI validation",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
frontend_static = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend", "static")
if os.path.exists(frontend_static):
    app.mount("/static", StaticFiles(directory=frontend_static), name="static")
else:
    logger.warning(f"Static files directory not found at {frontend_static}")

# Import routers
from app.routers import bot, trades, indicators, paper, cycles

# Include routers
app.include_router(bot.router)
app.include_router(trades.router)
app.include_router(indicators.router)
app.include_router(paper.router)
app.include_router(cycles.router)

@app.get("/")
async def root():
    """Serve the frontend HTML"""
    from fastapi.responses import FileResponse
    import os
    
    frontend_index = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
        "frontend", 
        "index.html"
    )
    
    if os.path.exists(frontend_index):
        return FileResponse(
            frontend_index,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    else:
        return {"message": "Kraken AI Trading Bot API is running", "frontend": "not found"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "Kraken AI Trading Bot"}

# API routes
@app.get("/api/v1/status")
async def api_status():
    return {"api_version": "1.0.0", "status": "active"}

@app.get("/api/v1/bot/status")
async def bot_status():
    """Get current bot trading status - legacy endpoint, use /api/v1/bot/status instead"""
    from app.database import SessionLocal
    from app.models import BotStatus
    
    db = SessionLocal()
    try:
        status = db.query(BotStatus).order_by(BotStatus.id.desc()).first()
        if status:
            return {
                "is_running": status.is_running,
                "trading_mode": status.trading_mode,
                "btc_balance": status.btc_balance,
                "usd_balance": status.usd_balance,
                "last_buy_price": status.last_buy_price,
                "trailing_stop_price": status.trailing_stop_price
            }
        return {
            "is_running": True,
            "trading_mode": "PAPER",
            "btc_balance": 0.0,
            "usd_balance": 0.0,
            "last_buy_price": None,
            "trailing_stop_price": None
        }
    finally:
        db.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
