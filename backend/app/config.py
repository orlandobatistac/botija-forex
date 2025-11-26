"""
Bot configuration settings
"""

import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Trading bot configuration"""
    
    # Kraken API
    KRAKEN_API_KEY = os.getenv('KRAKEN_API_KEY', '')
    KRAKEN_SECRET_KEY = os.getenv('KRAKEN_SECRET_KEY', '')
    
    # OpenAI
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
    
    # Telegram
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')
    
    # Trading Parameters
    # Trading amounts - can use fixed USD or percentage
    TRADE_AMOUNT_USD = float(os.getenv('TRADE_AMOUNT_USD', 0))  # 0 = use percentage
    TRADE_AMOUNT_PERCENT = float(os.getenv('TRADE_AMOUNT_PERCENT', 10))  # 10% default
    MIN_BALANCE_USD = float(os.getenv('MIN_BALANCE_USD', 0))  # 0 = use percentage
    MIN_BALANCE_PERCENT = float(os.getenv('MIN_BALANCE_PERCENT', 20))  # 20% default
    TRAILING_STOP_PERCENTAGE = float(os.getenv('TRAILING_STOP_PERCENTAGE', 0.99))
    TRADING_INTERVAL_HOURS = int(os.getenv('TRADING_INTERVAL_HOURS', 1))  # Execute every N hours on the hour
    
    # Technical Analysis
    KRAKEN_OHLC_INTERVAL = int(os.getenv('KRAKEN_OHLC_INTERVAL', 240))  # 1=1min, 5=5min, 15=15min, 30=30min, 60=1h, 240=4h, 1440=1day
    
    # Bot Parameters
    TRADING_ENABLED = os.getenv('TRADING_ENABLED', 'true').lower() == 'true'
    TRADING_INTERVAL = int(os.getenv('TRADING_INTERVAL', 3600))  # 1 hour in seconds
    
    # Database
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./kraken-ai-trading-bot.db')
    
    # API
    API_HOST = os.getenv('API_HOST', '0.0.0.0')
    API_PORT = int(os.getenv('API_PORT', 8001))
    DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'
    
    # Technical Indicators
    EMA20_PERIOD = 20
    EMA50_PERIOD = 50
    RSI14_PERIOD = 14
    
    # Trading Strategy
    BUY_RSI_MIN = 45
    BUY_RSI_MAX = 60
    SELL_RSI_MIN = 40
