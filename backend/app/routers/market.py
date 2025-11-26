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


@router.get("/backtest/{instrument}")
async def run_backtest(
    instrument: str,
    timeframe: str = "H4",
    candles: int = 500,
    stop_loss: float = 50.0,
    take_profit: float = 100.0
):
    """
    Run a backtest on historical data.

    Args:
        instrument: Currency pair (EUR_USD, GBP_USD, etc.)
        timeframe: Candle granularity (H1, H4, D)
        candles: Number of candles to test (max 5000)
        stop_loss: Stop loss in pips
        take_profit: Take profit in pips
    """
    try:
        oanda = get_oanda_client()
        if not oanda:
            raise HTTPException(status_code=503, detail="OANDA not configured")

        instrument = instrument.upper().replace("-", "_")

        backtester = Backtester(
            oanda_client=oanda,
            instrument=instrument,
            stop_loss_pips=stop_loss,
            take_profit_pips=take_profit
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
    Run backtest on all configured pairs and return summary.
    """
    try:
        oanda = get_oanda_client()
        if not oanda:
            raise HTTPException(status_code=503, detail="OANDA not configured")

        results = []

        for instrument in Config.TRADING_INSTRUMENTS:
            backtester = Backtester(
                oanda_client=oanda,
                instrument=instrument,
                stop_loss_pips=Config.STOP_LOSS_PIPS,
                take_profit_pips=Config.TAKE_PROFIT_PIPS
            )

            result = backtester.run(timeframe=timeframe, candle_count=candles)

            results.append({
                "instrument": instrument,
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

