"""
Scheduler para ejecutar ciclos de trading automáticamente
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import logging
import asyncio
import os
from datetime import datetime
from .services.trading_bot import TradingBot
from .services.kraken_client import KrakenClient
from .config import Config

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()
trading_bot = None

# Track last cycle execution
last_cycle_info = {
    "timestamp": None,
    "status": "pending",
    "error": None,
    "trigger": None  # "manual" or "scheduled"
}

def init_scheduler():
    """Inicializa el scheduler con el bot de trading"""
    global trading_bot, last_cycle_info
    
    try:
        # Load last cycle from database
        from .database import SessionLocal
        from .models import TradingCycle
        
        db = SessionLocal()
        try:
            last_db_cycle = db.query(TradingCycle).order_by(TradingCycle.timestamp.desc()).first()
            if last_db_cycle:
                last_cycle_info["timestamp"] = last_db_cycle.timestamp.strftime('%Y-%m-%dT%H:%M:%SZ')
                last_cycle_info["status"] = "success" if last_db_cycle.action in ["BOUGHT", "SOLD", "HOLD"] else "error"
                last_cycle_info["error"] = last_db_cycle.error_message
                last_cycle_info["trigger"] = last_db_cycle.trigger or "scheduled"
                logger.info(f"📊 Loaded last cycle from DB: {last_db_cycle.timestamp} - {last_db_cycle.action}")
        finally:
            db.close()
        
        config = Config()
        
        # Obtener credenciales y parámetros
        kraken_key = os.getenv('KRAKEN_API_KEY', '')
        kraken_secret = os.getenv('KRAKEN_SECRET_KEY', '')
        openai_key = os.getenv('OPENAI_API_KEY', '')
        telegram_token = os.getenv('TELEGRAM_TOKEN', '')
        telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
        
        # Inicializar bot con todos los parámetros
        trading_bot = TradingBot(
            kraken_api_key=kraken_key,
            kraken_secret=kraken_secret,
            openai_api_key=openai_key,
            telegram_token=telegram_token,
            telegram_chat_id=telegram_chat_id,
            trade_amount=config.TRADE_AMOUNT_USD,
            trade_amount_percent=config.TRADE_AMOUNT_PERCENT,
            min_balance=config.MIN_BALANCE_USD,
            min_balance_percent=config.MIN_BALANCE_PERCENT,
            trailing_stop_pct=config.TRAILING_STOP_PERCENTAGE
        )
        
        mode = "REAL TRADING" if (kraken_key and kraken_secret) else "PAPER TRADING"
        logger.info(f"✅ Bot inicializado en modo {mode}")
        
        # Get interval in hours from config
        interval_hours = config.TRADING_INTERVAL_HOURS
        
        # Build cron expression for every N hours on the hour
        # Examples:
        # 1 hour: */1 (every hour: 19:00, 20:00, 21:00...)
        # 2 hours: */2 (every 2 hours: 20:00, 22:00, 00:00...)
        # 4 hours: */4 (every 4 hours: 20:00, 00:00, 04:00...)
        # 24 hours: 0 (once per day at midnight: 00:00)
        
        if interval_hours == 24:
            # Special case: once per day at midnight
            hour_expr = '0'
            desc = 'daily at midnight (00:00 ET)'
        else:
            # Every N hours on the hour
            hour_expr = f'*/{interval_hours}'
            desc = f'every {interval_hours} hour(s) on the hour (ET)'
        
        scheduler.add_job(
            run_trading_cycle,
            CronTrigger(minute=0, hour=hour_expr, timezone='America/New_York'),
            id='trading_cycle',
            name=f'Trading cycle - {desc}',
            replace_existing=True
        )
        
        scheduler.start()
        logger.info(f"✅ Scheduler iniciado - Ciclo de trading {desc} (Charlotte, NC)")
        
    except Exception as e:
        logger.warning(f"⚠️  Scheduler deshabilitado: {e}")


def run_trading_cycle():
    """Ejecuta un ciclo completo de trading"""
    global last_cycle_info
    
    try:
        now = datetime.utcnow()
        logger.info(f"🔄 Iniciando ciclo de trading - {now.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Update cycle start
        last_cycle_info["timestamp"] = now.strftime('%Y-%m-%dT%H:%M:%SZ')
        last_cycle_info["status"] = "running"
        last_cycle_info["error"] = None
        last_cycle_info["trigger"] = "scheduled"
        
        # Ejecutar en loop asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(trading_bot.run_cycle())
        
        # Update cycle success
        last_cycle_info["status"] = "success"
        logger.info(f"✅ Ciclo de trading completado - {datetime.now().strftime('%H:%M:%S')}")
        
    except Exception as e:
        # Update cycle error
        last_cycle_info["status"] = "error"
        last_cycle_info["error"] = str(e)
        logger.error(f"❌ Error en ciclo de trading: {e}")

def shutdown_scheduler():
    """Apaga el scheduler gracefully"""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("✅ Scheduler detenido")

def get_scheduler_status():
    """Retorna el estado actual del scheduler con countdown preciso"""
    from datetime import datetime
    import pytz
    
    status = {
        "running": scheduler.running,
        "jobs": len(scheduler.get_jobs()) if scheduler.running else 0,
        "next_run_time": None,
        "seconds_until_next": 0,
        "last_cycle": last_cycle_info["timestamp"],
        "last_cycle_result": {
            "status": last_cycle_info["status"],
            "error": last_cycle_info["error"],
            "trigger": last_cycle_info["trigger"]
        }
    }
    
    if not scheduler.running:
        return status
    
    try:
        jobs = scheduler.get_jobs()
        if not jobs:
            return status
        
        job = jobs[0]
        if not job.next_run_time:
            return status
        
        next_run = job.next_run_time
        
        # Obtener tiempo actual con timezone awareness
        if next_run.tzinfo:
            now = datetime.now(next_run.tzinfo)
        else:
            now = datetime.now()
        
        # Calcular diferencia en segundos
        time_diff = next_run - now
        seconds = int(time_diff.total_seconds())
        
        status["next_run_time"] = next_run.isoformat()
        status["seconds_until_next"] = max(0, seconds)
        
        logger.debug(f"Scheduler status: next_run={next_run}, now={now}, seconds={seconds}")
        
    except Exception as e:
        logger.error(f"Error calculating scheduler status: {e}")
        status["error"] = str(e)
    
    return status

