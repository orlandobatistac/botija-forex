"""
Tests for sentiment analysis features - Phase 3
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from app.services.sentiment_analyzer import SentimentAnalyzer, FearGreedFetcher, OandaSentimentFetcher
from app.services.economic_calendar import EconomicCalendar, EventImpact, EconomicEvent
from app.services.news_sentiment import NewsSentimentAnalyzer
from app.services.enhanced_ai_validator import EnhancedAIValidator, MarketContext


class TestFearGreedFetcher:
    """Tests for Fear & Greed Index fetcher"""

    def test_initialization(self):
        """Fetcher should initialize correctly"""
        fetcher = FearGreedFetcher()
        assert fetcher._cache is None
        assert fetcher._cache_time is None

    @patch('requests.get')
    def test_get_index_success(self, mock_get):
        """Should fetch and parse Fear & Greed index"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "data": [{"value": "25", "value_classification": "Fear"}]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        fetcher = FearGreedFetcher()
        result = fetcher.get_index()

        assert result["value"] == 25
        assert result["classification"] == "Fear"

    @patch('requests.get')
    def test_get_index_uses_cache(self, mock_get):
        """Should use cache on subsequent calls"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "data": [{"value": "45", "value_classification": "Fear"}]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        fetcher = FearGreedFetcher()

        # First call
        result1 = fetcher.get_index()
        # Second call should use cache
        result2 = fetcher.get_index()

        assert mock_get.call_count == 1
        assert result1["value"] == result2["value"]

    @patch('requests.get')
    def test_get_index_error_fallback(self, mock_get):
        """Should return neutral on error"""
        mock_get.side_effect = Exception("Network error")

        fetcher = FearGreedFetcher()
        result = fetcher.get_index()

        assert result["value"] == 50
        assert result["classification"] == "Neutral"


class TestOandaSentimentFetcher:
    """Tests for OANDA position sentiment"""

    def test_initialization(self):
        """Fetcher should initialize with OANDA client"""
        mock_oanda = Mock()
        fetcher = OandaSentimentFetcher(mock_oanda)
        assert fetcher.oanda == mock_oanda

    def test_get_sentiment_bullish(self):
        """Should identify bullish sentiment when crowd is long"""
        mock_oanda = Mock()
        mock_oanda._request.return_value = {
            "positionBook": {
                "buckets": [
                    {"longCountPercent": 70, "shortCountPercent": 30}
                ]
            }
        }

        fetcher = OandaSentimentFetcher(mock_oanda)
        result = fetcher.get_sentiment("EUR_USD")

        assert result["sentiment"] == "BULLISH"
        assert result["contrarian_signal"] == "SELL"

    def test_get_sentiment_bearish(self):
        """Should identify bearish sentiment when crowd is short"""
        mock_oanda = Mock()
        mock_oanda._request.return_value = {
            "positionBook": {
                "buckets": [
                    {"longCountPercent": 30, "shortCountPercent": 70}
                ]
            }
        }

        fetcher = OandaSentimentFetcher(mock_oanda)
        result = fetcher.get_sentiment("EUR_USD")

        assert result["sentiment"] == "BEARISH"
        assert result["contrarian_signal"] == "BUY"

    def test_get_sentiment_error_fallback(self):
        """Should return neutral on error"""
        mock_oanda = Mock()
        mock_oanda._request.return_value = {"error": "API Error"}

        fetcher = OandaSentimentFetcher(mock_oanda)
        result = fetcher.get_sentiment("EUR_USD")

        assert result["sentiment"] == "NEUTRAL"
        assert result["contrarian_signal"] == "HOLD"


class TestSentimentAnalyzer:
    """Tests for aggregate sentiment analyzer"""

    def test_initialization_without_oanda(self):
        """Should work without OANDA client"""
        analyzer = SentimentAnalyzer(None)
        assert analyzer.fear_greed is not None
        assert analyzer.oanda_sentiment is None

    def test_initialization_with_oanda(self):
        """Should initialize with OANDA client"""
        mock_oanda = Mock()
        analyzer = SentimentAnalyzer(mock_oanda)
        assert analyzer.oanda_sentiment is not None


class TestEconomicCalendar:
    """Tests for economic calendar"""

    def test_initialization(self):
        """Calendar should initialize correctly"""
        calendar = EconomicCalendar()
        assert len(calendar.HIGH_IMPACT_EVENTS) > 0

    def test_high_impact_events_contains_nfp(self):
        """Should have NFP in high impact events"""
        calendar = EconomicCalendar()
        assert any("NFP" in e for e in calendar.HIGH_IMPACT_EVENTS)

    def test_high_impact_events_contains_fomc(self):
        """Should have FOMC in high impact events"""
        calendar = EconomicCalendar()
        assert any("FOMC" in e for e in calendar.HIGH_IMPACT_EVENTS)

    def test_is_high_impact_true(self):
        """Should detect high impact events"""
        calendar = EconomicCalendar()
        assert calendar._is_high_impact("US Non-Farm Payrolls") is True
        assert calendar._is_high_impact("FOMC Meeting") is True

    def test_is_high_impact_false(self):
        """Should not flag low impact events"""
        calendar = EconomicCalendar()
        assert calendar._is_high_impact("Housing Starts") is False

    def test_should_avoid_trading_no_events(self):
        """Should not avoid when no events"""
        calendar = EconomicCalendar()
        calendar._cache = []
        calendar._cache_time = datetime.now()

        result = calendar.should_avoid_trading("EUR_USD")
        assert result["should_avoid"] is False

    def test_filter_by_currency(self):
        """Should filter events by currency"""
        calendar = EconomicCalendar()
        events = [
            EconomicEvent("NFP", "US", "USD", EventImpact.HIGH, datetime.now(), None, None, None),
            EconomicEvent("BOE", "UK", "GBP", EventImpact.HIGH, datetime.now(), None, None, None)
        ]

        filtered = calendar._filter_by_currency(events, ["USD"])
        assert len(filtered) == 1
        assert filtered[0].currency == "USD"


class TestNewsSentimentAnalyzer:
    """Tests for news sentiment analysis"""

    def test_initialization(self):
        """Analyzer should initialize"""
        analyzer = NewsSentimentAnalyzer()
        assert len(analyzer.BULLISH_WORDS) > 0
        assert len(analyzer.BEARISH_WORDS) > 0

    def test_analyze_sentiment_bullish(self):
        """Bullish keywords should give positive score"""
        analyzer = NewsSentimentAnalyzer()
        score = analyzer._analyze_sentiment("EUR rallies on strong economic growth")
        assert score > 0

    def test_analyze_sentiment_bearish(self):
        """Bearish keywords should give negative score"""
        analyzer = NewsSentimentAnalyzer()
        score = analyzer._analyze_sentiment("USD falls amid recession fears")
        assert score < 0

    def test_analyze_sentiment_neutral(self):
        """Neutral headline should give zero score"""
        analyzer = NewsSentimentAnalyzer()
        score = analyzer._analyze_sentiment("Markets closed for holiday")
        assert score == 0

    def test_extract_currencies(self):
        """Should extract mentioned currencies"""
        analyzer = NewsSentimentAnalyzer()
        currencies = analyzer._extract_currencies("EUR/USD rises as ECB holds rates")
        assert "EUR" in currencies

    def test_multiple_bullish_keywords(self):
        """Multiple keywords should compound"""
        analyzer = NewsSentimentAnalyzer()
        score = analyzer._analyze_sentiment("EUR surges on strong growth, bulls rally")
        assert score > 0.5  # Multiple positive keywords


class TestMarketContext:
    """Tests for MarketContext dataclass"""

    def test_create_full_context(self):
        """Should create context with all fields"""
        context = MarketContext(
            instrument="EUR_USD",
            price=1.1025,
            ema_fast=1.1050,
            ema_slow=1.1000,
            rsi=45.0,
            spread_pips=1.2,
            position_units=0,
            balance=10000.0,
            fear_greed_index=35,
            fear_greed_label="Fear",
            oanda_long_percent=40.0,
            oanda_short_percent=60.0,
            news_sentiment=-0.2,
            news_summary="Mixed signals",
            has_high_impact_event=False,
            next_event=""
        )

        assert context.instrument == "EUR_USD"
        assert context.fear_greed_index == 35
        assert context.oanda_long_percent == 40.0

    def test_default_values(self):
        """Should have sensible defaults"""
        context = MarketContext(
            instrument="EUR_USD",
            price=1.1025,
            ema_fast=1.1050,
            ema_slow=1.1000,
            rsi=45.0,
            spread_pips=1.2,
            position_units=0,
            balance=10000.0
        )

        assert context.fear_greed_index == 50
        assert context.fear_greed_label == "Neutral"
        assert context.has_high_impact_event is False


class TestEnhancedAIValidator:
    """Tests for enhanced AI validator"""

    def test_initialization_without_key(self):
        """Should initialize without API key"""
        ai = EnhancedAIValidator(None)
        assert ai.client is None

    def test_initialization_with_key(self):
        """Should initialize with API key"""
        with patch('openai.OpenAI'):
            ai = EnhancedAIValidator("test-key")
            # Client should be created (mocked)

    @patch('openai.OpenAI')
    def test_get_signal_basic(self, mock_openai):
        """Basic signal should work"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="BUY | 0.75 | Bullish EMA cross | tech:80 sent:+10"))]
        mock_client.chat.completions.create.return_value = mock_response

        ai = EnhancedAIValidator("test-key")
        ai.client = mock_client

        result = ai.get_signal(
            instrument="EUR_USD",
            price=1.1025,
            ema_fast=1.1050,
            ema_slow=1.1000,
            rsi=45.0,
            spread_pips=1.2,
            position_units=0,
            balance=10000.0
        )

        assert "signal" in result

    @patch('openai.OpenAI')
    def test_get_signal_with_sentiment(self, mock_openai):
        """Signal with sentiment should include context"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="HOLD | 0.6 | Wait for confirmation | tech:50 sent:-20"))]
        mock_client.chat.completions.create.return_value = mock_response

        ai = EnhancedAIValidator("test-key")
        ai.client = mock_client

        sentiment_data = {
            "fear_greed_index": 25,
            "fear_greed_label": "Fear",
            "oanda_long_percent": 30.0,
            "oanda_short_percent": 70.0
        }

        news_data = {
            "sentiment_score": -0.3,
            "summary": "Bearish news"
        }

        calendar_data = {
            "has_event": True,
            "next_event": "NFP",
            "should_avoid": False,
            "avoid_reason": ""
        }

        result = ai.get_signal(
            instrument="EUR_USD",
            price=1.1025,
            ema_fast=1.1050,
            ema_slow=1.1000,
            rsi=45.0,
            spread_pips=1.2,
            position_units=0,
            balance=10000.0,
            sentiment_data=sentiment_data,
            news_data=news_data,
            calendar_data=calendar_data
        )

        assert result["signal"] in ["BUY", "SELL", "HOLD"]

    def test_no_client_returns_hold(self):
        """Should return HOLD when no client configured"""
        ai = EnhancedAIValidator(None)

        context = MarketContext(
            instrument="EUR_USD",
            price=1.1025,
            ema_fast=1.1050,
            ema_slow=1.1000,
            rsi=45.0,
            spread_pips=1.2,
            position_units=0,
            balance=10000.0
        )

        result = ai.get_enhanced_signal(context)

        assert result["signal"] == "HOLD"
        assert result["ai_enabled"] is False
class TestSentimentIntegration:
    """Integration tests for sentiment features"""

    def test_all_services_instantiate(self):
        """All sentiment services should instantiate"""
        sentiment = SentimentAnalyzer(None)
        calendar = EconomicCalendar()
        news = NewsSentimentAnalyzer()
        ai = EnhancedAIValidator(None)

        assert sentiment is not None
        assert calendar is not None
        assert news is not None
        assert ai is not None

    def test_market_context_full_scenario(self):
        """Full market context scenario"""
        context = MarketContext(
            instrument="EUR_USD",
            price=1.1025,
            ema_fast=1.1050,  # Bullish cross
            ema_slow=1.1000,
            rsi=45.0,  # Neutral
            spread_pips=1.2,
            position_units=0,
            balance=10000.0,
            fear_greed_index=25,  # Fear (contrarian bullish)
            fear_greed_label="Fear",
            oanda_long_percent=35.0,  # More shorts (contrarian bullish)
            oanda_short_percent=65.0,
            news_sentiment=0.3,  # Slightly bullish
            has_high_impact_event=False
        )

        # Technical bullish (EMA fast > slow)
        assert context.ema_fast > context.ema_slow

        # Sentiment contrarian bullish (fear + more shorts)
        assert context.fear_greed_index < 40
        assert context.oanda_short_percent > context.oanda_long_percent

        # News slightly bullish
        assert context.news_sentiment > 0

        # No event blocking
        assert context.has_high_impact_event is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
