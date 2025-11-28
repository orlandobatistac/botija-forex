"""
Walk-Forward Analysis H4 con Filtro Anti-Consolidación
=======================================================
Objetivos:
1. Más trades por año → Mejor validación estadística
2. Filtro EMA spread → Evitar consolidación (problema 2024-2025)

Filtro Anti-Consolidación:
- Si |Price - EMA200| < X pips → NO operar (mercado lateral)
- Esto evita entrar cuando el precio está "pegado" a la EMA200
"""

import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
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


class H4Optimizer:
    """Optimizador para timeframe H4"""

    # Grid de parámetros expandido
    PARAM_GRID = {
        'adx_threshold': [20, 25, 30],
        'atr_sl_mult': [1.5, 2.0, 2.5],
        'rr_ratio': [2.0, 2.5, 3.0],
        'macd_fast': [8, 12],
        'macd_slow': [21, 26],
        'ema_spread_min': [0, 30, 50, 80],  # Filtro anti-consolidación (pips)
    }

    def __init__(self, pair: str = "EUR_USD"):
        self.pair = pair
        self.pip_mult = 100 if 'JPY' in pair else 10000
        self.spread = 1.5 if 'JPY' in pair else 1.0

    def _calculate_indicators(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        """Calcular indicadores"""
        df = df.copy()

        # EMAs
        df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
        df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()

        # EMA Spread (distancia precio-EMA200 en pips) - Filtro anti-consolidación
        df['ema_spread'] = (df['close'] - df['ema_200']).abs() * self.pip_mult

        # MACD
        ema_fast = df['close'].ewm(span=params['macd_fast'], adjust=False).mean()
        ema_slow = df['close'].ewm(span=params['macd_slow'], adjust=False).mean()
        df['macd'] = ema_fast - ema_slow
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()

        df['macd_cross_up'] = (df['macd'] > df['macd_signal']) & (df['macd'].shift(1) <= df['macd_signal'].shift(1))
        df['macd_cross_down'] = (df['macd'] < df['macd_signal']) & (df['macd'].shift(1) >= df['macd_signal'].shift(1))

        # ATR
        high_low = df['high'] - df['low']
        high_close = (df['high'] - df['close'].shift(1)).abs()
        low_close = (df['low'] - df['close'].shift(1)).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr'] = tr.rolling(14).mean()

        # ADX
        df['adx'] = self._calculate_adx(df)

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

    def backtest(self, df: pd.DataFrame, params: dict, count_only_after: int = 0) -> dict:
        """
        Backtest con parámetros específicos.

        Args:
            df: DataFrame con datos OHLC
            params: Parámetros de la estrategia
            count_only_after: Índice a partir del cual contar trades (para test period)
        """
        df = self._calculate_indicators(df, params)

        trades = []
        position = None

        for i in range(200, len(df)):
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

                    # Solo contar si está en período de test
                    if i >= count_only_after:
                        trades.append(pips)
                    position = None
                    continue

            # Nueva entrada
            if position is None and i >= count_only_after:
                # Filtros
                if pd.isna(row['adx']) or row['adx'] < params['adx_threshold']:
                    continue

                # FILTRO ANTI-CONSOLIDACIÓN: Skip si precio muy cerca de EMA200
                if row['ema_spread'] < params['ema_spread_min']:
                    continue

                atr = row['atr']
                close = row['close']

                # LONG
                if row['macd_cross_up'] and close > row['ema_200']:
                    prev_macd = df.iloc[i-1]['macd']
                    if prev_macd < 0:
                        position = {
                            'entry': close,
                            'direction': 'long',
                            'sl': close - (atr * params['atr_sl_mult']),
                            'tp': close + (atr * params['atr_sl_mult'] * params['rr_ratio'])
                        }

                # SHORT
                elif row['macd_cross_down'] and close < row['ema_200']:
                    prev_macd = df.iloc[i-1]['macd']
                    if prev_macd > 0:
                        position = {
                            'entry': close,
                            'direction': 'short',
                            'sl': close + (atr * params['atr_sl_mult']),
                            'tp': close - (atr * params['atr_sl_mult'] * params['rr_ratio'])
                        }

        if not trades:
            return {'pf': 0, 'trades': 0, 'pips': 0, 'win_rate': 0}

        wins = [t for t in trades if t > 0]
        losses = [t for t in trades if t <= 0]

        total_wins = sum(wins) if wins else 0
        total_losses = abs(sum(losses)) if losses else 0.001

        return {
            'pf': total_wins / total_losses,
            'trades': len(trades),
            'pips': sum(trades),
            'win_rate': len(wins) / len(trades) * 100 if trades else 0
        }

    def optimize(self, df: pd.DataFrame, min_trades: int = 20) -> tuple:
        """Grid search para mejores parámetros"""
        best_pf = 0
        best_params = None
        best_metrics = None

        param_names = list(self.PARAM_GRID.keys())
        param_values = list(self.PARAM_GRID.values())

        for values in product(*param_values):
            params = dict(zip(param_names, values))
            metrics = self.backtest(df, params)

            # Criterio: PF alto con mínimo de trades
            if metrics['trades'] >= min_trades and metrics['pf'] > best_pf:
                best_pf = metrics['pf']
                best_params = params
                best_metrics = metrics

        return best_params, best_metrics


class WalkForwardH4:
    """Walk-Forward Analysis en H4"""

    def __init__(
        self,
        train_months: int = 18,  # 18 meses de training
        test_months: int = 6,    # 6 meses de test
        pair: str = "EUR_USD"
    ):
        self.train_months = train_months
        self.test_months = test_months
        self.pair = pair
        self.optimizer = H4Optimizer(pair)

    def load_data(self) -> pd.DataFrame:
        """Cargar datos H4"""
        db_path = Path(__file__).parent / "historical_data.db"
        conn = sqlite3.connect(db_path)

        # Intentar H4 primero, luego tabla genérica
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
        """Ejecutar Walk-Forward Analysis"""
        print("=" * 70)
        print(f"🔄 WALK-FORWARD H4 - {self.pair}")
        print("=" * 70)
        print(f"   Train: {self.train_months} meses | Test: {self.test_months} meses")
        print(f"   Filtro Anti-Consolidación: HABILITADO")
        print()

        df = self.load_data()
        print(f"   📊 Data: {len(df)} candles H4")
        print(f"   📅 Período: {df['time'].min().date()} → {df['time'].max().date()}")
        print()

        # Crear ventanas
        df['month'] = df['time'].dt.to_period('M')
        months = df['month'].unique()

        results = []
        window_size = self.train_months + self.test_months
        step = self.test_months  # Avanzar por período de test

        i = 0
        window_num = 0

        while i + window_size <= len(months):
            window_num += 1
            train_months = months[i:i + self.train_months]
            test_months = months[i + self.train_months:i + window_size]

            train_start = train_months[0]
            train_end = train_months[-1]
            test_start = test_months[0]
            test_end = test_months[-1]

            print(f"{'='*60}")
            print(f"📊 Ventana {window_num}: Train {train_start}-{train_end} → Test {test_start}-{test_end}")
            print(f"{'='*60}")

            # Filtrar datos
            train_df = df[df['month'].isin(train_months)].copy()
            full_df = df[df['month'] <= test_end].copy()  # Incluir histórico para indicadores
            test_start_idx = len(df[df['month'] < test_start])

            print(f"   Train: {len(train_df)} candles | Test start idx: {test_start_idx}")

            # Optimizar
            print(f"   🔧 Optimizando...")
            best_params, train_metrics = self.optimizer.optimize(train_df, min_trades=15)

            if best_params is None:
                print(f"   ❌ No se encontraron parámetros válidos")
                i += step
                continue

            print(f"   ✅ Mejor: ADX>{best_params['adx_threshold']}, "
                  f"ATR×{best_params['atr_sl_mult']}, R:R 1:{best_params['rr_ratio']}, "
                  f"EMA_spread>{best_params['ema_spread_min']}pips")
            print(f"   📈 Train: PF={train_metrics['pf']:.2f}, Trades={train_metrics['trades']}")

            # Test con parámetros óptimos
            test_metrics = self.optimizer.backtest(full_df, best_params, count_only_after=test_start_idx)

            indicator = "🟢" if test_metrics['pf'] >= 1.5 else "🟡" if test_metrics['pf'] >= 1.0 else "🔴"
            print(f"   {indicator} Test: PF={test_metrics['pf']:.2f}, "
                  f"Trades={test_metrics['trades']}, Pips={test_metrics['pips']:.1f}")

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
        """Resumen de resultados"""
        print("=" * 70)
        print("📊 RESUMEN WALK-FORWARD H4")
        print("=" * 70)

        if not results:
            print("   ❌ No hay resultados")
            return

        print(f"\n{'Test Period':<20} {'Train PF':>10} {'Test PF':>10} {'Trades':>8} {'Pips':>10} {'Win%':>7} {'Status':>8}")
        print("-" * 80)

        total_pips = 0
        total_trades = 0
        profitable = 0

        for r in results:
            status = "✅" if r.test_pf >= 1.0 else "❌"
            if r.test_pf >= 1.0:
                profitable += 1
            total_pips += r.test_pips
            total_trades += r.test_trades

            print(f"{r.test_period:<20} {r.train_pf:>10.2f} {r.test_pf:>10.2f} "
                  f"{r.test_trades:>8} {r.test_pips:>10.1f} {r.test_win_rate:>6.1f}% {status:>8}")

        print("-" * 80)
        avg_pf = np.mean([r.test_pf for r in results])
        consistency = profitable / len(results) * 100

        print(f"{'TOTAL':<20} {'':<10} {avg_pf:>10.2f} {total_trades:>8} {total_pips:>10.1f}")

        print(f"\n🎯 Métricas:")
        print(f"   Ventanas testeadas: {len(results)}")
        print(f"   Ventanas rentables: {profitable}")
        print(f"   Consistencia: {consistency:.0f}%")
        print(f"   Avg Test PF: {avg_pf:.2f}")
        print(f"   Total Pips: {total_pips:.1f}")
        print(f"   Total Trades: {total_trades}")

        print(f"\n{'='*70}")
        if consistency >= 80 and avg_pf >= 1.3:
            print("🏆 ESTRATEGIA ROBUSTA - Lista para producción")
        elif consistency >= 60 and avg_pf >= 1.0:
            print("🟡 ESTRATEGIA ACEPTABLE - Monitorear")
        else:
            print("🔴 ESTRATEGIA DÉBIL - Requiere ajustes")
        print("=" * 70)

        # Parámetros más comunes
        print(f"\n📋 Parámetros por Ventana:")
        for r in results:
            p = r.params
            print(f"   {r.test_period}: ADX>{p['adx_threshold']}, "
                  f"ATR×{p['atr_sl_mult']}, R:R 1:{p['rr_ratio']}, "
                  f"EMA_spread>{p['ema_spread_min']}")

        # Analizar filtro anti-consolidación
        print(f"\n📊 Análisis Filtro Anti-Consolidación:")
        spread_values = [r.params['ema_spread_min'] for r in results]
        print(f"   Valores usados: {set(spread_values)}")
        print(f"   Valor más común: {max(set(spread_values), key=spread_values.count)} pips")


def run_h4_walkforward():
    """Ejecutar Walk-Forward H4"""
    pairs = ['EUR_USD', 'USD_JPY']

    for pair in pairs:
        try:
            wf = WalkForwardH4(
                train_months=18,
                test_months=6,
                pair=pair
            )
            results = wf.run()
            wf.print_summary(results)
            print("\n")
        except Exception as e:
            print(f"❌ Error con {pair}: {e}")
            print()


if __name__ == "__main__":
    run_h4_walkforward()
