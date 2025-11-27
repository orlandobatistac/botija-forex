"""
Triple EMA Strategy
===================
Estrategia de Trend Following basada en 3 EMAs (20, 50, 200).

Reglas:
1. EMA 200 define el bias (BULLISH/BEARISH)
2. Entrada en pullback a EMA 50
3. Confirmación con vela de rechazo (pin bar, engulfing)
4. R:R fijo 1:2

Filtros anti-lateral:
- ADX > 20 (tendencia presente)
- EMA 50 slope (pendiente mínima)
"""

from dataclasses import dataclass
from typing import Optional
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


@dataclass
class TripleEMASignal:
    """Señal generada por la estrategia Triple EMA."""

    direction: str  # "LONG", "SHORT", "WAIT"
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    confidence: float = 0.0
    reason: str = ""

    # Metadata para logging
    ema_20: Optional[float] = None
    ema_50: Optional[float] = None
    ema_200: Optional[float] = None
    adx: Optional[float] = None
    slope: Optional[float] = None

    def to_dict(self) -> dict:
        """Convierte señal a diccionario."""
        return {
            "direction": self.direction,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "confidence": self.confidence,
            "reason": self.reason,
            "ema_20": self.ema_20,
            "ema_50": self.ema_50,
            "ema_200": self.ema_200,
            "adx": self.adx,
            "slope": self.slope
        }


class TripleEMAStrategy:
    """
    Triple EMA Trend Following Strategy.

    Simple, probada, rentable con disciplina.
    Incluye filtros anti-lateral (ADX, slope).
    SL dinámico basado en ATR para adaptarse a volatilidad.
    """

    def __init__(
        self,
        ema_fast: int = 20,
        ema_medium: int = 50,
        ema_slow: int = 200,
        rr_ratio: float = 3.0,  # Aumentado a 1:3 para compensar bajo win rate
        ema50_tolerance_pips: float = 15.0,
        sl_buffer_pips: float = 5.0,  # Solo se usa si use_atr_sl=False
        atr_sl_multiplier: float = 1.5,  # SL = ATR * 1.5
        use_atr_sl: bool = True,  # Usar ATR para SL dinámico
        min_ema_slope: float = 0.0001,
        min_adx: float = 25.0,  # Aumentado de 20 a 25 para filtrar más
        use_adx_filter: bool = True,
        use_slope_filter: bool = True,
        slope_lookback: int = 10,
        atr_period: int = 14
    ):
        """
        Inicializa la estrategia.

        Args:
            ema_fast: Período EMA rápida (default: 20)
            ema_medium: Período EMA media (default: 50)
            ema_slow: Período EMA lenta (default: 200)
            rr_ratio: Ratio Risk:Reward (default: 3.0 = 1:3)
            ema50_tolerance_pips: Distancia máxima a EMA 50 para considerar pullback
            sl_buffer_pips: Buffer adicional para SL (si no usa ATR)
            atr_sl_multiplier: Multiplicador ATR para SL dinámico
            use_atr_sl: Si usar ATR para calcular SL
            min_ema_slope: Pendiente mínima de EMA 50 para confirmar tendencia
            min_adx: ADX mínimo para confirmar tendencia (< 25 = lateral/débil)
            use_adx_filter: Si usar filtro ADX
            use_slope_filter: Si usar filtro de pendiente
            slope_lookback: Períodos para calcular pendiente
            atr_period: Período para calcular ATR
        """
        self.ema_fast = ema_fast
        self.ema_medium = ema_medium
        self.ema_slow = ema_slow
        self.rr_ratio = rr_ratio
        self.ema50_tolerance_pips = ema50_tolerance_pips
        self.sl_buffer_pips = sl_buffer_pips
        self.atr_sl_multiplier = atr_sl_multiplier
        self.use_atr_sl = use_atr_sl
        self.min_ema_slope = min_ema_slope
        self.min_adx = min_adx
        self.use_adx_filter = use_adx_filter
        self.use_slope_filter = use_slope_filter
        self.slope_lookback = slope_lookback
        self.atr_period = atr_period

        logger.info(
            f"TripleEMAStrategy initialized: "
            f"EMA({ema_fast}/{ema_medium}/{ema_slow}), "
            f"R:R 1:{rr_ratio}, ADX>{min_adx}, ATR SL: {use_atr_sl}"
        )

    def calculate_emas(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula las 3 EMAs."""
        df = df.copy()
        df['ema_20'] = df['close'].ewm(span=self.ema_fast, adjust=False).mean()
        df['ema_50'] = df['close'].ewm(span=self.ema_medium, adjust=False).mean()
        df['ema_200'] = df['close'].ewm(span=self.ema_slow, adjust=False).mean()
        return df

    def calculate_atr(self, df: pd.DataFrame) -> float:
        """
        Calcula ATR (Average True Range) para SL dinámico.

        ATR mide volatilidad - SL más amplio en mercados volátiles,
        más ajustado en mercados tranquilos.
        """
        high = df['high']
        low = df['low']
        close = df['close'].shift(1)

        tr1 = high - low
        tr2 = abs(high - close)
        tr3 = abs(low - close)

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(self.atr_period).mean().iloc[-1]

        return atr if not np.isnan(atr) else 0.0

    def calculate_adx(self, df: pd.DataFrame, period: int = 14) -> float:
        """
        Calcula ADX (Average Directional Index).

        ADX < 20: Sin tendencia (lateral)
        ADX 20-25: Tendencia débil
        ADX 25-50: Tendencia fuerte
        ADX > 50: Tendencia muy fuerte
        """
        df = df.copy()

        # True Range
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift())
        low_close = abs(df['low'] - df['close'].shift())

        df['tr'] = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)

        # +DM (Positive Directional Movement)
        df['plus_dm'] = np.where(
            (df['high'] - df['high'].shift()) > (df['low'].shift() - df['low']),
            np.maximum(df['high'] - df['high'].shift(), 0),
            0
        )

        # -DM (Negative Directional Movement)
        df['minus_dm'] = np.where(
            (df['low'].shift() - df['low']) > (df['high'] - df['high'].shift()),
            np.maximum(df['low'].shift() - df['low'], 0),
            0
        )

        # Smoothed averages
        atr = df['tr'].rolling(period).mean()
        plus_di = 100 * (df['plus_dm'].rolling(period).mean() / atr)
        minus_di = 100 * (df['minus_dm'].rolling(period).mean() / atr)

        # DX y ADX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 0.0001)  # Evitar div/0
        adx = dx.rolling(period).mean().iloc[-1]

        return adx if not np.isnan(adx) else 0.0

    def calculate_ema_slope(self, df: pd.DataFrame) -> float:
        """
        Calcula la pendiente de EMA 50.

        Returns:
            Pendiente normalizada (positiva = alcista, negativa = bajista)
        """
        if 'ema_50' not in df.columns or len(df) < self.slope_lookback + 1:
            return 0.0

        ema50_current = df['ema_50'].iloc[-1]
        ema50_prev = df['ema_50'].iloc[-self.slope_lookback]

        if ema50_prev == 0:
            return 0.0

        slope = (ema50_current - ema50_prev) / ema50_prev
        return slope

    def get_trend_bias(self, row: pd.Series) -> str:
        """
        Determina sesgo basado en EMA 200.

        Returns:
            "BULLISH", "BEARISH", o "NEUTRAL"
        """
        price = row['close']
        ema_200 = row['ema_200']

        # Buffer de 0.1% para evitar señales en la zona de EMA 200
        buffer = ema_200 * 0.001

        if price > ema_200 + buffer:
            return "BULLISH"
        elif price < ema_200 - buffer:
            return "BEARISH"
        return "NEUTRAL"

    def is_perfect_order(self, row: pd.Series, direction: str) -> bool:
        """
        Verifica orden perfecto de EMAs.

        LONG:  EMA 20 > EMA 50 > EMA 200
        SHORT: EMA 20 < EMA 50 < EMA 200
        """
        ema_20 = row['ema_20']
        ema_50 = row['ema_50']
        ema_200 = row['ema_200']

        if direction == "LONG":
            return ema_20 > ema_50 > ema_200
        elif direction == "SHORT":
            return ema_20 < ema_50 < ema_200
        return False

    def is_at_ema50_zone(self, row: pd.Series) -> bool:
        """
        Verifica si precio está cerca de EMA 50 (zona de pullback).
        """
        price = row['close']
        ema_50 = row['ema_50']

        # Determinar valor de pip según el par
        pip_value = 0.0001 if price < 10 else 0.01  # Forex vs JPY pairs

        distance = abs(price - ema_50)
        distance_pips = distance / pip_value

        return distance_pips <= self.ema50_tolerance_pips

    def detect_rejection_candle(
        self,
        current: pd.Series,
        previous: pd.Series,
        direction: str
    ) -> tuple[bool, str]:
        """
        Detecta vela de rechazo (pin bar o engulfing).

        Returns:
            (is_rejection, pattern_type)
        """
        body = abs(current['close'] - current['open'])
        upper_wick = current['high'] - max(current['close'], current['open'])
        lower_wick = min(current['close'], current['open']) - current['low']
        total_range = current['high'] - current['low']

        if total_range == 0 or body == 0:
            return False, ""

        if direction == "LONG":
            # Pin bar alcista: mecha inferior larga, cierre en parte superior
            is_pin_bar = (
                lower_wick > body * 2 and
                current['close'] > current['open'] and
                current['close'] > (current['high'] + current['low']) / 2
            )

            # Engulfing alcista
            is_engulfing = (
                current['close'] > current['open'] and  # Vela verde actual
                previous['close'] < previous['open'] and  # Vela roja anterior
                current['close'] > previous['open'] and  # Cierre > apertura anterior
                current['open'] < previous['close']  # Apertura < cierre anterior
            )

            if is_pin_bar:
                return True, "PIN_BAR_BULLISH"
            if is_engulfing:
                return True, "ENGULFING_BULLISH"

        elif direction == "SHORT":
            # Pin bar bajista: mecha superior larga
            is_pin_bar = (
                upper_wick > body * 2 and
                current['close'] < current['open'] and
                current['close'] < (current['high'] + current['low']) / 2
            )

            # Engulfing bajista
            is_engulfing = (
                current['close'] < current['open'] and  # Vela roja actual
                previous['close'] > previous['open'] and  # Vela verde anterior
                current['close'] < previous['open'] and  # Cierre < apertura anterior
                current['open'] > previous['close']  # Apertura > cierre anterior
            )

            if is_pin_bar:
                return True, "PIN_BAR_BEARISH"
            if is_engulfing:
                return True, "ENGULFING_BEARISH"

        return False, ""

    def is_trending(self, df: pd.DataFrame) -> tuple[bool, str, float, float]:
        """
        Verifica si hay tendencia real (no lateral).

        Returns:
            (is_trending, reason, adx_value, slope_value)
        """
        adx = 0.0
        slope = 0.0

        # Filtro ADX
        if self.use_adx_filter:
            adx = self.calculate_adx(df)
            if adx < self.min_adx:
                return False, f"Mercado lateral (ADX: {adx:.1f} < {self.min_adx})", adx, slope

        # Filtro Slope
        if self.use_slope_filter:
            slope = self.calculate_ema_slope(df)
            if abs(slope) < self.min_ema_slope:
                return False, f"EMA 50 plana (slope: {slope:.6f})", adx, slope

        return True, "Tendencia confirmada", adx, slope

    def calculate_levels(
        self,
        current: pd.Series,
        direction: str,
        atr: float = 0.0
    ) -> tuple[float, float, float]:
        """
        Calcula Entry, SL y TP.

        Si use_atr_sl=True, usa ATR para calcular SL dinámico.
        Esto da más espacio al trade en mercados volátiles.

        Returns:
            (entry, stop_loss, take_profit)
        """
        pip_value = 0.0001 if current['close'] < 10 else 0.01
        entry = current['close']

        # Calcular distancia del SL
        if self.use_atr_sl and atr > 0:
            # SL dinámico basado en ATR
            sl_distance = atr * self.atr_sl_multiplier
        else:
            # SL fijo basado en buffer + swing high/low
            buffer = self.sl_buffer_pips * pip_value
            if direction == "LONG":
                sl_distance = entry - (current['low'] - buffer)
            else:
                sl_distance = (current['high'] + buffer) - entry

        if direction == "LONG":
            stop_loss = entry - sl_distance
            take_profit = entry + (sl_distance * self.rr_ratio)
        else:  # SHORT
            stop_loss = entry + sl_distance
            take_profit = entry - (sl_distance * self.rr_ratio)

        return (
            round(entry, 5),
            round(stop_loss, 5),
            round(take_profit, 5)
        )

    def analyze(self, df: pd.DataFrame) -> TripleEMASignal:
        """
        Analiza mercado y genera señal.

        Args:
            df: DataFrame con columnas OHLC (open, high, low, close)
                Mínimo 200+ períodos para EMA 200

        Returns:
            TripleEMASignal con dirección y niveles
        """
        # Validar datos
        required_periods = self.ema_slow + 1
        if len(df) < required_periods:
            return TripleEMASignal(
                direction="WAIT",
                reason=f"Datos insuficientes ({len(df)} < {required_periods})"
            )

        # Verificar columnas requeridas
        required_cols = ['open', 'high', 'low', 'close']
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            return TripleEMASignal(
                direction="WAIT",
                reason=f"Columnas faltantes: {missing}"
            )

        # Calcular EMAs
        df = self.calculate_emas(df)

        current = df.iloc[-1]
        previous = df.iloc[-2]

        # Metadata para logging
        ema_20 = round(current['ema_20'], 5)
        ema_50 = round(current['ema_50'], 5)
        ema_200 = round(current['ema_200'], 5)

        # ═══════════════════════════════════════════════════════════════
        # STEP 0: Verificar tendencia (filtros anti-lateral)
        # ═══════════════════════════════════════════════════════════════
        is_trending, trend_reason, adx, slope = self.is_trending(df)

        if not is_trending:
            return TripleEMASignal(
                direction="WAIT",
                reason=trend_reason,
                ema_20=ema_20,
                ema_50=ema_50,
                ema_200=ema_200,
                adx=round(adx, 1),
                slope=round(slope, 6)
            )

        # ═══════════════════════════════════════════════════════════════
        # STEP 1: Determinar bias (EMA 200)
        # ═══════════════════════════════════════════════════════════════
        bias = self.get_trend_bias(current)

        if bias == "NEUTRAL":
            return TripleEMASignal(
                direction="WAIT",
                reason="Precio en zona de EMA 200 - sin bias claro",
                ema_20=ema_20,
                ema_50=ema_50,
                ema_200=ema_200,
                adx=round(adx, 1),
                slope=round(slope, 6)
            )

        # Dirección potencial
        potential_direction = "LONG" if bias == "BULLISH" else "SHORT"

        # ═══════════════════════════════════════════════════════════════
        # STEP 2: Verificar Perfect Order (bonus de confianza)
        # ═══════════════════════════════════════════════════════════════
        perfect_order = self.is_perfect_order(current, potential_direction)

        # ═══════════════════════════════════════════════════════════════
        # STEP 3: Verificar pullback a EMA 50
        # ═══════════════════════════════════════════════════════════════
        at_ema50 = self.is_at_ema50_zone(current)

        if not at_ema50:
            confidence = 0.3 if perfect_order else 0.1
            return TripleEMASignal(
                direction="WAIT",
                confidence=confidence,
                reason=f"Esperando pullback a EMA 50. Bias: {bias}",
                ema_20=ema_20,
                ema_50=ema_50,
                ema_200=ema_200,
                adx=round(adx, 1),
                slope=round(slope, 6)
            )

        # ═══════════════════════════════════════════════════════════════
        # STEP 4: Detectar vela de rechazo
        # ═══════════════════════════════════════════════════════════════
        has_rejection, pattern = self.detect_rejection_candle(
            current, previous, potential_direction
        )

        if not has_rejection:
            return TripleEMASignal(
                direction="WAIT",
                confidence=0.4,
                reason=f"En EMA 50 pero sin vela de rechazo. Bias: {bias}",
                ema_20=ema_20,
                ema_50=ema_50,
                ema_200=ema_200,
                adx=round(adx, 1),
                slope=round(slope, 6)
            )

        # ═══════════════════════════════════════════════════════════════
        # 🎯 SEÑAL CONFIRMADA
        # ═══════════════════════════════════════════════════════════════

        # Calcular ATR para SL dinámico
        atr = self.calculate_atr(df)

        # Calcular niveles con ATR
        entry, stop_loss, take_profit = self.calculate_levels(
            current, potential_direction, atr
        )

        # Calcular confianza
        confidence = 0.7 if perfect_order else 0.6
        if adx > 30:
            confidence += 0.05  # Bonus por tendencia fuerte

        reason = (
            f"Triple EMA {potential_direction}: "
            f"Pullback + {pattern} en EMA 50"
        )
        if perfect_order:
            reason += " (Perfect Order)"

        logger.info(
            f"Signal: {potential_direction} | "
            f"Entry: {entry} | SL: {stop_loss} | TP: {take_profit} | "
            f"Confidence: {confidence:.0%}"
        )

        return TripleEMASignal(
            direction=potential_direction,
            entry_price=entry,
            stop_loss=stop_loss,
            take_profit=take_profit,
            confidence=confidence,
            reason=reason,
            ema_20=ema_20,
            ema_50=ema_50,
            ema_200=ema_200,
            adx=round(adx, 1),
            slope=round(slope, 6)
        )

    def generate_signal(self, df: pd.DataFrame) -> TripleEMASignal:
        """
        Alias for analyze() - implements StrategyProtocol for backtester.
        """
        return self.analyze(df)
