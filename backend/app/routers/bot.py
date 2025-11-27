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
        # Get live data from OANDA
        bot = get_trading_bot()
        live_balance = 0.0
        live_nav = 0.0
        live_unrealized_pl = 0.0

        if bot and bot.oanda:
            live_balance = bot.oanda.get_balance()
            live_nav = bot.oanda.get_nav()
            live_unrealized_pl = live_nav - live_balance  # NAV - Balance = Unrealized P/L

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
                    balance=live_balance or last_cycle.balance,
                    nav=live_nav or last_cycle.balance,
                    position_units=last_cycle.position_units,
                    unrealized_pl=live_unrealized_pl,
                    is_running=False,
                    last_price=last_cycle.price,
                    spread_pips=last_cycle.spread_pips,
                    status="from_cycle"
                )

            return schemas.DashboardResponse(
                mode=Config.TRADING_MODE,
                instrument=Config.DEFAULT_INSTRUMENT,
                balance=live_balance,
                nav=live_nav,
                position_units=0,
                unrealized_pl=live_unrealized_pl,
                is_running=False,
                status="not_initialized"
            )

        return schemas.DashboardResponse(
            mode=status.trading_mode,
            instrument=status.instrument,
            balance=live_balance or status.balance,
            nav=live_nav or status.nav,
            position_units=status.position_units,
            unrealized_pl=live_unrealized_pl or status.unrealized_pl,
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


@router.get("/positions")
async def get_active_positions():
    """Get all active positions/trades from OANDA with detailed info"""
    from datetime import datetime, timezone

    try:
        bot = get_trading_bot()
        if not bot or not bot.oanda:
            return {"positions": [], "count": 0}

        # Use open trades for more detailed info (includes openTime, tradeId, etc.)
        open_trades = bot.oanda.get_open_trades()
        if not open_trades:
            return {"positions": [], "count": 0}

        positions_list = []
        now = datetime.now(timezone.utc)

        for trade in open_trades:
            instrument = trade.get("instrument", "")
            units = int(trade.get("currentUnits", 0))
            trade_id = trade.get("id", "")
            open_time_str = trade.get("openTime", "")
            entry_price = float(trade.get("price", 0))
            unrealized_pl = float(trade.get("unrealizedPL", 0))

            # Determine side
            side = "LONG" if units > 0 else "SHORT"
            units = abs(units)

            # Get current price
            pricing = bot.oanda.get_spread(instrument)
            current_price = pricing.get("mid", 0) if pricing else 0
            spread_pips = pricing.get("spread_pips", 0) if pricing else 0

            # Calculate P/L in pips
            pip_multiplier = 10000 if "JPY" not in instrument else 100
            if side == "LONG":
                pl_pips = (current_price - entry_price) * pip_multiplier if entry_price > 0 else 0
            else:
                pl_pips = (entry_price - current_price) * pip_multiplier if entry_price > 0 else 0

            # Parse open time and calculate duration
            open_time = None
            duration_str = "N/A"
            duration_seconds = 0
            if open_time_str:
                try:
                    # OANDA format: 2025-11-27T01:23:45.123456789Z
                    open_time = datetime.fromisoformat(open_time_str.replace('Z', '+00:00'))
                    delta = now - open_time
                    duration_seconds = int(delta.total_seconds())

                    days = delta.days
                    hours, remainder = divmod(delta.seconds, 3600)
                    minutes, _ = divmod(remainder, 60)

                    if days > 0:
                        duration_str = f"{days}d {hours}h {minutes}m"
                    elif hours > 0:
                        duration_str = f"{hours}h {minutes}m"
                    else:
                        duration_str = f"{minutes}m"
                except Exception:
                    pass

            # Get stop loss and take profit if set
            stop_loss = trade.get("stopLossOrder", {}).get("price")
            take_profit = trade.get("takeProfitOrder", {}).get("price")
            trailing_stop = trade.get("trailingStopLossOrder", {}).get("distance")

            # Calculate margin used (approximate)
            margin_used = float(trade.get("marginUsed", 0))

            # Calculate initial value
            initial_value = entry_price * units

            positions_list.append({
                "trade_id": trade_id,
                "instrument": instrument,
                "side": side,
                "units": units,
                "entry_price": entry_price,
                "current_price": current_price,
                "unrealized_pl": unrealized_pl,
                "pl_pips": round(pl_pips, 1),
                "open_time": open_time_str,
                "duration": duration_str,
                "duration_seconds": duration_seconds,
                "stop_loss": float(stop_loss) if stop_loss else None,
                "take_profit": float(take_profit) if take_profit else None,
                "trailing_stop_pips": float(trailing_stop) * pip_multiplier if trailing_stop else None,
                "margin_used": margin_used,
                "spread_pips": round(spread_pips, 1),
                "initial_value": round(initial_value, 2)
            })

        # Sort by open time (newest first)
        positions_list.sort(key=lambda x: x.get("open_time", ""), reverse=True)

        return {"positions": positions_list, "count": len(positions_list)}
    except Exception as e:
        logger.error(f"Error getting positions: {e}")
        return {"positions": [], "count": 0, "error": str(e)}


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
