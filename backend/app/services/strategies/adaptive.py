"""
Adaptive Strategy
=================
Estrategia que detecta el régimen de mercado y adapta su comportamiento.

Basado en análisis de 5 años (2020-2025):
- TRENDING: Usar MACD + EMA200 (funciona bien)
- RANGING: Reducir tamaño o esperar
- VOLATILE: No operar
- QUIET: Esperar breakout

Resultados backtest:
- EUR_USD: PF 1.53, 100% años rentables
- USD_JPY: PF 1.70, 83% años rentables
- GBP_USD: PF 1.39, 50% años rentables
"""

from dataclasses import dataclass
from typing import Optional
from enum import Enum
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


class MarketRegime(Enum):
    """Regímenes de mercado detectados"""
    TRENDING = "trending"      # ADX > 25, bueno para trend-following
    RANGING = "ranging"        # ADX < 25, ATR bajo
    VOLATILE = "volatile"      # ATR alto, ADX bajo - peligroso
    QUIET = "quiet"            # ATR muy bajo - esperar breakout


@dataclass
class AdaptiveSignal:
    """Señal generada por estrategia adaptativa."""
    direction: str  # "LONG", "SHORT", "WAIT"
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    confidence: float = 0.0
    reason: str = ""

    # Metadata
    regime: Optional[str] = None
    strategy_used: Optional[str] = None
    adx: Optional[float] = None
    atr: Optional[float] = None
    macd: Optional[float] = None
    ema_200: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "direction": self.direction,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "confidence": self.confidence,
            "reason": self.reason,
            "regime": self.regime,
            "strategy_used": self.strategy_used,
            "adx": self.adx,
            "atr": self.atr,
            "macd": self.macd,
            "ema_200": self.ema_200
        }


class AdaptiveStrategy:
    """
    Adaptive Market Regime Strategy.

    Detecta el régimen actual y aplica la estrategia apropiada:
    - TRENDING: MACD crossover + EMA200 filter (trend-following)
    - RANGING: No operar (mean reversion demostró ser perdedora)
    - VOLATILE: No operar (muy arriesgado)
    - QUIET: No operar (esperar)

    Optimizado para consistencia multi-año.
    """

    def __init__(
        self,
        # ADX parameters
        adx_period: int = 14,
        adx_trending_threshold: float = 25.0,

        # ATR parameters
        atr_period: int = 14,
        atr_sl_multiplier: float = 2.0,
        rr_ratio: float = 2.5,

        # MACD parameters
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,

        # EMA trend filter
        ema_period: int = 200,

        # Regime detection
        volatility_lookback: int = 60,
        high_volatility_percentile: float = 70.0,
        low_volatility_percentile: float = 30.0,

        # Trading options
        trade_ranging: bool = False,  # Desactivado por backtest
        trade_quiet: bool = False,
        trade_volatile: bool = False
    ):
        self.adx_period = adx_period
        self.adx_trending_threshold = adx_trending_threshold
        self.atr_period = atr_period
        self.atr_sl_multiplier = atr_sl_multiplier
        self.rr_ratio = rr_ratio
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal
        self.ema_period = ema_period
        self.volatility_lookback = volatility_lookback
        self.high_volatility_percentile = high_volatility_percentile
        self.low_volatility_percentile = low_volatility_percentile
        self.trade_ranging = trade_ranging
        self.trade_quiet = trade_quiet
        self.trade_volatile = trade_volatile

        logger.info(f"AdaptiveStrategy initialized: ADX>{adx_trending_threshold}, "
                   f"ATR SL {atr_sl_multiplier}x, R:R 1:{rr_ratio}")

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcular todos los indicadores necesarios."""
        df = df.copy()

        # EMA 200
        df['ema_200'] = df['close'].ewm(span=self.ema_period, adjust=False).mean()

        # MACD
        ema_fast = df['close'].ewm(span=self.macd_fast, adjust=False).mean()
        ema_slow = df['close'].ewm(span=self.macd_slow, adjust=False).mean()
        df['macd'] = ema_fast - ema_slow
        df['macd_signal'] = df['macd'].ewm(span=self.macd_signal, adjust=False).mean()
        df['macd_histogram'] = df['macd'] - df['macd_signal']

        # MACD Crossovers
        df['macd_cross_up'] = (
            (df['macd'] > df['macd_signal']) &
            (df['macd'].shift(1) <= df['macd_signal'].shift(1))
        )
        df['macd_cross_down'] = (
            (df['macd'] < df['macd_signal']) &
            (df['macd'].shift(1) >= df['macd_signal'].shift(1))
        )

        # ATR
        high_low = df['high'] - df['low']
        high_close = (df['high'] - df['close'].shift(1)).abs()
        low_close = (df['low'] - df['close'].shift(1)).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr'] = tr.rolling(window=self.atr_period).mean()

        # ATR Percentile (para detectar volatilidad)
        df['atr_percentile'] = df['atr'].rolling(self.volatility_lookback).apply(
            lambda x: pd.Series(x).rank(pct=True).iloc[-1] * 100 if len(x) > 0 else 50
        )

        # ADX
        df['adx'] = self._calculate_adx(df)

        return df

    def _calculate_adx(self, df: pd.DataFrame) -> pd.Series:
        """Calcular ADX (Average Directional Index)."""
        high = df['high']
        low = df['low']
        close = df['close']

        plus_dm = high.diff()
        minus_dm = low.diff().abs() * -1

        plus_dm = plus_dm.where(plus_dm > 0, 0)
        minus_dm = minus_dm.where(minus_dm < 0, 0).abs()

        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        atr = tr.rolling(self.adx_period).mean()

        plus_di = 100 * (plus_dm.rolling(self.adx_period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(self.adx_period).mean() / atr)

        # Avoid division by zero
        di_sum = plus_di + minus_di
        di_sum = di_sum.replace(0, np.nan)

        dx = 100 * ((plus_di - minus_di).abs() / di_sum)
        adx = dx.rolling(self.adx_period).mean()

        return adx

    def detect_regime(self, adx: float, atr_percentile: float) -> MarketRegime:
        """
        Detectar régimen de mercado actual.

        Args:
            adx: Current ADX value
            atr_percentile: ATR percentile (0-100)

        Returns:
            MarketRegime enum
        """
        # Alta volatilidad + Sin tendencia = VOLATILE
        if atr_percentile > self.high_volatility_percentile and adx < self.adx_trending_threshold:
            return MarketRegime.VOLATILE

        # Baja volatilidad + Sin tendencia = QUIET
        if atr_percentile < self.low_volatility_percentile and adx < 20:
            return MarketRegime.QUIET

        # ADX alto = TRENDING
        if adx >= self.adx_trending_threshold:
            return MarketRegime.TRENDING

        # Default = RANGING
        return MarketRegime.RANGING

    def generate_signal(self, candles: list[dict]) -> AdaptiveSignal:
        """
        Generar señal de trading basada en régimen actual.

        Args:
            candles: List of OHLCV dictionaries

        Returns:
            AdaptiveSignal with direction and levels
        """
        if len(candles) < self.ema_period + 50:
            logger.warning(f"Insufficient data: {len(candles)} candles, need {self.ema_period + 50}")
            return AdaptiveSignal(
                direction="WAIT",
                reason="Insufficient historical data"
            )

        # Convert to DataFrame
        df = pd.DataFrame(candles)
        if 'time' in df.columns:
            df['time'] = pd.to_datetime(df['time'])

        # Calculate indicators
        df = self.calculate_indicators(df)

        # Get latest values
        latest = df.iloc[-1]
        prev = df.iloc[-2]

        adx = latest['adx']
        atr = latest['atr']
        atr_percentile = latest['atr_percentile']
        macd = latest['macd']
        macd_signal_line = latest['macd_signal']
        ema_200 = latest['ema_200']
        close = latest['close']

        # Detect regime
        if pd.isna(adx) or pd.isna(atr_percentile):
            return AdaptiveSignal(
                direction="WAIT",
                reason="Indicators not ready"
            )

        regime = self.detect_regime(adx, atr_percentile)
        logger.info(f"Detected regime: {regime.value} (ADX={adx:.1f}, ATR%={atr_percentile:.0f})")

        # Base signal
        signal = AdaptiveSignal(
            direction="WAIT",
            regime=regime.value,
            adx=round(adx, 2),
            atr=round(atr, 5),
            macd=round(macd, 5),
            ema_200=round(ema_200, 5)
        )

        # Apply regime-specific strategy
        if regime == MarketRegime.TRENDING:
            return self._trending_strategy(df, signal)

        elif regime == MarketRegime.RANGING and self.trade_ranging:
            return self._ranging_strategy(df, signal)

        elif regime == MarketRegime.QUIET and self.trade_quiet:
            signal.reason = "QUIET regime - waiting for breakout"
            return signal

        elif regime == MarketRegime.VOLATILE and self.trade_volatile:
            signal.reason = "VOLATILE regime - reduced position size recommended"
            return signal

        else:
            signal.reason = f"{regime.value.upper()} regime - no trading"
            return signal

    def _trending_strategy(self, df: pd.DataFrame, signal: AdaptiveSignal) -> AdaptiveSignal:
        """
        Estrategia para mercado TRENDING: MACD crossover + EMA200.

        Esta estrategia demostró ser la más rentable en backtest.
        """
        latest = df.iloc[-1]
        close = latest['close']
        ema_200 = latest['ema_200']
        atr = latest['atr']
        macd = latest['macd']
        macd_cross_up = latest['macd_cross_up']
        macd_cross_down = latest['macd_cross_down']

        signal.strategy_used = "trend_macd"

        # LONG: MACD cross up + price > EMA200 + MACD viene de negativo
        if macd_cross_up and close > ema_200:
            # Extra filter: MACD should be coming from negative territory
            prev_macd = df.iloc[-2]['macd']
            if prev_macd < 0:
                signal.direction = "LONG"
                signal.entry_price = close
                signal.stop_loss = close - (atr * self.atr_sl_multiplier)
                signal.take_profit = close + (atr * self.atr_sl_multiplier * self.rr_ratio)
                signal.confidence = min(0.8, 0.5 + (signal.adx / 100))
                signal.reason = f"TRENDING LONG: MACD cross up, price above EMA200, ADX={signal.adx}"

                logger.info(f"LONG signal: entry={close:.5f}, SL={signal.stop_loss:.5f}, "
                           f"TP={signal.take_profit:.5f}")

        # SHORT: MACD cross down + price < EMA200 + MACD viene de positivo
        elif macd_cross_down and close < ema_200:
            prev_macd = df.iloc[-2]['macd']
            if prev_macd > 0:
                signal.direction = "SHORT"
                signal.entry_price = close
                signal.stop_loss = close + (atr * self.atr_sl_multiplier)
                signal.take_profit = close - (atr * self.atr_sl_multiplier * self.rr_ratio)
                signal.confidence = min(0.8, 0.5 + (signal.adx / 100))
                signal.reason = f"TRENDING SHORT: MACD cross down, price below EMA200, ADX={signal.adx}"

                logger.info(f"SHORT signal: entry={close:.5f}, SL={signal.stop_loss:.5f}, "
                           f"TP={signal.take_profit:.5f}")

        else:
            signal.reason = "TRENDING - waiting for MACD crossover"

        return signal

    def _ranging_strategy(self, df: pd.DataFrame, signal: AdaptiveSignal) -> AdaptiveSignal:
        """
        Estrategia para mercado RANGING.

        NOTA: Esta estrategia está desactivada por defecto porque
        el backtest mostró que pierde dinero (-122 pips en EUR_USD).
        """
        signal.strategy_used = "mean_rev_disabled"
        signal.reason = "RANGING - mean reversion disabled (backtest showed losses)"
        return signal


def create_adaptive_strategy(**params) -> AdaptiveStrategy:
    """Factory function para crear estrategia adaptativa."""
    return AdaptiveStrategy(**params)
