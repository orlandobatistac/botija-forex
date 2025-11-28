"""
Market Regime Detector & Adaptive Strategy
===========================================
Objetivo: Identificar por qué 2024-2025 pierde y crear estrategia adaptativa.

Regímenes de mercado:
1. TRENDING - Movimientos direccionales claros (usar trend-following)
2. RANGING - Mercado lateral sin dirección (usar mean-reversion)
3. VOLATILE - Alta volatilidad, movimientos erráticos (reducir tamaño o no operar)
4. QUIET - Baja volatilidad, consolidación (esperar breakout)
"""

import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Optional
from dataclasses import dataclass
from enum import Enum


class MarketRegime(Enum):
    TRENDING = "trending"
    RANGING = "ranging"
    VOLATILE = "volatile"
    QUIET = "quiet"


@dataclass
class RegimeStats:
    """Estadísticas por régimen"""
    regime: MarketRegime
    days: int
    pct_of_total: float
    avg_daily_range: float
    trend_strength: float


class RegimeDetector:
    """Detecta el régimen de mercado actual"""

    def __init__(
        self,
        adx_period: int = 14,
        atr_period: int = 14,
        bb_period: int = 20,
        lookback: int = 20
    ):
        self.adx_period = adx_period
        self.atr_period = atr_period
        self.bb_period = bb_period
        self.lookback = lookback

    def calculate_adx(self, df: pd.DataFrame) -> pd.Series:
        """Calcular ADX (fuerza de tendencia)"""
        high = df['high']
        low = df['low']
        close = df['close']

        plus_dm = high.diff()
        minus_dm = low.diff().abs() * -1

        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm > 0] = 0
        minus_dm = minus_dm.abs()

        tr1 = high - low
        tr2 = (high - close.shift()).abs()
        tr3 = (low - close.shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        atr = tr.rolling(self.adx_period).mean()

        plus_di = 100 * (plus_dm.rolling(self.adx_period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(self.adx_period).mean() / atr)

        dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di))
        adx = dx.rolling(self.adx_period).mean()

        return adx

    def calculate_volatility_regime(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcular régimen de volatilidad"""
        df = df.copy()

        # ATR y su percentil histórico
        high_low = df['high'] - df['low']
        high_close = (df['high'] - df['close'].shift()).abs()
        low_close = (df['low'] - df['close'].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr'] = tr.rolling(self.atr_period).mean()

        # ATR percentil (rolling 60 días)
        df['atr_percentile'] = df['atr'].rolling(60).apply(
            lambda x: pd.Series(x).rank(pct=True).iloc[-1] * 100
        )

        # ADX
        df['adx'] = self.calculate_adx(df)

        # Bollinger Band Width (volatilidad)
        df['sma'] = df['close'].rolling(self.bb_period).mean()
        df['bb_std'] = df['close'].rolling(self.bb_period).std()
        df['bb_width'] = (df['bb_std'] * 2) / df['sma'] * 100  # % width

        # Precio vs EMA200 (tendencia)
        df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()
        df['dist_from_ema'] = ((df['close'] - df['ema200']) / df['ema200'] * 100).abs()

        # Determinar régimen
        def get_regime(row):
            adx = row['adx']
            atr_pct = row['atr_percentile']

            if pd.isna(adx) or pd.isna(atr_pct):
                return None

            # Alta volatilidad + Sin tendencia = VOLATILE
            if atr_pct > 70 and adx < 25:
                return MarketRegime.VOLATILE

            # Baja volatilidad + Sin tendencia = QUIET
            if atr_pct < 30 and adx < 20:
                return MarketRegime.QUIET

            # Alta tendencia = TRENDING
            if adx >= 25:
                return MarketRegime.TRENDING

            # Default = RANGING
            return MarketRegime.RANGING

        df['regime'] = df.apply(get_regime, axis=1)

        return df

    def analyze_by_year(self, df: pd.DataFrame) -> dict:
        """Analizar regímenes por año"""
        df = self.calculate_volatility_regime(df)
        df['year'] = df['time'].dt.year

        yearly_analysis = {}

        for year in sorted(df['year'].unique()):
            year_df = df[df['year'] == year].dropna(subset=['regime'])

            if len(year_df) == 0:
                continue

            regime_counts = year_df['regime'].value_counts()
            total_days = len(year_df)

            yearly_analysis[year] = {
                'total_days': total_days,
                'avg_adx': round(year_df['adx'].mean(), 1),
                'avg_atr_pct': round(year_df['atr_percentile'].mean(), 1),
                'regimes': {
                    regime.value: {
                        'days': int(regime_counts.get(regime, 0)),
                        'pct': round(regime_counts.get(regime, 0) / total_days * 100, 1)
                    }
                    for regime in MarketRegime
                }
            }

        return yearly_analysis


class AdaptiveStrategy:
    """
    Estrategia Adaptativa

    Cambia el comportamiento según el régimen:
    - TRENDING: Trend-following (MACD + EMA200)
    - RANGING: Mean-reversion (Bollinger Bands)
    - VOLATILE: No operar o SL muy amplio
    - QUIET: Esperar breakout
    """

    def __init__(self):
        self.regime_detector = RegimeDetector()

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Generar señales adaptativas según régimen"""
        df = self.regime_detector.calculate_volatility_regime(df)

        # Indicadores para cada estrategia
        # MACD (trending)
        ema12 = df['close'].ewm(span=12, adjust=False).mean()
        ema26 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = ema12 - ema26
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_cross_up'] = (df['macd'] > df['macd_signal']) & (df['macd'].shift(1) <= df['macd_signal'].shift(1))
        df['macd_cross_down'] = (df['macd'] < df['macd_signal']) & (df['macd'].shift(1) >= df['macd_signal'].shift(1))

        # Bollinger Bands (ranging)
        df['bb_upper'] = df['sma'] + (df['bb_std'] * 2)
        df['bb_lower'] = df['sma'] - (df['bb_std'] * 2)
        df['bb_touch_lower'] = df['low'] <= df['bb_lower']
        df['bb_touch_upper'] = df['high'] >= df['bb_upper']

        # RSI
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))

        # Señales adaptativas
        df['long_signal'] = False
        df['short_signal'] = False
        df['strategy_used'] = None

        for i in range(200, len(df)):
            regime = df.iloc[i]['regime']

            if regime == MarketRegime.TRENDING:
                # Trend following
                if df.iloc[i]['macd_cross_up'] and df.iloc[i]['close'] > df.iloc[i]['ema200']:
                    df.iloc[i, df.columns.get_loc('long_signal')] = True
                    df.iloc[i, df.columns.get_loc('strategy_used')] = 'trend_macd'
                elif df.iloc[i]['macd_cross_down'] and df.iloc[i]['close'] < df.iloc[i]['ema200']:
                    df.iloc[i, df.columns.get_loc('short_signal')] = True
                    df.iloc[i, df.columns.get_loc('strategy_used')] = 'trend_macd'

            elif regime == MarketRegime.RANGING:
                # Mean reversion
                if df.iloc[i]['bb_touch_lower'] and df.iloc[i]['rsi'] < 35:
                    df.iloc[i, df.columns.get_loc('long_signal')] = True
                    df.iloc[i, df.columns.get_loc('strategy_used')] = 'mean_rev_bb'
                elif df.iloc[i]['bb_touch_upper'] and df.iloc[i]['rsi'] > 65:
                    df.iloc[i, df.columns.get_loc('short_signal')] = True
                    df.iloc[i, df.columns.get_loc('strategy_used')] = 'mean_rev_bb'

            elif regime == MarketRegime.QUIET:
                # Breakout (esperar movimiento fuerte)
                if df.iloc[i]['adx'] > 20 and df.iloc[i]['close'] > df.iloc[i]['bb_upper']:
                    df.iloc[i, df.columns.get_loc('long_signal')] = True
                    df.iloc[i, df.columns.get_loc('strategy_used')] = 'breakout'
                elif df.iloc[i]['adx'] > 20 and df.iloc[i]['close'] < df.iloc[i]['bb_lower']:
                    df.iloc[i, df.columns.get_loc('short_signal')] = True
                    df.iloc[i, df.columns.get_loc('strategy_used')] = 'breakout'

            # VOLATILE: No operamos (señales = False por defecto)

        return df

    def backtest(self, df: pd.DataFrame, pair: str = "USD_JPY") -> dict:
        """Backtest de estrategia adaptativa"""
        df = self.generate_signals(df)

        pip_mult = 100 if 'JPY' in pair else 10000
        spread_pips = 1.5 if 'JPY' in pair else 1.0

        trades = []
        position = None

        for i in range(200, len(df)):
            row = df.iloc[i]
            atr = row['atr']

            # Gestionar posición abierta
            if position:
                exit_price = None
                exit_reason = None

                if position['direction'] == 'long':
                    if row['low'] <= position['sl']:
                        exit_price = position['sl']
                        exit_reason = 'stop_loss'
                    elif position['tp'] and row['high'] >= position['tp']:
                        exit_price = position['tp']
                        exit_reason = 'take_profit'
                    elif row['short_signal']:
                        exit_price = row['close']
                        exit_reason = 'signal_reverse'
                else:
                    if row['high'] >= position['sl']:
                        exit_price = position['sl']
                        exit_reason = 'stop_loss'
                    elif position['tp'] and row['low'] <= position['tp']:
                        exit_price = position['tp']
                        exit_reason = 'take_profit'
                    elif row['long_signal']:
                        exit_price = row['close']
                        exit_reason = 'signal_reverse'

                if exit_price:
                    if position['direction'] == 'long':
                        pips = (exit_price - position['entry']) * pip_mult - spread_pips
                    else:
                        pips = (position['entry'] - exit_price) * pip_mult - spread_pips

                    trades.append({
                        'entry_time': position['entry_time'],
                        'exit_time': row['time'],
                        'direction': position['direction'],
                        'strategy': position['strategy'],
                        'regime': position['regime'],
                        'pips': pips,
                        'exit_reason': exit_reason,
                        'year': position['entry_time'].year
                    })
                    position = None
                    continue

            # Nueva entrada
            if position is None:
                regime = row['regime']

                # SL/TP adaptativo según régimen
                if regime == MarketRegime.TRENDING:
                    sl_mult = 2.0
                    rr = 2.5
                elif regime == MarketRegime.RANGING:
                    sl_mult = 1.5
                    rr = 1.5  # Mean reversion tiene menor R:R
                elif regime == MarketRegime.QUIET:
                    sl_mult = 1.0
                    rr = 3.0  # Breakouts buscan movimientos grandes
                else:
                    continue  # VOLATILE - no operar

                if row['long_signal']:
                    entry = row['close']
                    sl = entry - (atr * sl_mult)
                    tp = entry + (atr * sl_mult * rr)

                    position = {
                        'entry': entry,
                        'entry_time': row['time'],
                        'direction': 'long',
                        'sl': sl,
                        'tp': tp,
                        'strategy': row['strategy_used'],
                        'regime': regime.value if regime else 'unknown'
                    }

                elif row['short_signal']:
                    entry = row['close']
                    sl = entry + (atr * sl_mult)
                    tp = entry - (atr * sl_mult * rr)

                    position = {
                        'entry': entry,
                        'entry_time': row['time'],
                        'direction': 'short',
                        'sl': sl,
                        'tp': tp,
                        'strategy': row['strategy_used'],
                        'regime': regime.value if regime else 'unknown'
                    }

        return self._calculate_metrics(trades, pair)

    def _calculate_metrics(self, trades: list, pair: str) -> dict:
        """Calcular métricas"""
        if not trades:
            return {'pair': pair, 'total_trades': 0, 'net_pips': 0, 'profit_factor': 0}

        wins = [t for t in trades if t['pips'] > 0]
        losses = [t for t in trades if t['pips'] <= 0]

        total_wins = sum(t['pips'] for t in wins)
        total_losses = abs(sum(t['pips'] for t in losses))

        # Por año
        yearly = {}
        for t in trades:
            year = t['year']
            if year not in yearly:
                yearly[year] = {'trades': 0, 'pips': 0, 'wins': 0}
            yearly[year]['trades'] += 1
            yearly[year]['pips'] += t['pips']
            if t['pips'] > 0:
                yearly[year]['wins'] += 1

        # Por estrategia
        by_strategy = {}
        for t in trades:
            strat = t['strategy']
            if strat not in by_strategy:
                by_strategy[strat] = {'trades': 0, 'pips': 0, 'wins': 0}
            by_strategy[strat]['trades'] += 1
            by_strategy[strat]['pips'] += t['pips']
            if t['pips'] > 0:
                by_strategy[strat]['wins'] += 1

        # Por régimen
        by_regime = {}
        for t in trades:
            regime = t['regime']
            if regime not in by_regime:
                by_regime[regime] = {'trades': 0, 'pips': 0, 'wins': 0}
            by_regime[regime]['trades'] += 1
            by_regime[regime]['pips'] += t['pips']
            if t['pips'] > 0:
                by_regime[regime]['wins'] += 1

        return {
            'pair': pair,
            'total_trades': len(trades),
            'wins': len(wins),
            'win_rate': round(len(wins) / len(trades) * 100, 1),
            'net_pips': round(sum(t['pips'] for t in trades), 1),
            'profit_factor': round(total_wins / total_losses, 2) if total_losses > 0 else float('inf'),
            'yearly': {y: {'trades': d['trades'], 'pips': round(d['pips'], 1),
                          'win_rate': round(d['wins']/d['trades']*100, 1) if d['trades'] > 0 else 0}
                      for y, d in sorted(yearly.items())},
            'by_strategy': {s: {'trades': d['trades'], 'pips': round(d['pips'], 1)}
                           for s, d in by_strategy.items()},
            'by_regime': {r: {'trades': d['trades'], 'pips': round(d['pips'], 1)}
                         for r, d in by_regime.items()}
        }


def load_data(pair: str, start_year: int = 2020) -> pd.DataFrame:
    """Cargar datos D1"""
    db_path = Path(__file__).parent / "historical_data.db"
    conn = sqlite3.connect(db_path)

    query = """
        SELECT time, open, high, low, close, volume
        FROM candles
        WHERE instrument = ? AND timeframe = 'D' AND time >= ?
        ORDER BY time
    """
    df = pd.read_sql(query, conn, params=(pair, f"{start_year}-01-01"))
    conn.close()

    df['time'] = pd.to_datetime(df['time'])
    return df


def run_regime_analysis():
    """Análisis de regímenes y estrategia adaptativa"""
    print("=" * 80)
    print("🔍 MARKET REGIME ANALYSIS & ADAPTIVE STRATEGY")
    print("=" * 80)

    pairs = ['EUR_USD', 'USD_JPY', 'GBP_USD']
    detector = RegimeDetector()

    # PARTE 1: Análisis de regímenes por año
    print("\n" + "=" * 60)
    print("📊 PARTE 1: ¿QUÉ CAMBIÓ EN 2024-2025?")
    print("=" * 60)

    for pair in pairs:
        df = load_data(pair)
        analysis = detector.analyze_by_year(df)

        print(f"\n📈 {pair}")
        print("-" * 50)
        print(f"{'Year':<6} {'ADX':>6} {'ATR%':>6} | {'Trend':>8} {'Range':>8} {'Volat':>8} {'Quiet':>8}")
        print("-" * 50)

        for year, data in analysis.items():
            regimes = data['regimes']
            print(f"{year:<6} {data['avg_adx']:>6.1f} {data['avg_atr_pct']:>6.1f} | "
                  f"{regimes['trending']['pct']:>7.1f}% "
                  f"{regimes['ranging']['pct']:>7.1f}% "
                  f"{regimes['volatile']['pct']:>7.1f}% "
                  f"{regimes['quiet']['pct']:>7.1f}%")

    # PARTE 2: Backtest de estrategia adaptativa
    print("\n" + "=" * 60)
    print("📊 PARTE 2: ADAPTIVE STRATEGY BACKTEST")
    print("=" * 60)

    adaptive = AdaptiveStrategy()

    for pair in pairs:
        df = load_data(pair)
        result = adaptive.backtest(df, pair)

        print(f"\n📈 {pair}")
        print("-" * 50)

        if result['total_trades'] == 0:
            print("   No trades generated")
            continue

        # Indicador
        pf = result['profit_factor']
        indicator = "🟢" if pf >= 1.5 else "🟡" if pf >= 1.0 else "🔴"

        print(f"   {indicator} Total: {result['total_trades']} trades | "
              f"Win: {result['win_rate']:.1f}% | Net: {result['net_pips']:.1f} pips | PF: {pf:.2f}")

        # Por año
        print(f"\n   📅 Por Año:")
        for year, data in result['yearly'].items():
            year_indicator = "✅" if data['pips'] > 0 else "❌"
            print(f"      {year}: {year_indicator} {data['trades']:2} trades | {data['pips']:>8.1f} pips | Win: {data['win_rate']:.0f}%")

        # Por estrategia
        print(f"\n   🎯 Por Estrategia:")
        for strat, data in result.get('by_strategy', {}).items():
            if strat:
                strat_indicator = "✅" if data['pips'] > 0 else "❌"
                print(f"      {strat:<15}: {strat_indicator} {data['trades']:2} trades | {data['pips']:>8.1f} pips")

        # Por régimen
        print(f"\n   🌡️ Por Régimen:")
        for regime, data in result.get('by_regime', {}).items():
            regime_indicator = "✅" if data['pips'] > 0 else "❌"
            print(f"      {regime:<12}: {regime_indicator} {data['trades']:2} trades | {data['pips']:>8.1f} pips")

    # PARTE 3: Comparación con estrategia NO adaptativa
    print("\n" + "=" * 60)
    print("📊 PARTE 3: COMPARACIÓN ADAPTATIVA vs FIJA")
    print("=" * 60)


if __name__ == "__main__":
    run_regime_analysis()
