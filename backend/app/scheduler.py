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
from .services.risk_manager import RiskManager

logger = logging.getLogger(__name__)

# Global instances
scheduler = BackgroundScheduler()
trading_bot: ForexTradingBot = None
risk_manager: RiskManager = None

# Track last cycle execution
last_cycle_info = {
    "timestamp": None,
    "status": "pending",
    "error": None,
    "trigger": None
}


def get_risk_manager() -> RiskManager:
    """Get or create risk manager instance"""
    global risk_manager

    if risk_manager is None and Config.RISK_MANAGER_ENABLED:
        risk_manager = RiskManager(
            max_daily_loss_percent=Config.MAX_DAILY_LOSS_PERCENT,
            max_drawdown_percent=Config.MAX_DRAWDOWN_PERCENT,
            max_consecutive_losses=Config.MAX_CONSECUTIVE_LOSSES,
            base_risk_per_trade_percent=Config.RISK_PER_TRADE_PERCENT
        )
        logger.info(f"🛡️ Risk Manager initialized: max daily loss {Config.MAX_DAILY_LOSS_PERCENT}%, max DD {Config.MAX_DRAWDOWN_PERCENT}%")

    return risk_manager


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
            trailing_stop_enabled=Config.TRAILING_STOP_ENABLED,
            trailing_stop_distance_pips=Config.TRAILING_STOP_DISTANCE_PIPS,
            trailing_stop_activation_pips=Config.TRAILING_STOP_ACTIVATION_PIPS
        )

        # Attach risk manager
        rm = get_risk_manager()
        if rm:
            trading_bot.set_risk_manager(rm)

        logger.info(f"✅ Trading bot initialized: {Config.DEFAULT_INSTRUMENT} ({Config.TRADING_MODE}) - Strategy: {Config.DEFAULT_STRATEGY}")

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
    from datetime import datetime, timezone

    jobs = scheduler.get_jobs() if scheduler.running else []

    # Calculate seconds until next run
    seconds_until_next = None
    next_run_time = None
    if jobs and jobs[0].next_run_time:
        next_run_time = jobs[0].next_run_time
        now = datetime.now(timezone.utc)
        if next_run_time.tzinfo is None:
            next_run_time = next_run_time.replace(tzinfo=timezone.utc)
        seconds_until_next = max(0, (next_run_time - now).total_seconds())

    return {
        "running": scheduler.running,
        "jobs": len(jobs),
        "next_run": str(next_run_time) if next_run_time else None,
        "next_run_time": str(next_run_time) if next_run_time else None,
        "seconds_until_next": seconds_until_next,
        "last_cycle": last_cycle_info,
        "last_cycle_result": last_cycle_info,
        "trading_mode": "DEMO"
    }


def trigger_manual_cycle():
    """Trigger a manual trading cycle (deprecated - use async version)"""
    run_trading_cycle(trigger="manual")
    return last_cycle_info


async def trigger_manual_cycle_async():
    """Trigger a manual trading cycle (async for FastAPI)"""
    return await run_trading_cycle_async(trigger="manual")
