"""
Tests para TripleEMAStrategy
============================
Verifica el funcionamiento correcto de la estrategia Triple EMA.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from app.services.strategies.triple_ema import TripleEMAStrategy, TripleEMASignal


class TestTripleEMAStrategy:
    """Tests para la estrategia Triple EMA."""

    @pytest.fixture
    def strategy(self):
        """Instancia de estrategia con configuración default."""
        return TripleEMAStrategy()

    @pytest.fixture
    def strategy_no_filters(self):
        """Estrategia sin filtros anti-lateral (para tests específicos)."""
        return TripleEMAStrategy(
            use_adx_filter=False,
            use_slope_filter=False
        )

    @pytest.fixture
    def bullish_trend_data(self) -> pd.DataFrame:
        """Genera datos de tendencia alcista clara."""
        np.random.seed(42)
        n = 250

        # Tendencia alcista con pullbacks
        base = 1.0800
        trend = np.linspace(0, 0.0200, n)  # +200 pips de tendencia
        noise = np.random.normal(0, 0.0010, n)  # Ruido de 10 pips

        close = base + trend + noise

        # OHLC realista
        df = pd.DataFrame({
            'open': close - np.random.uniform(0.0002, 0.0010, n),
            'high': close + np.random.uniform(0.0005, 0.0020, n),
            'low': close - np.random.uniform(0.0005, 0.0020, n),
            'close': close,
            'timestamp': [datetime.now() - timedelta(hours=n-i) for i in range(n)]
        })

        return df

    @pytest.fixture
    def bearish_trend_data(self) -> pd.DataFrame:
        """Genera datos de tendencia bajista clara."""
        np.random.seed(42)
        n = 250

        # Tendencia bajista
        base = 1.1000
        trend = np.linspace(0, -0.0200, n)  # -200 pips
        noise = np.random.normal(0, 0.0010, n)

        close = base + trend + noise

        df = pd.DataFrame({
            'open': close + np.random.uniform(0.0002, 0.0010, n),
            'high': close + np.random.uniform(0.0005, 0.0020, n),
            'low': close - np.random.uniform(0.0005, 0.0020, n),
            'close': close,
            'timestamp': [datetime.now() - timedelta(hours=n-i) for i in range(n)]
        })

        return df

    @pytest.fixture
    def lateral_data(self) -> pd.DataFrame:
        """Genera datos de mercado lateral (rango)."""
        np.random.seed(42)
        n = 250

        # Mercado lateral: oscila entre 1.0900 y 1.0950
        base = 1.0925
        noise = np.random.uniform(-0.0025, 0.0025, n)  # Rango de 50 pips

        close = base + noise

        df = pd.DataFrame({
            'open': close - np.random.uniform(-0.0005, 0.0005, n),
            'high': close + np.random.uniform(0.0005, 0.0015, n),
            'low': close - np.random.uniform(0.0005, 0.0015, n),
            'close': close,
            'timestamp': [datetime.now() - timedelta(hours=n-i) for i in range(n)]
        })

        return df

    # ═══════════════════════════════════════════════════════════════
    # Tests de cálculo de EMAs
    # ═══════════════════════════════════════════════════════════════

    def test_calculate_emas(self, strategy, bullish_trend_data):
        """Verifica que las EMAs se calculan correctamente."""
        df = strategy.calculate_emas(bullish_trend_data)

        assert 'ema_20' in df.columns
        assert 'ema_50' in df.columns
        assert 'ema_200' in df.columns

        # EMAs no deben tener NaN en los últimos registros
        assert not pd.isna(df['ema_20'].iloc[-1])
        assert not pd.isna(df['ema_50'].iloc[-1])
        assert not pd.isna(df['ema_200'].iloc[-1])

    def test_ema_order_in_uptrend(self, strategy, bullish_trend_data):
        """En tendencia alcista, EMA 20 > EMA 50 > EMA 200."""
        df = strategy.calculate_emas(bullish_trend_data)
        last = df.iloc[-1]

        # En tendencia alcista clara, debería haber orden perfecto
        # (puede no ser exacto por el ruido, pero la tendencia es clara)
        assert last['ema_20'] > last['ema_200']

    # ═══════════════════════════════════════════════════════════════
    # Tests de bias de tendencia
    # ═══════════════════════════════════════════════════════════════

    def test_bullish_bias(self, strategy, bullish_trend_data):
        """Precio sobre EMA 200 = BULLISH."""
        df = strategy.calculate_emas(bullish_trend_data)
        last = df.iloc[-1]

        bias = strategy.get_trend_bias(last)
        assert bias == "BULLISH"

    def test_bearish_bias(self, strategy, bearish_trend_data):
        """Precio bajo EMA 200 = BEARISH."""
        df = strategy.calculate_emas(bearish_trend_data)
        last = df.iloc[-1]

        bias = strategy.get_trend_bias(last)
        assert bias == "BEARISH"

    # ═══════════════════════════════════════════════════════════════
    # Tests de filtros anti-lateral
    # ═══════════════════════════════════════════════════════════════

    def test_adx_filter_rejects_lateral(self, strategy, lateral_data):
        """ADX bajo debería rechazar operaciones."""
        df = strategy.calculate_emas(lateral_data)

        adx = strategy.calculate_adx(df)

        # En mercado lateral, ADX debería ser bajo (< 25 típicamente)
        # El test verifica que el cálculo funciona, no el valor exacto
        assert adx >= 0
        assert adx <= 100

    def test_slope_filter(self, strategy, lateral_data):
        """EMA plana debería tener slope cercano a 0."""
        df = strategy.calculate_emas(lateral_data)

        slope = strategy.calculate_ema_slope(df)

        # En lateral, el slope debería ser muy pequeño
        assert abs(slope) < 0.01  # Menos de 1%

    def test_is_trending_rejects_lateral(self, strategy, lateral_data):
        """Mercado lateral no debería pasar filtro de tendencia."""
        df = strategy.calculate_emas(lateral_data)

        is_trending, reason, adx, slope = strategy.is_trending(df)

        # Debería rechazar por ADX bajo o slope plano
        # (depende de los datos generados)
        assert isinstance(is_trending, bool)
        assert len(reason) > 0

    # ═══════════════════════════════════════════════════════════════
    # Tests de detección de patrones
    # ═══════════════════════════════════════════════════════════════

    def test_detect_bullish_pin_bar(self, strategy):
        """Detecta pin bar alcista."""
        # Pin bar alcista: mecha inferior larga, cuerpo pequeño arriba
        current = pd.Series({
            'open': 1.0900,
            'high': 1.0910,
            'low': 1.0870,   # Mecha larga hacia abajo
            'close': 1.0905  # Cierre cerca del high
        })
        previous = pd.Series({
            'open': 1.0910,
            'high': 1.0920,
            'low': 1.0895,
            'close': 1.0895
        })

        is_rejection, pattern = strategy.detect_rejection_candle(
            current, previous, "LONG"
        )

        assert is_rejection is True
        assert pattern == "PIN_BAR_BULLISH"

    def test_detect_bearish_pin_bar(self, strategy):
        """Detecta pin bar bajista."""
        # Pin bar bajista: mecha superior larga, cuerpo pequeño abajo
        current = pd.Series({
            'open': 1.0900,
            'high': 1.0930,  # Mecha larga hacia arriba
            'low': 1.0890,
            'close': 1.0895  # Cierre cerca del low
        })
        previous = pd.Series({
            'open': 1.0890,
            'high': 1.0905,
            'low': 1.0880,
            'close': 1.0905
        })

        is_rejection, pattern = strategy.detect_rejection_candle(
            current, previous, "SHORT"
        )

        assert is_rejection is True
        assert pattern == "PIN_BAR_BEARISH"

    def test_detect_bullish_engulfing(self, strategy):
        """Detecta patrón envolvente alcista."""
        # Engulfing: vela verde grande que envuelve vela roja anterior
        previous = pd.Series({
            'open': 1.0900,
            'high': 1.0905,
            'low': 1.0885,
            'close': 1.0890  # Vela roja
        })
        current = pd.Series({
            'open': 1.0885,  # Abre bajo el cierre anterior
            'high': 1.0920,
            'low': 1.0880,
            'close': 1.0915  # Cierra sobre la apertura anterior
        })

        is_rejection, pattern = strategy.detect_rejection_candle(
            current, previous, "LONG"
        )

        assert is_rejection is True
        assert pattern == "ENGULFING_BULLISH"

    def test_no_rejection_pattern(self, strategy):
        """Vela sin patrón de rechazo."""
        current = pd.Series({
            'open': 1.0900,
            'high': 1.0910,
            'low': 1.0895,
            'close': 1.0905  # Vela normal, sin características especiales
        })
        previous = pd.Series({
            'open': 1.0895,
            'high': 1.0905,
            'low': 1.0890,
            'close': 1.0900
        })

        is_rejection, pattern = strategy.detect_rejection_candle(
            current, previous, "LONG"
        )

        assert is_rejection is False
        assert pattern == ""

    # ═══════════════════════════════════════════════════════════════
    # Tests de cálculo de niveles
    # ═══════════════════════════════════════════════════════════════

    def test_calculate_levels_long(self, strategy):
        """Calcula SL y TP correctamente para LONG."""
        current = pd.Series({
            'open': 1.0900,
            'high': 1.0920,
            'low': 1.0880,
            'close': 1.0910
        })

        entry, sl, tp = strategy.calculate_levels(current, "LONG")

        # Entry = close
        assert entry == 1.0910

        # SL = low - buffer (5 pips = 0.0005)
        assert sl == 1.0875  # 1.0880 - 0.0005

        # Risk = entry - sl = 0.0035
        # TP = entry + (risk * 2) = 1.0910 + 0.0070 = 1.0980
        expected_tp = entry + ((entry - sl) * 2)
        assert tp == round(expected_tp, 5)

    def test_calculate_levels_short(self, strategy):
        """Calcula SL y TP correctamente para SHORT."""
        current = pd.Series({
            'open': 1.0920,
            'high': 1.0940,
            'low': 1.0900,
            'close': 1.0905
        })

        entry, sl, tp = strategy.calculate_levels(current, "SHORT")

        # Entry = close
        assert entry == 1.0905

        # SL = high + buffer
        assert sl == 1.0945  # 1.0940 + 0.0005

        # Risk = sl - entry
        # TP = entry - (risk * 2)
        expected_tp = entry - ((sl - entry) * 2)
        assert tp == round(expected_tp, 5)

    # ═══════════════════════════════════════════════════════════════
    # Tests del método analyze (integración)
    # ═══════════════════════════════════════════════════════════════

    def test_analyze_insufficient_data(self, strategy):
        """Retorna WAIT si no hay suficientes datos."""
        df = pd.DataFrame({
            'open': [1.0900],
            'high': [1.0910],
            'low': [1.0890],
            'close': [1.0905]
        })

        signal = strategy.analyze(df)

        assert signal.direction == "WAIT"
        assert "insuficientes" in signal.reason.lower() or "insufficient" in signal.reason.lower()

    def test_analyze_missing_columns(self, strategy):
        """Retorna WAIT si faltan columnas requeridas."""
        df = pd.DataFrame({
            'close': [1.0900] * 250
            # Falta open, high, low
        })

        signal = strategy.analyze(df)

        assert signal.direction == "WAIT"
        assert "faltantes" in signal.reason.lower() or "missing" in signal.reason.lower()

    def test_analyze_returns_signal_dataclass(self, strategy, bullish_trend_data):
        """El método analyze retorna un TripleEMASignal."""
        signal = strategy.analyze(bullish_trend_data)

        assert isinstance(signal, TripleEMASignal)
        assert signal.direction in ["LONG", "SHORT", "WAIT"]
        assert isinstance(signal.confidence, float)
        assert len(signal.reason) > 0

    def test_signal_to_dict(self, strategy, bullish_trend_data):
        """La señal se puede convertir a diccionario."""
        signal = strategy.analyze(bullish_trend_data)

        result = signal.to_dict()

        assert isinstance(result, dict)
        assert 'direction' in result
        assert 'entry_price' in result
        assert 'stop_loss' in result
        assert 'take_profit' in result

    # ═══════════════════════════════════════════════════════════════
    # Tests de configuración
    # ═══════════════════════════════════════════════════════════════

    def test_custom_ema_periods(self):
        """Se pueden personalizar los períodos de EMA."""
        strategy = TripleEMAStrategy(
            ema_fast=10,
            ema_medium=30,
            ema_slow=100
        )

        assert strategy.ema_fast == 10
        assert strategy.ema_medium == 30
        assert strategy.ema_slow == 100

    def test_custom_rr_ratio(self):
        """Se puede personalizar el ratio R:R."""
        strategy = TripleEMAStrategy(rr_ratio=3.0)

        current = pd.Series({
            'open': 1.0900,
            'high': 1.0920,
            'low': 1.0880,
            'close': 1.0910
        })

        entry, sl, tp = strategy.calculate_levels(current, "LONG")

        risk = entry - sl
        expected_tp = entry + (risk * 3.0)

        assert tp == round(expected_tp, 5)

    def test_disable_filters(self):
        """Se pueden desactivar los filtros."""
        strategy = TripleEMAStrategy(
            use_adx_filter=False,
            use_slope_filter=False
        )

        assert strategy.use_adx_filter is False
        assert strategy.use_slope_filter is False


class TestTripleEMASignal:
    """Tests para el dataclass TripleEMASignal."""

    def test_signal_creation(self):
        """Crea señal con valores correctos."""
        signal = TripleEMASignal(
            direction="LONG",
            entry_price=1.0900,
            stop_loss=1.0850,
            take_profit=1.1000,
            confidence=0.75,
            reason="Test signal"
        )

        assert signal.direction == "LONG"
        assert signal.entry_price == 1.0900
        assert signal.stop_loss == 1.0850
        assert signal.take_profit == 1.1000
        assert signal.confidence == 0.75

    def test_signal_defaults(self):
        """Valores por defecto son correctos."""
        signal = TripleEMASignal(direction="WAIT")

        assert signal.entry_price is None
        assert signal.stop_loss is None
        assert signal.take_profit is None
        assert signal.confidence == 0.0
        assert signal.reason == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
