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

        # Si no hay status, usar último ciclo como fallback
        if not status:
            last_cycle = db.query(models.TradingCycle).order_by(
                models.TradingCycle.timestamp.desc()
            ).first()

            if last_cycle:
                return schemas.DashboardResponse(
                    mode=last_cycle.trading_mode,
                    instrument=last_cycle.instrument,
                    balance=last_cycle.balance,
                    nav=last_cycle.balance,
                    position_units=last_cycle.position_units,
                    unrealized_pl=0.0,
                    is_running=False,
                    last_price=last_cycle.price,
                    spread_pips=last_cycle.spread_pips,
                    status="from_cycle"
                )

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


@router.get("/position")
async def get_active_position():
    """Get active position details from OANDA"""
    try:
        bot = get_trading_bot()
        if not bot or not bot.oanda:
            return {"has_position": False, "position": None}

        instrument = Config.DEFAULT_INSTRUMENT
        position = bot.oanda.get_position(instrument)

        if not position:
            return {"has_position": False, "position": None}

        long_units = int(position.get("long", {}).get("units", 0))
        short_units = int(position.get("short", {}).get("units", 0))
        total_units = long_units + short_units

        if total_units == 0:
            return {"has_position": False, "position": None}

        # Get current price for P/L calculation
        pricing = bot.oanda.get_spread(instrument)
        current_price = pricing.get("mid", 0) if pricing else 0

        # Determine side and get details
        if long_units > 0:
            side = "LONG"
            units = long_units
            avg_price = float(position.get("long", {}).get("averagePrice", 0))
            unrealized_pl = float(position.get("long", {}).get("unrealizedPL", 0))
        else:
            side = "SHORT"
            units = abs(short_units)
            avg_price = float(position.get("short", {}).get("averagePrice", 0))
            unrealized_pl = float(position.get("short", {}).get("unrealizedPL", 0))

        # Calculate P/L in pips
        if avg_price > 0 and current_price > 0:
            pip_multiplier = 10000 if "JPY" not in instrument else 100
            if side == "LONG":
                pl_pips = (current_price - avg_price) * pip_multiplier
            else:
                pl_pips = (avg_price - current_price) * pip_multiplier
        else:
            pl_pips = 0

        return {
            "has_position": True,
            "position": {
                "instrument": instrument,
                "side": side,
                "units": units,
                "entry_price": avg_price,
                "current_price": current_price,
                "unrealized_pl": unrealized_pl,
                "pl_pips": round(pl_pips, 1)
            }
        }
    except Exception as e:
        logger.error(f"Error getting position: {e}")
        return {"has_position": False, "position": None, "error": str(e)}


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


@router.get("/logs/download")
async def download_logs():
    """Download logs as a file"""
    from fastapi.responses import PlainTextResponse
    handler = get_log_handler()
    logs = handler.get_logs(limit=1000)

    # Format logs as text
    log_text = "\n".join([
        f"{log.get('timestamp', '')} [{log.get('level', '')}] {log.get('message', '')}"
        for log in logs
    ])

    return PlainTextResponse(
        content=log_text,
        media_type="text/plain",
        headers={"Content-Disposition": "attachment; filename=botija-forex.log"}
    )
