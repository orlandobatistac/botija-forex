"""
Botija Forex - FastAPI Application
AI-Powered Forex Trading Bot with OANDA Integration
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
import logging

from .database import init_db
from .config import Config
from .services.log_handler import setup_log_handler
from .scheduler import init_scheduler, shutdown_scheduler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    init_db()
    setup_log_handler()
    init_scheduler()
    logger.info("🚀 Botija Forex started")
    yield
    # Shutdown
    shutdown_scheduler()
    logger.info("🛑 Botija Forex stopped")


# Create FastAPI app
app = FastAPI(
    title="Botija Forex",
    description="AI-Powered Forex Trading Bot with OANDA Integration",
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
frontend_static = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "frontend",
    "static"
)
if os.path.exists(frontend_static):
    app.mount("/static", StaticFiles(directory=frontend_static), name="static")

# Import and include routers
from .routers import bot, trades, cycles, market

app.include_router(bot.router)
app.include_router(trades.router)
app.include_router(cycles.router)
app.include_router(market.router)


@app.get("/")
async def root():
    """Serve the frontend HTML"""
    from fastapi.responses import FileResponse

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
    return {"message": "Botija Forex API", "status": "running", "docs": "/docs"}


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "Botija Forex"}


@app.get("/api/v1/status")
async def api_status():
    """API status endpoint"""
    return {
        "status": "active",
        "mode": Config.TRADING_MODE,
        "instrument": Config.DEFAULT_INSTRUMENT,
        "version": "1.0.0"
    }
