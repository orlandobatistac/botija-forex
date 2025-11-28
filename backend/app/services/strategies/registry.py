"""
Strategy Registry
==================
Central registry for all trading strategies.
Allows dynamic strategy selection via configuration or API.
"""

from typing import Dict, Type, Any, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class StrategyInfo:
    """Metadata about a strategy."""
    id: str
    name: str
    description: str
    class_path: str
    default_params: Dict[str, Any]


# Registry of available strategies
STRATEGIES: Dict[str, StrategyInfo] = {
    "hybrid": StrategyInfo(
        id="hybrid",
        name="Hybrid Breakout+MACD",
        description="ADX Switch: Breakout (consolidación) + MACD (tendencia). Walk-Forward: 71% consistencia, +1426 pips",
        class_path="backend.app.services.strategies.hybrid.HybridStrategy",
        default_params={
            "adx_switch_threshold": 30,
            "breakout_range_period": 30,
            "breakout_extension": 1.5,
            "macd_fast": 12,
            "macd_slow": 26,
            "macd_risk_reward": 2.5
        }
    ),
    "adaptive": StrategyInfo(
        id="adaptive",
        name="Adaptive Regime",
        description="Detecta régimen de mercado (trending/ranging/volatile) y adapta estrategia. Backtest: 100% años rentables EUR_USD",
        class_path="backend.app.services.strategies.adaptive.AdaptiveStrategy",
        default_params={
            "adx_trending_threshold": 25.0,
            "atr_sl_multiplier": 2.0,
            "rr_ratio": 2.5,
            "trade_ranging": False,  # Desactivado por backtest
            "trade_volatile": False,
            "trade_quiet": False
        }
    ),
    "triple_ema": StrategyInfo(
        id="triple_ema",
        name="Triple EMA",
        description="Trend following with EMA 20/50/200 + ATR SL + R:R 1:4 + ADX>30",
        class_path="backend.app.services.strategies.triple_ema.TripleEMAStrategy",
        default_params={
            "rr_ratio": 4.0,  # 1:4 para compensar win rate ~30%
            "min_adx": 30.0,  # Solo tendencias muy fuertes
            "atr_sl_multiplier": 1.5,  # SL = 1.5x ATR
            "use_atr_sl": True,
            "use_adx_filter": True,
            "use_slope_filter": True
        }
    ),
    "rsi_ema200": StrategyInfo(
        id="rsi_ema200",
        name="RSI + EMA200",
        description="Mean reversion with RSI oversold/overbought + EMA200 trend filter",
        class_path="backend.app.services.strategies.rsi_ema200.RSIEMA200Strategy",
        default_params={
            "rsi_oversold": 30.0,
            "rsi_overbought": 70.0,
            "atr_sl_multiplier": 1.5,
            "atr_tp_multiplier": 2.5
        }
    )
}


def get_strategy_list() -> list:
    """Get list of available strategies for frontend."""
    return [
        {
            "id": info.id,
            "name": info.name,
            "description": info.description,
            "params": info.default_params
        }
        for info in STRATEGIES.values()
    ]


def load_strategy(strategy_id: str, params: Optional[Dict[str, Any]] = None):
    """
    Load a strategy by ID.

    Args:
        strategy_id: Strategy identifier (e.g., 'triple_ema', 'rsi_ema200')
        params: Optional parameters to override defaults

    Returns:
        Strategy instance
    """
    logger.info(f"Loading strategy: {strategy_id}")

    if strategy_id not in STRATEGIES:
        logger.error(f"Unknown strategy: {strategy_id}")
        # Default to RSI + EMA200
        strategy_id = "rsi_ema200"

    info = STRATEGIES[strategy_id]
    logger.info(f"Found strategy info: {info.name}")

    # Merge default params with provided params
    final_params = {**info.default_params}
    if params:
        final_params.update(params)

    try:
        if strategy_id == "hybrid":
            from .hybrid import HybridStrategy
            logger.info("Instantiating HybridStrategy")
            return HybridStrategy(**final_params)

        elif strategy_id == "adaptive":
            from .adaptive import AdaptiveStrategy
            logger.info("Instantiating AdaptiveStrategy")
            return AdaptiveStrategy(**final_params)

        elif strategy_id == "triple_ema":
            from .triple_ema import TripleEMAStrategy
            logger.info("Instantiating TripleEMAStrategy")
            return TripleEMAStrategy(**final_params)

        elif strategy_id == "rsi_ema200":
            from .rsi_ema200 import RSIEMA200Strategy
            logger.info("Instantiating RSIEMA200Strategy")
            return RSIEMA200Strategy(**final_params)

        else:
            logger.warning(f"Strategy {strategy_id} not implemented, using hybrid")
            from .hybrid import HybridStrategy
            return HybridStrategy()

    except Exception as e:
        logger.error(f"Failed to load strategy {strategy_id}: {e}")
        from .hybrid import HybridStrategy
        return HybridStrategy()


def get_default_strategy_id() -> str:
    """Get the default strategy ID from config or return default."""
    try:
        from ...config import Config
        return getattr(Config, 'DEFAULT_STRATEGY', 'rsi_ema200')
    except:
        return 'rsi_ema200'
