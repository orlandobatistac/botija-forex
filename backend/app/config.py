"""
Configuration settings for Botija Forex
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Trading bot configuration"""

    # OANDA API
    OANDA_API_KEY = os.getenv("OANDA_API_KEY", "")
    OANDA_ACCOUNT_ID = os.getenv("OANDA_ACCOUNT_ID", "")
    OANDA_ENVIRONMENT = os.getenv("OANDA_ENVIRONMENT", "demo")  # demo or live
    OANDA_GRANULARITY = os.getenv("OANDA_GRANULARITY", "H4")  # M1, M5, M15, H1, H4, D

    # OpenAI
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

    # Telegram
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

    # Trading Parameters
    TRADING_MODE = os.getenv("TRADING_MODE", "DEMO")  # DEMO or LIVE
    DEFAULT_INSTRUMENT = os.getenv("DEFAULT_INSTRUMENT", "EUR_USD")

    # Multiple pairs (comma-separated)
    TRADING_INSTRUMENTS = os.getenv("TRADING_INSTRUMENTS", "EUR_USD").split(",")
    TRADING_INSTRUMENTS = [i.strip() for i in TRADING_INSTRUMENTS if i.strip()]

    # Position sizing (percentage-based)
    TRADE_AMOUNT_PERCENT = float(os.getenv("TRADE_AMOUNT_PERCENT", 10))  # % of balance per trade
    MIN_BALANCE_PERCENT = float(os.getenv("MIN_BALANCE_PERCENT", 20))  # % to keep as reserve

    # Risk management (pips)
    STOP_LOSS_PIPS = float(os.getenv("STOP_LOSS_PIPS", 50))
    TAKE_PROFIT_PIPS = float(os.getenv("TAKE_PROFIT_PIPS", 100))
    TRAILING_STOP_PIPS = float(os.getenv("TRAILING_STOP_PIPS", 30))

    # Scheduler
    TRADING_INTERVAL_HOURS = int(os.getenv("TRADING_INTERVAL_HOURS", 4))

    # Technical Indicators
    EMA_FAST_PERIOD = int(os.getenv("EMA_FAST_PERIOD", 20))
    EMA_SLOW_PERIOD = int(os.getenv("EMA_SLOW_PERIOD", 50))
    RSI_PERIOD = int(os.getenv("RSI_PERIOD", 14))

    # Trailing Stop
    TRAILING_STOP_ENABLED = os.getenv("TRAILING_STOP_ENABLED", "true").lower() == "true"
    TRAILING_STOP_DISTANCE_PIPS = float(os.getenv("TRAILING_STOP_DISTANCE_PIPS", 30))
    TRAILING_STOP_ACTIVATION_PIPS = float(os.getenv("TRAILING_STOP_ACTIVATION_PIPS", 20))

    # Risk Management
    RISK_MANAGER_ENABLED = os.getenv("RISK_MANAGER_ENABLED", "true").lower() == "true"
    MAX_DAILY_LOSS_PERCENT = float(os.getenv("MAX_DAILY_LOSS_PERCENT", 3.0))
    MAX_DRAWDOWN_PERCENT = float(os.getenv("MAX_DRAWDOWN_PERCENT", 10.0))
    MAX_CONSECUTIVE_LOSSES = int(os.getenv("MAX_CONSECUTIVE_LOSSES", 3))
    RISK_PER_TRADE_PERCENT = float(os.getenv("RISK_PER_TRADE_PERCENT", 1.0))

    # Multi-Timeframe Analysis
    MULTI_TIMEFRAME_ENABLED = os.getenv("MULTI_TIMEFRAME_ENABLED", "true").lower() == "true"

    # Active Strategy
    ACTIVE_STRATEGY = os.getenv("ACTIVE_STRATEGY", "Triple EMA")
    USE_TRIPLE_EMA_STRATEGY = os.getenv("USE_TRIPLE_EMA_STRATEGY", "true").lower() == "true"

    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./botija-forex.db")

    # API Server
    API_HOST = os.getenv("API_HOST", "0.0.0.0")
    API_PORT = int(os.getenv("API_PORT", 8001))
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
