"""
Market Sentiment Analyzer
Aggregates sentiment from multiple sources for Forex trading
"""

import logging
import requests
from typing import Dict, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class SentimentLevel(Enum):
    """Sentiment classification"""
    EXTREME_FEAR = "EXTREME_FEAR"
    FEAR = "FEAR"
    NEUTRAL = "NEUTRAL"
    GREED = "GREED"
    EXTREME_GREED = "EXTREME_GREED"


@dataclass
class SentimentData:
    """Aggregated sentiment data"""
    fear_greed_index: int  # 0-100
    fear_greed_label: str
    oanda_long_percent: float  # % of traders long
    oanda_short_percent: float  # % of traders short
    oanda_sentiment: str  # BULLISH, BEARISH, NEUTRAL
    news_sentiment: float  # -1.0 to 1.0
    news_summary: str
    has_high_impact_event: bool
    next_event: Optional[str]
    overall_sentiment: SentimentLevel
    confidence: int  # 0-100
    timestamp: datetime


class FearGreedFetcher:
    """
    Fetches Fear & Greed Index from alternative.me
    Note: This is crypto-based but correlates with risk sentiment
    """

    API_URL = "https://api.alternative.me/fng/"

    def __init__(self):
        self.logger = logger
        self._cache: Optional[Dict] = None
        self._cache_time: Optional[datetime] = None
        self._cache_duration = timedelta(hours=1)

    def get_index(self) -> Dict:
        """
        Get current Fear & Greed Index.

        Returns:
            Dict with value (0-100) and classification
        """
        # Check cache
        if self._cache and self._cache_time:
            if datetime.now() - self._cache_time < self._cache_duration:
                return self._cache

        try:
            response = requests.get(self.API_URL, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get("data"):
                fng = data["data"][0]
                result = {
                    "value": int(fng.get("value", 50)),
                    "classification": fng.get("value_classification", "Neutral"),
                    "timestamp": fng.get("timestamp"),
                    "source": "alternative.me"
                }

                # Cache result
                self._cache = result
                self._cache_time = datetime.now()

                self.logger.info(f"📊 Fear & Greed: {result['value']} ({result['classification']})")
                return result

            return {"value": 50, "classification": "Neutral", "error": "No data"}

        except Exception as e:
            self.logger.error(f"Error fetching Fear & Greed: {e}")
            return {"value": 50, "classification": "Neutral", "error": str(e)}


class OandaSentimentFetcher:
    """
    Fetches trader sentiment from OANDA
    Uses open position ratios
    """

    def __init__(self, oanda_client):
        self.oanda = oanda_client
        self.logger = logger

    def get_sentiment(self, instrument: str = "EUR_USD") -> Dict:
        """
        Get OANDA trader sentiment for an instrument.

        Returns:
            Dict with long/short percentages
        """
        try:
            # OANDA provides this via their API
            # Endpoint: /v3/instruments/{instrument}/positionBook
            endpoint = f"/v3/instruments/{instrument}/positionBook"

            response = self.oanda._request("GET", endpoint)

            if "error" in response:
                # Fallback to default neutral
                return {
                    "instrument": instrument,
                    "long_percent": 50.0,
                    "short_percent": 50.0,
                    "sentiment": "NEUTRAL",
                    "contrarian_signal": "HOLD"
                }

            # Parse position book
            position_book = response.get("positionBook", {})
            buckets = position_book.get("buckets", [])

            # Calculate long vs short from buckets
            total_long = 0
            total_short = 0

            for bucket in buckets:
                long_count = float(bucket.get("longCountPercent", 0))
                short_count = float(bucket.get("shortCountPercent", 0))
                total_long += long_count
                total_short += short_count

            # Normalize
            total = total_long + total_short
            if total > 0:
                long_percent = (total_long / total) * 100
                short_percent = (total_short / total) * 100
            else:
                long_percent = 50.0
                short_percent = 50.0

            # Determine sentiment and contrarian signal
            if long_percent > 60:
                sentiment = "BULLISH"
                contrarian = "SELL"  # Crowd is long, fade them
            elif short_percent > 60:
                sentiment = "BEARISH"
                contrarian = "BUY"  # Crowd is short, fade them
            else:
                sentiment = "NEUTRAL"
                contrarian = "HOLD"

            result = {
                "instrument": instrument,
                "long_percent": round(long_percent, 1),
                "short_percent": round(short_percent, 1),
                "sentiment": sentiment,
                "contrarian_signal": contrarian
            }

            self.logger.info(
                f"📊 OANDA Sentiment {instrument}: "
                f"{result['long_percent']}% Long / {result['short_percent']}% Short"
            )

            return result

        except Exception as e:
            self.logger.error(f"Error fetching OANDA sentiment: {e}")
            return {
                "instrument": instrument,
                "long_percent": 50.0,
                "short_percent": 50.0,
                "sentiment": "NEUTRAL",
                "contrarian_signal": "HOLD",
                "error": str(e)
            }


class SentimentAnalyzer:
    """
    Main sentiment aggregator.
    Combines all sentiment sources into unified signal.
    """

    def __init__(self, oanda_client=None):
        self.fear_greed = FearGreedFetcher()
        self.oanda_sentiment = OandaSentimentFetcher(oanda_client) if oanda_client else None
        self.logger = logger

    def _classify_fear_greed(self, value: int) -> SentimentLevel:
        """Classify Fear & Greed value"""
        if value <= 20:
            return SentimentLevel.EXTREME_FEAR
        elif value <= 40:
            return SentimentLevel.FEAR
        elif value <= 60:
            return SentimentLevel.NEUTRAL
        elif value <= 80:
            return SentimentLevel.GREED
        else:
            return SentimentLevel.EXTREME_GREED

    def get_full_sentiment(self, instrument: str = "EUR_USD") -> SentimentData:
        """
        Get aggregated sentiment from all sources.

        Returns:
            SentimentData with all sentiment metrics
        """
        # Get Fear & Greed
        fng = self.fear_greed.get_index()
        fng_value = fng.get("value", 50)
        fng_label = fng.get("classification", "Neutral")

        # Get OANDA sentiment
        if self.oanda_sentiment:
            oanda = self.oanda_sentiment.get_sentiment(instrument)
        else:
            oanda = {
                "long_percent": 50.0,
                "short_percent": 50.0,
                "sentiment": "NEUTRAL",
                "contrarian_signal": "HOLD"
            }

        # Placeholder for news (implemented in news_fetcher.py)
        news_sentiment = 0.0
        news_summary = "No news data available"

        # Placeholder for calendar (implemented in economic_calendar.py)
        has_event = False
        next_event = None

        # Calculate overall sentiment
        overall = self._calculate_overall(fng_value, oanda)

        # Calculate confidence
        confidence = self._calculate_confidence(fng_value, oanda)

        return SentimentData(
            fear_greed_index=fng_value,
            fear_greed_label=fng_label,
            oanda_long_percent=oanda["long_percent"],
            oanda_short_percent=oanda["short_percent"],
            oanda_sentiment=oanda["sentiment"],
            news_sentiment=news_sentiment,
            news_summary=news_summary,
            has_high_impact_event=has_event,
            next_event=next_event,
            overall_sentiment=overall,
            confidence=confidence,
            timestamp=datetime.now()
        )

    def _calculate_overall(self, fng: int, oanda: Dict) -> SentimentLevel:
        """Calculate overall market sentiment"""
        # Weight: Fear & Greed 40%, OANDA contrarian 60%

        # Convert OANDA to score (-1 to 1)
        oanda_score = (oanda["long_percent"] - 50) / 50  # -1 if all short, +1 if all long

        # Convert Fear & Greed to score (-1 to 1)
        fng_score = (fng - 50) / 50

        # Weighted average (OANDA contrarian - invert the score)
        combined = (fng_score * 0.4) + (-oanda_score * 0.6)  # Negative because contrarian

        # Map to sentiment level
        if combined <= -0.4:
            return SentimentLevel.EXTREME_FEAR
        elif combined <= -0.2:
            return SentimentLevel.FEAR
        elif combined <= 0.2:
            return SentimentLevel.NEUTRAL
        elif combined <= 0.4:
            return SentimentLevel.GREED
        else:
            return SentimentLevel.EXTREME_GREED

    def _calculate_confidence(self, fng: int, oanda: Dict) -> int:
        """Calculate confidence in sentiment signal"""
        # Higher confidence when sources agree

        # Fear & Greed extremes = higher confidence
        fng_confidence = abs(fng - 50) * 2  # 0-100

        # OANDA extreme positioning = higher confidence
        oanda_extreme = abs(oanda["long_percent"] - 50) * 2  # 0-100

        # Average
        confidence = int((fng_confidence + oanda_extreme) / 2)

        return min(confidence, 100)

    def to_dict(self, data: SentimentData) -> Dict:
        """Convert SentimentData to JSON-serializable dict"""
        return {
            "fear_greed_index": data.fear_greed_index,
            "fear_greed_label": data.fear_greed_label,
            "oanda_long_percent": data.oanda_long_percent,
            "oanda_short_percent": data.oanda_short_percent,
            "oanda_sentiment": data.oanda_sentiment,
            "news_sentiment": data.news_sentiment,
            "news_summary": data.news_summary,
            "has_high_impact_event": data.has_high_impact_event,
            "next_event": data.next_event,
            "overall_sentiment": data.overall_sentiment.value,
            "confidence": data.confidence,
            "timestamp": data.timestamp.isoformat()
        }
