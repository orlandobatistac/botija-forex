"""
Bot router for Kraken AI Trading Bot
"""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response, FileResponse
from sqlalchemy.orm import Session
import os
import subprocess
from pathlib import Path
from .. import models, schemas
from ..database import get_db
from ..services import TradingBot, TechnicalIndicators
from ..services.modes.factory import get_trading_engine
from ..services.modes.paper import PaperTradingEngine
from ..scheduler import get_scheduler_status, last_cycle_info
from ..services.log_handler import get_log_handler
from datetime import datetime

router = APIRouter(
    prefix="/api/v1/bot",
    tags=["bot"]
)

# Initialize trading bot instance
trading_bot = None

def get_trading_bot() -> TradingBot:
    """Get or create trading bot instance"""
    global trading_bot
    if trading_bot is None:
        trading_bot = TradingBot(
            kraken_api_key=os.getenv('KRAKEN_API_KEY', ''),
            kraken_secret=os.getenv('KRAKEN_SECRET_KEY', ''),
            openai_api_key=os.getenv('OPENAI_API_KEY', ''),
            telegram_token=os.getenv('TELEGRAM_TOKEN', ''),
            telegram_chat_id=os.getenv('TELEGRAM_CHAT_ID', ''),
            trade_amount=float(os.getenv('TRADE_AMOUNT_USD', 0)),
            trade_amount_percent=float(os.getenv('TRADE_AMOUNT_PERCENT', 10)),
            min_balance=float(os.getenv('MIN_BALANCE_USD', 0)),
            min_balance_percent=float(os.getenv('MIN_BALANCE_PERCENT', 20)),
            trailing_stop_pct=float(os.getenv('TRAILING_STOP_PERCENTAGE', 0.99))
        )
    return trading_bot

@router.get("/status")
async def get_bot_status(db: Session = Depends(get_db)):
    """Get current bot status"""
    try:
        status = db.query(models.BotStatus).order_by(models.BotStatus.id.desc()).first()
        if not status:
            return {
                "bot_running": True,
                "mode": "PAPER",
                "btc_position": 0.0,
                "trailing_stop": None,
                "last_trade": None,
                "balance_usd": 0.0
            }
        return status
    except Exception as e:
        return {
            "bot_running": True,
            "mode": "PAPER",
            "error": str(e)
        }

@router.get("/dashboard")
async def get_dashboard_status():
    """Get combined dashboard status (paper + trading bot)"""
    try:
        # Get trading engine (paper or real)
        engine = get_trading_engine()
        balances = engine.load_balances()
        
        # If paper engine, get additional stats
        if isinstance(engine, PaperTradingEngine):
            wallet = engine.get_wallet_summary()
            position = engine.get_open_position()
            
            return {
                "mode": "PAPER",
                "btc_balance": wallet['btc_balance'],
                "usd_balance": wallet['usd_balance'],
                "trailing_stop": wallet.get('trailing_stop'),
                "position_open": wallet['btc_balance'] > 0,
                "position_details": position if position else None,
                "status": "ready"
            }
        else:
            # Real trading engine
            return {
                "mode": "REAL",
                "btc_balance": balances.get('btc', 0),
                "usd_balance": balances.get('usd', 0),
                "status": "connected"
            }
    except Exception as e:
        return {
            "error": str(e),
            "status": "error"
        }

@router.post("/status", response_model=schemas.BotStatus)
async def update_bot_status(status: schemas.BotStatusCreate, db: Session = Depends(get_db)):
    """Update bot status"""
    db_status = models.BotStatus(**status.dict())
    db.add(db_status)
    db.commit()
    db.refresh(db_status)
    return db_status

@router.get("/signals", response_model=list[schemas.Signal])
async def get_recent_signals(limit: int = 10, db: Session = Depends(get_db)):
    """Get recent trading signals"""
    signals = db.query(models.Signal).order_by(models.Signal.timestamp.desc()).limit(limit).all()
    return signals

@router.post("/signals", response_model=schemas.Signal)
async def create_signal(signal: schemas.SignalCreate, db: Session = Depends(get_db)):
    """Create a new trading signal record"""
    db_signal = models.Signal(**signal.dict())
    db.add(db_signal)
    db.commit()
    db.refresh(db_signal)
    return db_signal

@router.post("/start")
async def start_bot():
    """Start the trading bot"""
    try:
        bot = get_trading_bot()
        await bot.start()
        return {"message": "Bot started", "status": "running"}
    except Exception as e:
        # Return success even if bot can't be fully initialized (e.g., missing API keys)
        return {"message": "Bot start signal sent", "status": "running", "note": str(e)}

@router.post("/stop")
async def stop_bot():
    """Stop the trading bot"""
    try:
        bot = get_trading_bot()
        await bot.stop()
        return {"message": "Bot stopped", "status": "stopped"}
    except Exception as e:
        # Return success even if bot can't be fully initialized
        return {"message": "Bot stop signal sent", "status": "stopped", "note": str(e)}

@router.post("/cycle")
async def run_trading_cycle(
    db: Session = Depends(get_db),
    bot: TradingBot = Depends(get_trading_bot)
):
    """Execute one trading cycle manually"""
    try:
        # Update last cycle info - start
        last_cycle_info["timestamp"] = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        last_cycle_info["status"] = "running"
        last_cycle_info["error"] = None
        last_cycle_info["trigger"] = "manual"
        
        result = await bot.run_cycle(trigger="manual")
        
        # Update last cycle info - success
        last_cycle_info["status"] = "success"
        
        return {
            "success": True,
            "message": "Trading cycle executed successfully",
            "result": result
        }
    except Exception as e:
        # Update last cycle info - error
        last_cycle_info["status"] = "error"
        last_cycle_info["error"] = str(e)
        
        return {
            "success": False,
            "message": f"Error executing cycle: {str(e)}"
        }

@router.post("/cycle/manual")
async def run_manual_cycle(
    db: Session = Depends(get_db),
    bot: TradingBot = Depends(get_trading_bot)
):
    """Execute one trading cycle manually (alias)"""
    result = await bot.run_cycle()
    
    if result.get('success') and 'analysis' in result:
        analysis = result['analysis']
        
        # Store signal in database
        signal_data = schemas.SignalCreate(
            ema20=analysis['tech_signals'].get('ema20', 0),
            ema50=analysis['tech_signals'].get('ema50', 0),
            rsi14=analysis['tech_signals'].get('rsi14', 0),
            ai_signal=analysis['ai_signal']['signal'],
            confidence=analysis['ai_signal']['confidence']
        )
        
        db_signal = models.Signal(**signal_data.dict())
        db.add(db_signal)
        
        # Update bot status
        status_data = schemas.BotStatusCreate(
            is_running=bot.is_running,
            btc_balance=analysis['btc_balance'],
            usd_balance=analysis['usd_balance']
        )
        
        db_status = models.BotStatus(**status_data.dict())
        db.add(db_status)
        
        db.commit()
    
    return result

@router.get("/analysis")
async def get_market_analysis(bot: TradingBot = Depends(get_trading_bot)):
    """Get current market analysis without trading"""
    analysis = await bot.analyze_market()
    return analysis if analysis else {"error": "Analysis failed"}

@router.get("/indicators/{pair}")
async def get_indicators(pair: str = "XBTUSDT", bot: TradingBot = Depends(get_trading_bot)):
    """Get technical indicators for a pair"""
    try:
        ohlc_data = bot.kraken.get_ohlc(pair)
        if not ohlc_data:
            return {"error": "No OHLC data available"}
        
        closes = [float(candle[4]) for candle in ohlc_data]
        indicators = TechnicalIndicators.analyze_signals(closes)
        
        return indicators
    except Exception as e:
        return {"error": str(e)}

@router.get("/scheduler/status")
async def get_scheduler_info():
    """Get scheduler status and next cycle info"""
    return get_scheduler_status()

@router.get("/logs")
async def get_logs(
    limit: int = Query(100, description="Maximum number of logs to return"),
    level: str | None = Query(None, description="Filter by log level (INFO, WARNING, ERROR)")
):
    """Get recent application logs"""
    handler = get_log_handler()
    logs = handler.get_logs(limit=limit, level=level)
    return {
        "logs": logs,
        "total": len(logs)
    }

@router.get("/logs/download")
async def download_logs():
    """Download complete log file"""
    # Check if running in production (systemd service)
    service_name = "kraken-ai-trading-bot"
    
    # Try to get logs from systemd journal (production)
    try:
        result = subprocess.run(
            ["journalctl", "-u", service_name, "--no-pager"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0 and result.stdout:
            # Return journalctl logs as file
            return Response(
                content=result.stdout,
                media_type="text/plain",
                headers={
                    "Content-Disposition": "attachment; filename=botija.log"
                }
            )
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
        # journalctl not available or failed, use in-memory logs
        pass
    
    # Fallback: Use in-memory logs (development)
    handler = get_log_handler()
    logs = handler.get_logs(limit=10000)  # Get up to 10k logs
    
    # Format logs as text
    log_lines = []
    for log in logs:
        log_lines.append(f"{log['timestamp']} - {log['logger']} - {log['level']} - {log['message']}")
    
    log_content = "\n".join(log_lines)
    
    return Response(
        content=log_content,
        media_type="text/plain",
        headers={
            "Content-Disposition": "attachment; filename=botija.log"
        }
    )

@router.get("/cycles", response_model=list[schemas.TradingCycle])
async def get_trading_cycles(
    limit: int = Query(50, description="Number of cycles to return"),
    db: Session = Depends(get_db)
):
    """Get recent trading cycle executions"""
    cycles = db.query(models.TradingCycle).order_by(models.TradingCycle.timestamp.desc()).limit(limit).all()
    return cycles

@router.get("/cycles/{cycle_id}", response_model=schemas.TradingCycle)
async def get_trading_cycle(cycle_id: int, db: Session = Depends(get_db)):
    """Get specific trading cycle details"""
    cycle = db.query(models.TradingCycle).filter(models.TradingCycle.id == cycle_id).first()
    if not cycle:
        return {"error": "Cycle not found"}
    return cycle

