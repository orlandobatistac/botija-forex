"""
Walk-Forward Analysis - Breakout de Rangos
===========================================
Estrategia diseñada para capturar rupturas de consolidación.

Lógica:
1. Detectar rango (consolidación) - precio oscila entre máx/mín de N períodos
2. Esperar ruptura con volumen/momentum
3. Entrar en dirección de la ruptura
4. SL dentro del rango, TP basado en extensión del rango

Ventajas:
- Funciona MEJOR en consolidación (donde MACD falla)
- Menos señales falsas en tendencias establecidas
- Captura movimientos explosivos post-consolidación
"""

import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path
from dataclasses import dataclass
from itertools import product
import warnings
warnings.filterwarnings('ignore')


@dataclass
class WFResult:
    """Resultado Walk-Forward"""
    train_period: str
    test_period: str
    params: dict
    train_pf: float
    train_trades: int
    test_pf: float
    test_trades: int
    test_pips: float
    test_win_rate: float


class BreakoutOptimizer:
    """Optimizador para estrategia de Breakout de Rangos"""

    PARAM_GRID = {
        'range_period': [20, 30, 50],           # Período para detectar rango
        'breakout_atr_mult': [0.5, 1.0, 1.5],   # ATR multiplicador para confirmar breakout
        'atr_sl_mult': [1.0, 1.5, 2.0],         # SL dentro del rango
        'range_extension': [1.0, 1.5, 2.0],     # TP = extensión del rango
        'adx_max': [25, 30, 40],                # ADX máximo (evitar tendencias fuertes)
        'min_range_atr': [1.0, 1.5, 2.0],       # Rango mínimo en ATRs (evitar rangos muy pequeños)
    }

    def __init__(self, pair: str = "EUR_USD"):
        self.pair = pair
        self.pip_mult = 100 if 'JPY' in pair else 10000
        self.spread = 1.5 if 'JPY' in pair else 1.0

    def _calculate_indicators(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        """Calcular indicadores para breakout"""
        df = df.copy()
        period = params['range_period']

        # Rango de N períodos (Donchian Channel)
        df['range_high'] = df['high'].rolling(period).max()
        df['range_low'] = df['low'].rolling(period).min()
        df['range_size'] = df['range_high'] - df['range_low']
        df['range_mid'] = (df['range_high'] + df['range_low']) / 2

        # ATR para filtros
        high_low = df['high'] - df['low']
        high_close = (df['high'] - df['close'].shift(1)).abs()
        low_close = (df['low'] - df['close'].shift(1)).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr'] = tr.rolling(14).mean()

        # Rango en términos de ATR
        df['range_atr'] = df['range_size'] / df['atr']

        # ADX (para filtrar tendencias fuertes)
        df['adx'] = self._calculate_adx(df)

        # Breakout signals
        breakout_threshold = df['atr'] * params['breakout_atr_mult']

        # Breakout UP: Cierre por encima del máximo del rango + threshold
        df['breakout_up'] = (
            (df['close'] > df['range_high'].shift(1) + breakout_threshold) &
            (df['close'].shift(1) <= df['range_high'].shift(1))
        )

        # Breakout DOWN: Cierre por debajo del mínimo del rango - threshold
        df['breakout_down'] = (
            (df['close'] < df['range_low'].shift(1) - breakout_threshold) &
            (df['close'].shift(1) >= df['range_low'].shift(1))
        )

        # Volumen relativo (si disponible)
        if 'volume' in df.columns:
            df['vol_ma'] = df['volume'].rolling(20).mean()
            df['vol_ratio'] = df['volume'] / df['vol_ma']
        else:
            df['vol_ratio'] = 1.0

        return df

    def _calculate_adx(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calcular ADX"""
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
        atr = tr.rolling(period).mean()

        plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(period).mean() / atr)

        di_sum = plus_di + minus_di
        di_sum = di_sum.replace(0, np.nan)
        dx = 100 * ((plus_di - minus_di).abs() / di_sum)

        return dx.rolling(period).mean()

    def backtest(self, df: pd.DataFrame, params: dict, count_from: int = 0) -> dict:
        """Backtest de estrategia breakout"""
        df = self._calculate_indicators(df, params)

        trades = []
        position = None

        start_idx = max(params['range_period'] + 50, count_from)

        for i in range(start_idx, len(df)):
            row = df.iloc[i]

            # Gestionar posición abierta
            if position:
                exit_price = None

                if position['direction'] == 'long':
                    if row['low'] <= position['sl']:
                        exit_price = position['sl']
                    elif row['high'] >= position['tp']:
                        exit_price = position['tp']
                else:
                    if row['high'] >= position['sl']:
                        exit_price = position['sl']
                    elif row['low'] <= position['tp']:
                        exit_price = position['tp']

                if exit_price:
                    if position['direction'] == 'long':
                        pips = (exit_price - position['entry']) * self.pip_mult - self.spread
                    else:
                        pips = (position['entry'] - exit_price) * self.pip_mult - self.spread

                    if i >= count_from:
                        trades.append({
                            'pips': pips,
                            'direction': position['direction'],
                            'entry_idx': position['entry_idx'],
                            'exit_idx': i
                        })
                    position = None
                    continue

            # Nueva entrada
            if position is None and i >= count_from:
                # Filtros
                if pd.isna(row['adx']) or pd.isna(row['range_atr']):
                    continue

                # ADX debe ser bajo (no en tendencia fuerte)
                if row['adx'] > params['adx_max']:
                    continue

                # Rango debe ser significativo
                if row['range_atr'] < params['min_range_atr']:
                    continue

                atr = row['atr']
                close = row['close']
                range_size = row['range_size']

                # BREAKOUT UP
                if row['breakout_up']:
                    entry = close
                    # SL dentro del rango
                    sl = row['range_mid'] - (atr * params['atr_sl_mult'] * 0.5)
                    # TP = extensión del rango hacia arriba
                    tp = entry + (range_size * params['range_extension'])

                    position = {
                        'entry': entry,
                        'direction': 'long',
                        'sl': sl,
                        'tp': tp,
                        'entry_idx': i
                    }

                # BREAKOUT DOWN
                elif row['breakout_down']:
                    entry = close
                    sl = row['range_mid'] + (atr * params['atr_sl_mult'] * 0.5)
                    tp = entry - (range_size * params['range_extension'])

                    position = {
                        'entry': entry,
                        'direction': 'short',
                        'sl': sl,
                        'tp': tp,
                        'entry_idx': i
                    }

        if not trades:
            return {'pf': 0, 'trades': 0, 'pips': 0, 'win_rate': 0}

        wins = [t for t in trades if t['pips'] > 0]
        losses = [t for t in trades if t['pips'] <= 0]

        total_wins = sum(t['pips'] for t in wins) if wins else 0
        total_losses = abs(sum(t['pips'] for t in losses)) if losses else 0.001

        return {
            'pf': total_wins / total_losses,
            'trades': len(trades),
            'pips': sum(t['pips'] for t in trades),
            'win_rate': len(wins) / len(trades) * 100 if trades else 0,
            'avg_win': total_wins / len(wins) if wins else 0,
            'avg_loss': total_losses / len(losses) if losses else 0
        }

    def optimize(self, df: pd.DataFrame, min_trades: int = 15) -> tuple:
        """Grid search"""
        best_pf = 0
        best_params = None
        best_metrics = None

        param_names = list(self.PARAM_GRID.keys())
        param_values = list(self.PARAM_GRID.values())

        for values in product(*param_values):
            params = dict(zip(param_names, values))
            metrics = self.backtest(df, params)

            if metrics['trades'] >= min_trades and metrics['pf'] > best_pf:
                best_pf = metrics['pf']
                best_params = params
                best_metrics = metrics

        return best_params, best_metrics


class WalkForwardBreakout:
    """Walk-Forward para estrategia Breakout"""

    def __init__(
        self,
        train_months: int = 18,
        test_months: int = 6,
        pair: str = "EUR_USD"
    ):
        self.train_months = train_months
        self.test_months = test_months
        self.pair = pair
        self.optimizer = BreakoutOptimizer(pair)

    def load_data(self) -> pd.DataFrame:
        """Cargar datos H4"""
        db_path = Path(__file__).parent / "historical_data.db"
        conn = sqlite3.connect(db_path)

        try:
            df = pd.read_sql(
                f"SELECT time, open, high, low, close, volume FROM {self.pair}_H4 ORDER BY time",
                conn
            )
        except:
            df = pd.read_sql(
                f"SELECT time, open, high, low, close, volume FROM candles "
                f"WHERE instrument='{self.pair}' AND timeframe='H4' ORDER BY time",
                conn
            )

        conn.close()
        df['time'] = pd.to_datetime(df['time'])
        return df

    def run(self) -> list:
        """Ejecutar Walk-Forward"""
        print("=" * 75)
        print(f"🔄 WALK-FORWARD BREAKOUT STRATEGY - {self.pair}")
        print("=" * 75)
        print(f"   Estrategia: Ruptura de Rangos (Donchian Breakout)")
        print(f"   Train: {self.train_months} meses | Test: {self.test_months} meses")
        print()

        df = self.load_data()
        print(f"   📊 Data: {len(df)} candles H4")
        print(f"   📅 Período: {df['time'].min().date()} → {df['time'].max().date()}")
        print()

        df['month'] = df['time'].dt.to_period('M')
        months = df['month'].unique()

        results = []
        window_size = self.train_months + self.test_months
        step = self.test_months

        i = 0
        window_num = 0

        while i + window_size <= len(months):
            window_num += 1
            train_months_list = months[i:i + self.train_months]
            test_months_list = months[i + self.train_months:i + window_size]

            train_start = train_months_list[0]
            train_end = train_months_list[-1]
            test_start = test_months_list[0]
            test_end = test_months_list[-1]

            print(f"{'='*65}")
            print(f"📊 Ventana {window_num}: Train {train_start}→{train_end} | Test {test_start}→{test_end}")
            print(f"{'='*65}")

            train_df = df[df['month'].isin(train_months_list)].copy()
            full_df = df[df['month'] <= test_end].copy()
            test_start_idx = len(df[df['month'] < test_start])

            print(f"   Train: {len(train_df)} candles | Test start: idx {test_start_idx}")

            print(f"   🔧 Optimizando breakout params...")
            best_params, train_metrics = self.optimizer.optimize(train_df, min_trades=12)

            if best_params is None:
                print(f"   ❌ No params válidos (min 12 trades)")
                i += step
                continue

            print(f"   ✅ Range:{best_params['range_period']}, "
                  f"BO_ATR:{best_params['breakout_atr_mult']}, "
                  f"SL:{best_params['atr_sl_mult']}, "
                  f"Ext:{best_params['range_extension']}, "
                  f"ADX<{best_params['adx_max']}")
            print(f"   📈 Train: PF={train_metrics['pf']:.2f}, "
                  f"Trades={train_metrics['trades']}, Win={train_metrics['win_rate']:.0f}%")

            test_metrics = self.optimizer.backtest(full_df, best_params, count_from=test_start_idx)

            indicator = "🟢" if test_metrics['pf'] >= 1.5 else "🟡" if test_metrics['pf'] >= 1.0 else "🔴"
            status = "PASS" if test_metrics['pf'] >= 1.0 else "FAIL"

            print(f"   {indicator} Test: PF={test_metrics['pf']:.2f}, "
                  f"Trades={test_metrics['trades']}, Pips={test_metrics['pips']:.1f}, "
                  f"Win={test_metrics['win_rate']:.0f}% [{status}]")

            result = WFResult(
                train_period=f"{train_start}-{train_end}",
                test_period=f"{test_start}-{test_end}",
                params=best_params,
                train_pf=train_metrics['pf'],
                train_trades=train_metrics['trades'],
                test_pf=test_metrics['pf'],
                test_trades=test_metrics['trades'],
                test_pips=test_metrics['pips'],
                test_win_rate=test_metrics['win_rate']
            )
            results.append(result)

            i += step
            print()

        return results

    def print_summary(self, results: list):
        """Resumen"""
        print("=" * 75)
        print("📊 RESUMEN WALK-FORWARD - BREAKOUT STRATEGY")
        print("=" * 75)

        if not results:
            print("   ❌ No results")
            return

        print(f"\n{'Test Period':<22} {'Tr.PF':>7} {'Te.PF':>7} {'Trades':>7} {'Pips':>10} {'Win%':>6} {'St':>5}")
        print("-" * 75)

        total_pips = 0
        total_trades = 0
        profitable = 0

        for r in results:
            status = "✅" if r.test_pf >= 1.0 else "❌"
            if r.test_pf >= 1.0:
                profitable += 1
            total_pips += r.test_pips
            total_trades += r.test_trades

            print(f"{r.test_period:<22} {r.train_pf:>7.2f} {r.test_pf:>7.2f} "
                  f"{r.test_trades:>7} {r.test_pips:>10.1f} {r.test_win_rate:>5.0f}% {status:>5}")

        print("-" * 75)
        avg_pf = np.mean([r.test_pf for r in results])
        consistency = profitable / len(results) * 100

        print(f"{'TOTAL':<22} {'':<7} {avg_pf:>7.2f} {total_trades:>7} {total_pips:>10.1f}")

        print(f"\n🎯 Métricas Finales:")
        print(f"   Ventanas: {len(results)} | Rentables: {profitable} | Consistencia: {consistency:.0f}%")
        print(f"   Avg Test PF: {avg_pf:.2f} | Total Pips: {total_pips:.1f} | Trades: {total_trades}")

        # Comparación con MACD
        print(f"\n📊 Comparación con MACD+EMA200:")
        print(f"   MACD H4 EUR_USD: 57% consistencia, +29 pips")
        print(f"   Breakout H4 {self.pair}: {consistency:.0f}% consistencia, {total_pips:+.1f} pips")

        print(f"\n{'='*75}")
        if consistency >= 75 and avg_pf >= 1.3:
            print("🏆 ESTRATEGIA ROBUSTA - Breakout supera MACD")
        elif consistency >= 60 and avg_pf >= 1.0:
            print("🟡 ESTRATEGIA ACEPTABLE - Similar o mejor que MACD")
        else:
            print("🔴 ESTRATEGIA DÉBIL - Breakout no mejora MACD")
        print("=" * 75)

        # Análisis de parámetros
        print(f"\n📋 Parámetros Óptimos por Ventana:")
        for r in results:
            p = r.params
            print(f"   {r.test_period}: Range={p['range_period']}, "
                  f"ADX<{p['adx_max']}, Ext={p['range_extension']}")


def run_breakout_walkforward():
    """Ejecutar Walk-Forward Breakout"""
    pairs = ['EUR_USD', 'USD_JPY']

    for pair in pairs:
        try:
            wf = WalkForwardBreakout(
                train_months=18,
                test_months=6,
                pair=pair
            )
            results = wf.run()
            wf.print_summary(results)
            print("\n" + "="*75 + "\n")
        except Exception as e:
            print(f"❌ Error {pair}: {e}")
            import traceback
            traceback.print_exc()
            print()


if __name__ == "__main__":
    run_breakout_walkforward()
