"""
Bot router - Main bot control and status endpoints
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import logging

from ..database import get_db
from .. import models, schemas
from ..config import Config
from ..services.log_handler import get_log_handler
from ..scheduler import get_scheduler_status, trigger_manual_cycle_async, get_trading_bot

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/bot",
    tags=["bot"]
)


@router.get("/status")
async def get_bot_status(db: Session = Depends(get_db)):
    """Get current bot status"""
    try:
        status = db.query(models.BotStatus).order_by(models.BotStatus.id.desc()).first()
        if not status:
            return {
                "is_running": False,
                "mode": Config.TRADING_MODE,
                "instrument": Config.DEFAULT_INSTRUMENT,
                "balance": 0.0,
                "position_units": 0,
                "status": "not_initialized"
            }
        return status
    except Exception as e:
        logger.error(f"Error getting bot status: {e}")
        return {"error": str(e), "status": "error"}


@router.get("/dashboard", response_model=schemas.DashboardResponse)
async def get_dashboard(db: Session = Depends(get_db)):
    """Get dashboard data"""
    try:
        status = db.query(models.BotStatus).order_by(models.BotStatus.id.desc()).first()

        if not status:
            return schemas.DashboardResponse(
                mode=Config.TRADING_MODE,
                instrument=Config.DEFAULT_INSTRUMENT,
                balance=0.0,
                nav=0.0,
                position_units=0,
                unrealized_pl=0.0,
                is_running=False,
                status="not_initialized"
            )

        return schemas.DashboardResponse(
            mode=status.trading_mode,
            instrument=status.instrument,
            balance=status.balance,
            nav=status.nav,
            position_units=status.position_units,
            unrealized_pl=status.unrealized_pl,
            is_running=status.is_running,
            status="ready"
        )
    except Exception as e:
        logger.error(f"Error getting dashboard: {e}")
        return schemas.DashboardResponse(
            mode=Config.TRADING_MODE,
            instrument=Config.DEFAULT_INSTRUMENT,
            balance=0.0,
            nav=0.0,
            position_units=0,
            unrealized_pl=0.0,
            is_running=False,
            status="error"
        )


@router.post("/start")
async def start_bot():
    """Start the trading bot"""
    try:
        bot = get_trading_bot()
        await bot.start()
        return {"message": "Bot started", "status": "running"}
    except Exception as e:
        return {"message": str(e), "status": "error"}


@router.post("/stop")
async def stop_bot():
    """Stop the trading bot"""
    try:
        bot = get_trading_bot()
        await bot.stop()
        return {"message": "Bot stopped", "status": "stopped"}
    except Exception as e:
        return {"message": str(e), "status": "error"}


@router.post("/cycle")
async def run_cycle():
    """Execute one trading cycle manually"""
    try:
        result = await trigger_manual_cycle_async()
        return {"message": "Cycle executed", "result": result}
    except Exception as e:
        return {"error": str(e), "trigger": "manual"}


@router.get("/scheduler")
async def get_scheduler():
    """Get scheduler status"""
    return get_scheduler_status()


@router.get("/logs")
async def get_logs(limit: int = 100, level: str = None):
    """Get recent bot logs"""
    handler = get_log_handler()
    logs = handler.get_logs(limit=limit, level=level)
    return {"logs": logs, "count": len(logs)}
