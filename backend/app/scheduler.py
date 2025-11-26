"""
Scheduler for automated trading cycles
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import logging
import asyncio
from datetime import datetime

from .config import Config
from .services.forex_trading_bot import ForexTradingBot

logger = logging.getLogger(__name__)

# Global instances
scheduler = BackgroundScheduler()
trading_bot: ForexTradingBot = None

# Track last cycle execution
last_cycle_info = {
    "timestamp": None,
    "status": "pending",
    "error": None,
    "trigger": None
}


def get_trading_bot() -> ForexTradingBot:
    """Get or create trading bot instance"""
    global trading_bot

    if trading_bot is None:
        trading_bot = ForexTradingBot(
            oanda_api_key=Config.OANDA_API_KEY,
            oanda_account_id=Config.OANDA_ACCOUNT_ID,
            oanda_environment=Config.OANDA_ENVIRONMENT,
            openai_api_key=Config.OPENAI_API_KEY,
            telegram_token=Config.TELEGRAM_TOKEN,
            telegram_chat_id=Config.TELEGRAM_CHAT_ID,
            instrument=Config.DEFAULT_INSTRUMENT,
            trade_amount_percent=Config.TRADE_AMOUNT_PERCENT,
            min_balance_percent=Config.MIN_BALANCE_PERCENT,
            stop_loss_pips=Config.STOP_LOSS_PIPS,
            take_profit_pips=Config.TAKE_PROFIT_PIPS,
            trailing_stop_pips=Config.TRAILING_STOP_PIPS
        )
        logger.info(f"✅ Trading bot initialized: {Config.DEFAULT_INSTRUMENT} ({Config.TRADING_MODE})")

    return trading_bot


def run_trading_cycle(trigger: str = "scheduled"):
    """Execute one trading cycle (sync version for scheduler)"""
    global last_cycle_info

    try:
        bot = get_trading_bot()

        # Run async cycle in sync context (for APScheduler)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(bot.run_cycle(trigger=trigger))
        loop.close()

        last_cycle_info = {
            "timestamp": datetime.now().isoformat(),
            "status": "success" if result.get("success") else "error",
            "error": result.get("error"),
            "trigger": trigger,
            "action": result.get("action")
        }

        logger.info(f"📊 Cycle completed: {result.get('action', 'N/A')} (trigger={trigger})")

    except Exception as e:
        logger.error(f"❌ Cycle error: {e}")
        last_cycle_info = {
            "timestamp": datetime.now().isoformat(),
            "status": "error",
            "error": str(e),
            "trigger": trigger
        }


async def run_trading_cycle_async(trigger: str = "manual"):
    """Execute one trading cycle (async version for FastAPI endpoints)"""
    global last_cycle_info

    try:
        bot = get_trading_bot()
        result = await bot.run_cycle(trigger=trigger)

        last_cycle_info = {
            "timestamp": datetime.now().isoformat(),
            "status": "success" if result.get("success") else "error",
            "error": result.get("error"),
            "trigger": trigger,
            "action": result.get("action")
        }

        logger.info(f"📊 Cycle completed: {result.get('action', 'N/A')} (trigger={trigger})")
        return last_cycle_info

    except Exception as e:
        logger.error(f"❌ Cycle error: {e}")
        last_cycle_info = {
            "timestamp": datetime.now().isoformat(),
            "status": "error",
            "error": str(e),
            "trigger": trigger
        }
        return last_cycle_info


def init_scheduler():
    """Initialize the scheduler with trading cycles"""
    global scheduler

    try:
        interval_hours = Config.TRADING_INTERVAL_HOURS

        # Build cron expression for every N hours
        if interval_hours == 1:
            cron_hour = "*"
        elif interval_hours in [2, 3, 4, 6, 8, 12]:
            cron_hour = f"*/{interval_hours}"
        else:
            cron_hour = f"*/{interval_hours}"

        trigger = CronTrigger(hour=cron_hour, minute=0)

        scheduler.add_job(
            run_trading_cycle,
            trigger=trigger,
            id="trading_cycle",
            name="Forex Trading Cycle",
            replace_existing=True,
            kwargs={"trigger": "scheduled"}
        )

        scheduler.start()
        logger.info(f"⏰ Scheduler started: every {interval_hours}h at :00")

    except Exception as e:
        logger.error(f"❌ Scheduler init error: {e}")


def shutdown_scheduler():
    """Shutdown the scheduler"""
    global scheduler

    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("⏹️ Scheduler stopped")


def get_scheduler_status() -> dict:
    """Get scheduler status"""
    jobs = scheduler.get_jobs() if scheduler.running else []

    return {
        "running": scheduler.running,
        "jobs": len(jobs),
        "next_run": str(jobs[0].next_run_time) if jobs else None,
        "last_cycle": last_cycle_info
    }


def trigger_manual_cycle():
    """Trigger a manual trading cycle (deprecated - use async version)"""
    run_trading_cycle(trigger="manual")
    return last_cycle_info


async def trigger_manual_cycle_async():
    """Trigger a manual trading cycle (async for FastAPI)"""
    return await run_trading_cycle_async(trigger="manual")
