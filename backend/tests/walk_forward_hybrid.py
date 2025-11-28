"""
Walk-Forward Analysis - Sistema Híbrido (Breakout + MACD)
=========================================================
Combina dos estrategias complementarias según régimen de mercado:

- ADX < 25 (Consolidación) → Estrategia BREAKOUT
- ADX >= 25 (Tendencia)    → Estrategia MACD + EMA200

Objetivo: Capturar ganancias en TODOS los regímenes de mercado.
"""

import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path
from dataclasses import dataclass
from itertools import product
from joblib import Parallel, delayed
import multiprocessing
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
    breakout_trades: int = 0
    macd_trades: int = 0


class HybridOptimizer:
    """
    Optimizador para Sistema Híbrido Breakout + MACD

    Switch: ADX threshold determina qué estrategia usar
    - ADX < threshold → Breakout (mercado lateral)
    - ADX >= threshold → MACD + EMA200 (mercado tendencial)
    """

    PARAM_GRID = {
        # Switch ADX
        'adx_switch': [20, 25, 30],  # Umbral para cambiar entre estrategias

        # Parámetros BREAKOUT (cuando ADX < switch)
        'bo_range_period': [20, 30],
        'bo_atr_mult': [0.5, 1.0],
        'bo_sl_mult': [1.0, 1.5],
        'bo_extension': [1.5, 2.0],

        # Parámetros MACD (cuando ADX >= switch)
        'macd_fast': [8, 12],
        'macd_slow': [21, 26],
        'macd_sl_mult': [1.5, 2.0],
        'macd_rr': [2.0, 2.5],
    }

    def __init__(self, pair: str = "EUR_USD"):
        self.pair = pair
        self.pip_mult = 100 if 'JPY' in pair else 10000
        self.spread = 1.5 if 'JPY' in pair else 1.0

    def _calculate_indicators(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        """Calcular todos los indicadores necesarios"""
        df = df.copy()

        # === INDICADORES COMUNES ===
        # ATR
        high_low = df['high'] - df['low']
        high_close = (df['high'] - df['close'].shift(1)).abs()
        low_close = (df['low'] - df['close'].shift(1)).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr'] = tr.rolling(14).mean()

        # ADX (para el switch)
        df['adx'] = self._calculate_adx(df)

        # === INDICADORES BREAKOUT ===
        period = params['bo_range_period']
        df['range_high'] = df['high'].rolling(period).max()
        df['range_low'] = df['low'].rolling(period).min()
        df['range_size'] = df['range_high'] - df['range_low']
        df['range_mid'] = (df['range_high'] + df['range_low']) / 2

        # Breakout signals
        bo_threshold = df['atr'] * params['bo_atr_mult']
        df['breakout_up'] = (
            (df['close'] > df['range_high'].shift(1) + bo_threshold) &
            (df['close'].shift(1) <= df['range_high'].shift(1))
        )
        df['breakout_down'] = (
            (df['close'] < df['range_low'].shift(1) - bo_threshold) &
            (df['close'].shift(1) >= df['range_low'].shift(1))
        )

        # === INDICADORES MACD ===
        df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
        ema_fast = df['close'].ewm(span=params['macd_fast'], adjust=False).mean()
        ema_slow = df['close'].ewm(span=params['macd_slow'], adjust=False).mean()
        df['macd'] = ema_fast - ema_slow
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()

        df['macd_cross_up'] = (
            (df['macd'] > df['macd_signal']) &
            (df['macd'].shift(1) <= df['macd_signal'].shift(1))
        )
        df['macd_cross_down'] = (
            (df['macd'] < df['macd_signal']) &
            (df['macd'].shift(1) >= df['macd_signal'].shift(1))
        )

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
        """
        Backtest del sistema híbrido.

        Lógica:
        1. Calcular ADX actual
        2. Si ADX < switch → Buscar señales Breakout
        3. Si ADX >= switch → Buscar señales MACD
        """
        df = self._calculate_indicators(df, params)

        trades = []
        position = None
        breakout_count = 0
        macd_count = 0

        start_idx = max(200, params['bo_range_period'] + 50, count_from)

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
                            'strategy': position['strategy']
                        })
                    position = None
                    continue

            # Nueva entrada (solo después de count_from)
            if position is None and i >= count_from:
                if pd.isna(row['adx']):
                    continue

                adx = row['adx']
                atr = row['atr']
                close = row['close']

                # === SWITCH: Seleccionar estrategia según ADX ===
                if adx < params['adx_switch']:
                    # BREAKOUT STRATEGY (consolidación)
                    if row['breakout_up']:
                        entry = close
                        sl = row['range_mid'] - (atr * params['bo_sl_mult'] * 0.5)
                        tp = entry + (row['range_size'] * params['bo_extension'])

                        position = {
                            'entry': entry,
                            'direction': 'long',
                            'sl': sl,
                            'tp': tp,
                            'strategy': 'breakout'
                        }
                        breakout_count += 1

                    elif row['breakout_down']:
                        entry = close
                        sl = row['range_mid'] + (atr * params['bo_sl_mult'] * 0.5)
                        tp = entry - (row['range_size'] * params['bo_extension'])

                        position = {
                            'entry': entry,
                            'direction': 'short',
                            'sl': sl,
                            'tp': tp,
                            'strategy': 'breakout'
                        }
                        breakout_count += 1

                else:
                    # MACD STRATEGY (tendencia)
                    if row['macd_cross_up'] and close > row['ema_200']:
                        prev_macd = df.iloc[i-1]['macd']
                        if prev_macd < 0:
                            entry = close
                            sl = entry - (atr * params['macd_sl_mult'])
                            tp = entry + (atr * params['macd_sl_mult'] * params['macd_rr'])

                            position = {
                                'entry': entry,
                                'direction': 'long',
                                'sl': sl,
                                'tp': tp,
                                'strategy': 'macd'
                            }
                            macd_count += 1

                    elif row['macd_cross_down'] and close < row['ema_200']:
                        prev_macd = df.iloc[i-1]['macd']
                        if prev_macd > 0:
                            entry = close
                            sl = entry + (atr * params['macd_sl_mult'])
                            tp = entry - (atr * params['macd_sl_mult'] * params['macd_rr'])

                            position = {
                                'entry': entry,
                                'direction': 'short',
                                'sl': sl,
                                'tp': tp,
                                'strategy': 'macd'
                            }
                            macd_count += 1

        if not trades:
            return {
                'pf': 0, 'trades': 0, 'pips': 0, 'win_rate': 0,
                'breakout_trades': 0, 'macd_trades': 0
            }

        wins = [t for t in trades if t['pips'] > 0]
        losses = [t for t in trades if t['pips'] <= 0]

        total_wins = sum(t['pips'] for t in wins) if wins else 0
        total_losses = abs(sum(t['pips'] for t in losses)) if losses else 0.001

        # Desglose por estrategia
        bo_trades = [t for t in trades if t['strategy'] == 'breakout']
        macd_trades = [t for t in trades if t['strategy'] == 'macd']

        return {
            'pf': total_wins / total_losses,
            'trades': len(trades),
            'pips': sum(t['pips'] for t in trades),
            'win_rate': len(wins) / len(trades) * 100 if trades else 0,
            'breakout_trades': len(bo_trades),
            'macd_trades': len(macd_trades),
            'breakout_pips': sum(t['pips'] for t in bo_trades),
            'macd_pips': sum(t['pips'] for t in macd_trades)
        }

    def _evaluate_params(self, df: pd.DataFrame, params: dict, min_trades: int) -> tuple:
        """Evaluar un conjunto de parámetros (para paralelismo)"""
        metrics = self.backtest(df, params)
        score = 0

        if metrics['trades'] >= min_trades and metrics['pf'] > 0:
            # Bonus si usa ambas estrategias
            if metrics['breakout_trades'] >= 3 and metrics['macd_trades'] >= 3:
                score = metrics['pf']
            elif metrics['pf'] > 1.2:  # Si es mucho mejor, aceptar
                score = metrics['pf'] * 0.8  # Penalización leve

        return (score, params, metrics)

    def optimize(self, df: pd.DataFrame, min_trades: int = 15) -> tuple:
        """Grid search paralelo para mejores parámetros"""
        param_names = list(self.PARAM_GRID.keys())
        param_values = list(self.PARAM_GRID.values())

        # Generar todas las combinaciones
        all_combos = [dict(zip(param_names, values)) for values in product(*param_values)]

        # Número de CPUs disponibles
        n_jobs = max(1, multiprocessing.cpu_count() - 1)

        # Ejecutar en paralelo
        results = Parallel(n_jobs=n_jobs, prefer="processes")(
            delayed(self._evaluate_params)(df, params, min_trades)
            for params in all_combos
        )

        # Encontrar el mejor
        best_score = 0
        best_params = None
        best_metrics = None

        for score, params, metrics in results:
            if score > best_score:
                best_score = score
                best_params = params
                best_metrics = metrics

        return best_params, best_metrics


class WalkForwardHybrid:
    """Walk-Forward para Sistema Híbrido"""

    def __init__(
        self,
        train_months: int = 18,
        test_months: int = 6,
        pair: str = "EUR_USD"
    ):
        self.train_months = train_months
        self.test_months = test_months
        self.pair = pair
        self.optimizer = HybridOptimizer(pair)

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
        print("=" * 80)
        print(f"🔄 WALK-FORWARD HYBRID SYSTEM - {self.pair}")
        print("=" * 80)
        print(f"   🎯 Sistema: Breakout (ADX bajo) + MACD (ADX alto)")
        print(f"   📊 Train: {self.train_months} meses | Test: {self.test_months} meses")
        print()

        df = self.load_data()
        print(f"   📈 Data: {len(df)} candles H4")
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

            print(f"{'='*70}")
            print(f"📊 Ventana {window_num}: Train {train_start}→{train_end} | Test {test_start}→{test_end}")
            print(f"{'='*70}")

            train_df = df[df['month'].isin(train_months_list)].copy()
            full_df = df[df['month'] <= test_end].copy()
            test_start_idx = len(df[df['month'] < test_start])

            print(f"   Train: {len(train_df)} candles | Test start idx: {test_start_idx}")

            print(f"   🔧 Optimizando sistema híbrido...")
            best_params, train_metrics = self.optimizer.optimize(train_df, min_trades=12)

            if best_params is None:
                print(f"   ❌ No se encontraron parámetros válidos")
                i += step
                continue

            print(f"   ✅ ADX Switch: {best_params['adx_switch']}")
            print(f"      Breakout: Range={best_params['bo_range_period']}, Ext={best_params['bo_extension']}")
            print(f"      MACD: Fast={best_params['macd_fast']}, Slow={best_params['macd_slow']}, R:R={best_params['macd_rr']}")
            print(f"   📈 Train: PF={train_metrics['pf']:.2f}, Trades={train_metrics['trades']} "
                  f"(BO:{train_metrics['breakout_trades']}, MACD:{train_metrics['macd_trades']})")

            # Test
            test_metrics = self.optimizer.backtest(full_df, best_params, count_from=test_start_idx)

            indicator = "🟢" if test_metrics['pf'] >= 1.5 else "🟡" if test_metrics['pf'] >= 1.0 else "🔴"
            status = "PASS" if test_metrics['pf'] >= 1.0 else "FAIL"

            print(f"   {indicator} Test: PF={test_metrics['pf']:.2f}, Trades={test_metrics['trades']} "
                  f"(BO:{test_metrics['breakout_trades']}, MACD:{test_metrics['macd_trades']}), "
                  f"Pips={test_metrics['pips']:.1f} [{status}]")

            if test_metrics['breakout_trades'] > 0 or test_metrics['macd_trades'] > 0:
                print(f"      → Breakout: {test_metrics.get('breakout_pips', 0):.1f} pips | "
                      f"MACD: {test_metrics.get('macd_pips', 0):.1f} pips")

            result = WFResult(
                train_period=f"{train_start}-{train_end}",
                test_period=f"{test_start}-{test_end}",
                params=best_params,
                train_pf=train_metrics['pf'],
                train_trades=train_metrics['trades'],
                test_pf=test_metrics['pf'],
                test_trades=test_metrics['trades'],
                test_pips=test_metrics['pips'],
                test_win_rate=test_metrics['win_rate'],
                breakout_trades=test_metrics['breakout_trades'],
                macd_trades=test_metrics['macd_trades']
            )
            results.append(result)

            i += step
            print()

        return results

    def print_summary(self, results: list):
        """Resumen detallado"""
        print("=" * 80)
        print("📊 RESUMEN WALK-FORWARD - SISTEMA HÍBRIDO")
        print("=" * 80)

        if not results:
            print("   ❌ No hay resultados")
            return

        print(f"\n{'Test Period':<20} {'Tr.PF':>7} {'Te.PF':>7} {'Trades':>7} {'BO':>4} {'MACD':>5} {'Pips':>10} {'Win%':>6} {'St':>4}")
        print("-" * 80)

        total_pips = 0
        total_trades = 0
        total_bo = 0
        total_macd = 0
        profitable = 0

        for r in results:
            status = "✅" if r.test_pf >= 1.0 else "❌"
            if r.test_pf >= 1.0:
                profitable += 1
            total_pips += r.test_pips
            total_trades += r.test_trades
            total_bo += r.breakout_trades
            total_macd += r.macd_trades

            print(f"{r.test_period:<20} {r.train_pf:>7.2f} {r.test_pf:>7.2f} "
                  f"{r.test_trades:>7} {r.breakout_trades:>4} {r.macd_trades:>5} "
                  f"{r.test_pips:>10.1f} {r.test_win_rate:>5.0f}% {status:>4}")

        print("-" * 80)
        avg_pf = np.mean([r.test_pf for r in results])
        consistency = profitable / len(results) * 100

        print(f"{'TOTAL':<20} {'':<7} {avg_pf:>7.2f} {total_trades:>7} {total_bo:>4} {total_macd:>5} {total_pips:>10.1f}")

        print(f"\n🎯 Métricas del Sistema Híbrido:")
        print(f"   Ventanas: {len(results)} | Rentables: {profitable} | Consistencia: {consistency:.0f}%")
        print(f"   Avg Test PF: {avg_pf:.2f}")
        print(f"   Total Pips: {total_pips:.1f}")
        print(f"   Trades: {total_trades} (Breakout: {total_bo}, MACD: {total_macd})")

        # Comparación con estrategias individuales
        print(f"\n📊 COMPARACIÓN CON ESTRATEGIAS INDIVIDUALES:")
        print(f"   ┌─────────────────┬────────────┬────────────┬────────────┐")
        print(f"   │ Estrategia      │ Consistenc │ Total Pips │ Avg PF     │")
        print(f"   ├─────────────────┼────────────┼────────────┼────────────┤")
        print(f"   │ MACD solo       │    57%     │     +29    │    1.22    │")
        print(f"   │ Breakout solo   │    57%     │    +908    │   ~1.0*    │")
        print(f"   │ HÍBRIDO         │    {consistency:.0f}%     │   {total_pips:+.0f}    │    {avg_pf:.2f}    │")
        print(f"   └─────────────────┴────────────┴────────────┴────────────┘")

        print(f"\n{'='*80}")
        if consistency >= 75 and avg_pf >= 1.3:
            print("🏆 SISTEMA HÍBRIDO ROBUSTO - Supera estrategias individuales")
            verdict = "ROBUSTO"
        elif consistency >= 60 and avg_pf >= 1.0:
            print("🟡 SISTEMA ACEPTABLE - Considerar para producción con monitoreo")
            verdict = "ACEPTABLE"
        else:
            print("🔴 SISTEMA DÉBIL - Requiere más ajustes")
            verdict = "DÉBIL"
        print("=" * 80)

        # ADX Switch más común
        print(f"\n📋 Configuración Óptima por Ventana:")
        adx_values = []
        for r in results:
            adx_values.append(r.params['adx_switch'])
            print(f"   {r.test_period}: ADX_switch={r.params['adx_switch']}, "
                  f"BO_ext={r.params['bo_extension']}, MACD_rr={r.params['macd_rr']}")

        most_common_adx = max(set(adx_values), key=adx_values.count)
        print(f"\n   🎯 ADX Switch más efectivo: {most_common_adx}")

        return verdict


def run_hybrid_walkforward(pair: str = "EUR_USD"):
    """Ejecutar Walk-Forward del Sistema Híbrido"""
    wf = WalkForwardHybrid(
        train_months=18,
        test_months=6,
        pair=pair
    )

    results = wf.run()
    verdict = wf.print_summary(results)

    return results, verdict


if __name__ == "__main__":
    import sys
    pair = sys.argv[1] if len(sys.argv) > 1 else "EUR_USD"
    run_hybrid_walkforward(pair)
