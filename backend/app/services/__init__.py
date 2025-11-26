"""Services package for Botija Forex"""

from .oanda_client import OandaClient
from .technical_indicators import TechnicalIndicators
from .ai_validator import AISignalValidator
from .telegram_alerts import TelegramAlerts
from .trailing_stop import TrailingStop
from .forex_trailing_stop import ForexTrailingStop
from .risk_manager import RiskManager
from .multi_timeframe import MultiTimeframeAnalyzer
from .multi_pair import MultiPairManager
from .backtester import Backtester
from .log_handler import get_log_handler, setup_log_handler
from .sentiment_analyzer import SentimentAnalyzer
from .economic_calendar import EconomicCalendar
from .news_sentiment import NewsSentimentAnalyzer
from .enhanced_ai_validator import EnhancedAIValidator, MarketContext

__all__ = [
    "OandaClient",
    "TechnicalIndicators",
    "AISignalValidator",
    "TelegramAlerts",
    "TrailingStop",
    "ForexTrailingStop",
    "RiskManager",
    "MultiTimeframeAnalyzer",
    "MultiPairManager",
    "Backtester",
    "get_log_handler",
    "setup_log_handler",
    "SentimentAnalyzer",
    "EconomicCalendar",
    "NewsSentimentAnalyzer",
    "EnhancedAIValidator",
    "MarketContext",
]
