"""
Market analysis router - Multi-pair and multi-timeframe endpoints
"""

from fastapi import APIRouter, HTTPException
import logging

from ..config import Config
from ..services.oanda_client import OandaClient
from ..services.multi_timeframe import MultiTimeframeAnalyzer
from ..services.multi_pair import MultiPairManager
from ..services.backtester import Backtester
from ..services.sentiment_analyzer import SentimentAnalyzer
from ..services.economic_calendar import EconomicCalendar
from ..services.news_sentiment import NewsSentimentAnalyzer
from ..services.enhanced_ai_validator import EnhancedAIValidator

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/market",
    tags=["market"]
)

# Lazy-loaded clients
_oanda_client: OandaClient = None
_multi_pair: MultiPairManager = None


def get_oanda_client() -> OandaClient:
    """Get or create OANDA client"""
    global _oanda_client
    if not _oanda_client and Config.OANDA_API_KEY:
        _oanda_client = OandaClient(
            api_key=Config.OANDA_API_KEY,
            account_id=Config.OANDA_ACCOUNT_ID,
            environment=Config.OANDA_ENVIRONMENT
        )
    return _oanda_client


def get_multi_pair() -> MultiPairManager:
    """Get or create multi-pair manager"""
    global _multi_pair
    oanda = get_oanda_client()
    if not _multi_pair and oanda:
        _multi_pair = MultiPairManager(oanda, Config.TRADING_INSTRUMENTS)
    return _multi_pair


@router.get("/pairs")
async def get_all_pairs_analysis():
    """
    Get analysis for all configured currency pairs.
    Returns signals sorted by confidence.
    """
    try:
        manager = get_multi_pair()
        if not manager:
            raise HTTPException(status_code=503, detail="OANDA not configured")

        return manager.get_summary()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing pairs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pairs/{instrument}")
async def get_pair_analysis(instrument: str):
    """
    Get detailed analysis for a specific pair.
    """
    try:
        manager = get_multi_pair()
        if not manager:
            raise HTTPException(status_code=503, detail="OANDA not configured")

        analysis = manager.analyze_pair(instrument.upper().replace("-", "_"))
        if not analysis:
            raise HTTPException(status_code=404, detail=f"No analysis for {instrument}")

        return {
            "instrument": analysis.instrument,
            "signal": analysis.signal,
            "confidence": analysis.confidence,
            "mtf_confirmed": analysis.mtf_confirmed,
            "current_price": analysis.current_price,
            "spread_pips": round(analysis.spread_pips, 2),
            "position_units": analysis.position_units,
            "reason": analysis.reason
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing {instrument}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mtf/{instrument}")
async def get_multi_timeframe(instrument: str):
    """
    Get multi-timeframe analysis (H1 + H4) for a pair.
    """
    try:
        oanda = get_oanda_client()
        if not oanda:
            raise HTTPException(status_code=503, detail="OANDA not configured")

        instrument = instrument.upper().replace("-", "_")
        analyzer = MultiTimeframeAnalyzer(oanda, instrument)

        return analyzer.get_confirmed_signal()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in MTF analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/opportunity")
async def get_best_opportunity():
    """
    Get the best trading opportunity across all pairs.
    Returns the highest confidence confirmed signal.
    """
    try:
        manager = get_multi_pair()
        if not manager:
            raise HTTPException(status_code=503, detail="OANDA not configured")

        opportunity = manager.get_best_opportunity()

        if not opportunity:
            return {
                "found": False,
                "message": "No trading opportunities"
            }

        return {
            "found": True,
            "instrument": opportunity.instrument,
            "signal": opportunity.signal,
            "confidence": opportunity.confidence,
            "current_price": opportunity.current_price,
            "spread_pips": round(opportunity.spread_pips, 2)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error finding opportunity: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/positions")
async def get_all_positions():
    """
    Get all open positions across monitored pairs.
    """
    try:
        manager = get_multi_pair()
        if not manager:
            raise HTTPException(status_code=503, detail="OANDA not configured")

        return manager.get_all_positions()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strategies")
async def get_strategies():
    """Get list of available trading strategies."""
    try:
        from ..services.strategies.registry import get_strategy_list
        return get_strategy_list()
    except Exception as e:
        logger.error(f"Error getting strategies: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/backtest/{instrument}")
async def run_backtest(
    instrument: str,
    timeframe: str = "H4",
    candles: int = 500,
    strategy: str = "rsi_ema200"
):
    """
    Run a backtest on historical data.

    Args:
        instrument: Currency pair (EUR_USD, GBP_USD, etc.)
        timeframe: Candle granularity (H1, H4, D)
        candles: Number of candles to test (max 5000)
        strategy: Strategy ID (triple_ema, rsi_ema200)
    """
    try:
        oanda = get_oanda_client()
        if not oanda:
            raise HTTPException(status_code=503, detail="OANDA not configured")

        instrument = instrument.upper().replace("-", "_")

        backtester = Backtester(
            oanda_client=oanda,
            instrument=instrument,
            strategy_id=strategy
        )

        result = backtester.run(
            timeframe=timeframe,
            candle_count=min(candles, 5000)  # OANDA limit
        )

        return backtester.to_dict(result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Backtest error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/backtest-summary")
async def run_multi_pair_backtest(
    timeframe: str = "H4",
    candles: int = 500
):
    """
    Run backtest on all configured pairs using the current strategy.
    """
    try:
        oanda = get_oanda_client()
        if not oanda:
            raise HTTPException(status_code=503, detail="OANDA not configured")

        results = []

        for instrument in Config.TRADING_INSTRUMENTS:
            backtester = Backtester(
                oanda_client=oanda,
                instrument=instrument
            )

            result = backtester.run(timeframe=timeframe, candle_count=candles)

            results.append({
                "instrument": instrument,
                "strategy": result.strategy,
                "total_trades": result.total_trades,
                "win_rate": result.win_rate,
                "total_pips": result.total_pips,
                "profit_factor": result.profit_factor,
                "max_drawdown": result.max_drawdown_pips
            })

        # Sort by total pips
        results.sort(key=lambda x: x['total_pips'], reverse=True)

        return {
            "timeframe": timeframe,
            "candles": candles,
            "pairs_tested": len(results),
            "results": results
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Multi-pair backtest error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Lazy-loaded sentiment services
_sentiment_analyzer: SentimentAnalyzer = None
_economic_calendar: EconomicCalendar = None
_news_analyzer: NewsSentimentAnalyzer = None
_enhanced_ai: EnhancedAIValidator = None


def get_sentiment_analyzer() -> SentimentAnalyzer:
    """Get or create sentiment analyzer"""
    global _sentiment_analyzer
    oanda = get_oanda_client()
    if not _sentiment_analyzer:
        _sentiment_analyzer = SentimentAnalyzer(oanda)
    return _sentiment_analyzer


def get_economic_calendar() -> EconomicCalendar:
    """Get or create economic calendar"""
    global _economic_calendar
    if not _economic_calendar:
        _economic_calendar = EconomicCalendar()
    return _economic_calendar


def get_news_analyzer() -> NewsSentimentAnalyzer:
    """Get or create news analyzer"""
    global _news_analyzer
    if not _news_analyzer:
        _news_analyzer = NewsSentimentAnalyzer()
    return _news_analyzer


def get_enhanced_ai() -> EnhancedAIValidator:
    """Get or create enhanced AI validator"""
    global _enhanced_ai
    if not _enhanced_ai and Config.OPENAI_API_KEY:
        _enhanced_ai = EnhancedAIValidator(Config.OPENAI_API_KEY)
    return _enhanced_ai


@router.get("/sentiment")
async def get_market_sentiment(instrument: str = "EUR_USD"):
    """
    Get comprehensive market sentiment analysis.
    Includes Fear & Greed, OANDA positions, economic calendar, and news.
    """
    try:
        sentiment = get_sentiment_analyzer()
        calendar = get_economic_calendar()
        news = get_news_analyzer()

        # Get all sentiment data
        sentiment_data = sentiment.get_aggregate_sentiment(instrument)
        events = calendar.get_upcoming_events(instrument)
        should_avoid = calendar.should_avoid_trading(instrument)
        news_sentiment = news.get_sentiment(instrument)

        # Get currencies from instrument
        currencies = instrument.split("_") if "_" in instrument else [instrument[:3], instrument[3:]]

        return {
            "instrument": instrument,
            "overall": {
                "score": sentiment_data.get("aggregate_score", 0),
                "bias": sentiment_data.get("bias", "neutral"),
                "confidence": sentiment_data.get("confidence", 0)
            },
            "fear_greed": sentiment_data.get("fear_greed", {}),
            "oanda_sentiment": sentiment_data.get("oanda_sentiment", {}),
            "economic_calendar": {
                "upcoming_events": [
                    {
                        "event": e["event"],
                        "currency": e["currency"],
                        "hours_until": round(e["hours_until"], 1)
                    }
                    for e in events[:5]  # Top 5 events
                ],
                "should_avoid_trading": should_avoid
            },
            "news": {
                "sentiment_score": news_sentiment.get("sentiment_score", 0),
                "bullish_count": news_sentiment.get("bullish_count", 0),
                "bearish_count": news_sentiment.get("bearish_count", 0),
                "headlines_analyzed": news_sentiment.get("headlines_analyzed", 0)
            }
        }

    except Exception as e:
        logger.error(f"Error getting sentiment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sentiment/signal")
async def get_ai_enhanced_signal(
    instrument: str = "EUR_USD",
    ema_short: float = 0,
    ema_long: float = 0,
    rsi: float = 50,
    price: float = 0
):
    """
    Get AI-enhanced trading signal with sentiment analysis.
    """
    try:
        ai = get_enhanced_ai()
        if not ai:
            raise HTTPException(status_code=503, detail="OpenAI not configured")

        sentiment = get_sentiment_analyzer()
        calendar = get_economic_calendar()
        news = get_news_analyzer()

        # Get context data
        sentiment_data = sentiment.get_aggregate_sentiment(instrument)
        should_avoid = calendar.should_avoid_trading(instrument)
        news_sentiment = news.get_sentiment(instrument)

        # Build technical data dict
        technical_data = {
            "ema_short": ema_short,
            "ema_long": ema_long,
            "rsi": rsi,
            "current_price": price,
            "instrument": instrument
        }

        # Get enhanced signal
        result = ai.get_enhanced_signal(
            technical_data=technical_data,
            sentiment_data=sentiment_data,
            news_data=news_sentiment,
            high_impact_event=should_avoid
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting enhanced signal: {e}")
        raise HTTPException(status_code=500, detail=str(e))

