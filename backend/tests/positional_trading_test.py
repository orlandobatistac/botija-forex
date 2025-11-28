"""
Positional Trading Strategy Test (D1/W1)
========================================
Estrategia de largo plazo basada en:
- EMA 200 (filtro de tendencia)
- MACD (momentum y señales)
- ATR (stop loss dinámico)

Objetivo: Consistencia en backtests de 5+ años
"""

import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Optional
from dataclasses import dataclass


@dataclass
class PositionalTrade:
    """Trade de largo plazo"""
    entry_time: datetime
    entry_price: float
    direction: str  # 'long' or 'short'
    stop_loss: float
    take_profit: Optional[float]
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    pips: float = 0.0
    exit_reason: str = ""
    holding_days: int = 0


class PositionalStrategy:
    """
    Positional Trading Strategy

    Reglas:
    - Timeframe: D1 (diario)
    - Tendencia: EMA 200
    - Entrada: MACD cross + precio correcto vs EMA
    - SL: ATR-based (amplio para dar espacio)
    - TP: Trailing o ratio fijo
    """

    def __init__(
        self,
        ema_period: int = 200,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        atr_period: int = 14,
        atr_sl_mult: float = 2.0,
        rr_ratio: float = 2.0,
        use_trailing: bool = True,
        trailing_atr_mult: float = 1.5
    ):
        self.ema_period = ema_period
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal
        self.atr_period = atr_period
        self.atr_sl_mult = atr_sl_mult
        self.rr_ratio = rr_ratio
        self.use_trailing = use_trailing
        self.trailing_atr_mult = trailing_atr_mult

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcular indicadores técnicos"""
        df = df.copy()

        # EMA 200
        df['ema200'] = df['close'].ewm(span=self.ema_period, adjust=False).mean()

        # MACD
        ema_fast = df['close'].ewm(span=self.macd_fast, adjust=False).mean()
        ema_slow = df['close'].ewm(span=self.macd_slow, adjust=False).mean()
        df['macd'] = ema_fast - ema_slow
        df['macd_signal'] = df['macd'].ewm(span=self.macd_signal, adjust=False).mean()
        df['macd_histogram'] = df['macd'] - df['macd_signal']

        # MACD Cross
        df['macd_cross_up'] = (df['macd'] > df['macd_signal']) & (df['macd'].shift(1) <= df['macd_signal'].shift(1))
        df['macd_cross_down'] = (df['macd'] < df['macd_signal']) & (df['macd'].shift(1) >= df['macd_signal'].shift(1))

        # ATR
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift(1))
        low_close = abs(df['low'] - df['close'].shift(1))
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr'] = tr.rolling(window=self.atr_period).mean()

        # Tendencia
        df['trend'] = np.where(df['close'] > df['ema200'], 'bullish', 'bearish')

        return df

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Generar señales de entrada"""
        df = self.calculate_indicators(df)

        # Señal LONG: MACD cross up + precio > EMA200
        df['long_signal'] = (
            df['macd_cross_up'] &
            (df['close'] > df['ema200']) &
            (df['macd'] < 0)  # MACD viene de territorio negativo (mejor momentum)
        )

        # Señal SHORT: MACD cross down + precio < EMA200
        df['short_signal'] = (
            df['macd_cross_down'] &
            (df['close'] < df['ema200']) &
            (df['macd'] > 0)  # MACD viene de territorio positivo
        )

        return df

    def backtest(self, df: pd.DataFrame, pair: str = "EUR_USD") -> dict:
        """Ejecutar backtest"""
        df = self.generate_signals(df)

        # Pip value
        pip_mult = 100 if 'JPY' in pair else 10000
        spread_pips = 1.0 if 'JPY' not in pair else 1.5

        trades: list[PositionalTrade] = []
        current_trade: Optional[PositionalTrade] = None

        for i in range(self.ema_period, len(df)):
            row = df.iloc[i]

            # Si hay trade abierto, gestionar
            if current_trade:
                current_price = row['close']
                current_atr = row['atr']
                days_held = (row['time'] - current_trade.entry_time).days

                # Check exit conditions
                exit_reason = None
                exit_price = None

                if current_trade.direction == 'long':
                    # Check stop loss
                    if row['low'] <= current_trade.stop_loss:
                        exit_price = current_trade.stop_loss
                        exit_reason = 'stop_loss'
                    # Check take profit
                    elif current_trade.take_profit and row['high'] >= current_trade.take_profit:
                        exit_price = current_trade.take_profit
                        exit_reason = 'take_profit'
                    # Trailing stop (si está habilitado)
                    elif self.use_trailing:
                        new_sl = current_price - (current_atr * self.trailing_atr_mult)
                        if new_sl > current_trade.stop_loss:
                            current_trade.stop_loss = new_sl
                    # Señal contraria
                    elif row['short_signal']:
                        exit_price = current_price
                        exit_reason = 'signal_reverse'

                else:  # short
                    if row['high'] >= current_trade.stop_loss:
                        exit_price = current_trade.stop_loss
                        exit_reason = 'stop_loss'
                    elif current_trade.take_profit and row['low'] <= current_trade.take_profit:
                        exit_price = current_trade.take_profit
                        exit_reason = 'take_profit'
                    elif self.use_trailing:
                        new_sl = current_price + (current_atr * self.trailing_atr_mult)
                        if new_sl < current_trade.stop_loss:
                            current_trade.stop_loss = new_sl
                    elif row['long_signal']:
                        exit_price = current_price
                        exit_reason = 'signal_reverse'

                # Cerrar trade si hay razón
                if exit_reason:
                    current_trade.exit_time = row['time']
                    current_trade.exit_price = exit_price
                    current_trade.exit_reason = exit_reason
                    current_trade.holding_days = days_held

                    if current_trade.direction == 'long':
                        current_trade.pips = (exit_price - current_trade.entry_price) * pip_mult - spread_pips
                    else:
                        current_trade.pips = (current_trade.entry_price - exit_price) * pip_mult - spread_pips

                    trades.append(current_trade)
                    current_trade = None
                    continue

            # Buscar nueva entrada (solo si no hay trade abierto)
            if current_trade is None:
                atr = row['atr']

                if row['long_signal']:
                    entry_price = row['close']
                    sl = entry_price - (atr * self.atr_sl_mult)
                    tp = entry_price + (atr * self.atr_sl_mult * self.rr_ratio) if not self.use_trailing else None

                    current_trade = PositionalTrade(
                        entry_time=row['time'],
                        entry_price=entry_price,
                        direction='long',
                        stop_loss=sl,
                        take_profit=tp
                    )

                elif row['short_signal']:
                    entry_price = row['close']
                    sl = entry_price + (atr * self.atr_sl_mult)
                    tp = entry_price - (atr * self.atr_sl_mult * self.rr_ratio) if not self.use_trailing else None

                    current_trade = PositionalTrade(
                        entry_time=row['time'],
                        entry_price=entry_price,
                        direction='short',
                        stop_loss=sl,
                        take_profit=tp
                    )

        # Cerrar trade pendiente al final
        if current_trade:
            last_row = df.iloc[-1]
            current_trade.exit_time = last_row['time']
            current_trade.exit_price = last_row['close']
            current_trade.exit_reason = 'end_of_data'

            if current_trade.direction == 'long':
                current_trade.pips = (last_row['close'] - current_trade.entry_price) * pip_mult - spread_pips
            else:
                current_trade.pips = (current_trade.entry_price - last_row['close']) * pip_mult - spread_pips

            trades.append(current_trade)

        return self._calculate_metrics(trades, pair)

    def _calculate_metrics(self, trades: list[PositionalTrade], pair: str) -> dict:
        """Calcular métricas del backtest"""
        if not trades:
            return {
                'pair': pair,
                'total_trades': 0,
                'win_rate': 0,
                'net_pips': 0,
                'profit_factor': 0,
                'avg_holding_days': 0
            }

        wins = [t for t in trades if t.pips > 0]
        losses = [t for t in trades if t.pips <= 0]

        total_wins = sum(t.pips for t in wins)
        total_losses = abs(sum(t.pips for t in losses))

        avg_holding = np.mean([t.holding_days for t in trades]) if trades else 0

        # Análisis por año
        trades_by_year = {}
        for t in trades:
            year = t.entry_time.year
            if year not in trades_by_year:
                trades_by_year[year] = []
            trades_by_year[year].append(t)

        yearly_results = {}
        for year, year_trades in sorted(trades_by_year.items()):
            year_pips = sum(t.pips for t in year_trades)
            year_wins = len([t for t in year_trades if t.pips > 0])
            yearly_results[year] = {
                'trades': len(year_trades),
                'pips': round(year_pips, 1),
                'win_rate': round(year_wins / len(year_trades) * 100, 1) if year_trades else 0
            }

        return {
            'pair': pair,
            'total_trades': len(trades),
            'wins': len(wins),
            'losses': len(losses),
            'win_rate': round(len(wins) / len(trades) * 100, 1) if trades else 0,
            'net_pips': round(sum(t.pips for t in trades), 1),
            'profit_factor': round(total_wins / total_losses, 2) if total_losses > 0 else float('inf'),
            'avg_win': round(total_wins / len(wins), 1) if wins else 0,
            'avg_loss': round(total_losses / len(losses), 1) if losses else 0,
            'avg_holding_days': round(avg_holding, 1),
            'yearly_results': yearly_results,
            'trades': trades
        }


def load_daily_data(pair: str, start_year: int = 2020) -> pd.DataFrame:
    """Cargar datos diarios desde la base de datos (tabla candles)"""
    db_path = Path(__file__).parent / "historical_data.db"

    if not db_path.exists():
        raise FileNotFoundError("No se encontró historical_data.db. Ejecuta data_downloader.py primero.")

    conn = sqlite3.connect(db_path)

    # La tabla es 'candles' con columnas instrument, timeframe, time, open, high, low, close, volume
    query = """
        SELECT time, open, high, low, close, volume
        FROM candles
        WHERE instrument = ? AND timeframe = 'D' AND time >= ?
        ORDER BY time
    """
    start_date = f"{start_year}-01-01"
    df = pd.read_sql(query, conn, params=(pair, start_date))

    conn.close()

    if df.empty:
        raise ValueError(f"No hay datos D1 para {pair}")

    df['time'] = pd.to_datetime(df['time'])
    return df
def run_positional_test():
    """Ejecutar test de estrategia posicional"""
    print("=" * 80)
    print("📈 POSITIONAL TRADING STRATEGY TEST (D1)")
    print("=" * 80)
    print("Estrategia: EMA200 + MACD (basado en recomendación de Gemini)")
    print()

    pairs = ['EUR_USD', 'USD_JPY', 'GBP_USD']

    # Configuraciones a probar
    configs = [
        {
            'name': 'Classic MACD + EMA200',
            'params': {
                'ema_period': 200,
                'atr_sl_mult': 2.0,
                'rr_ratio': 2.0,
                'use_trailing': False
            }
        },
        {
            'name': 'MACD + Trailing Stop',
            'params': {
                'ema_period': 200,
                'atr_sl_mult': 2.0,
                'use_trailing': True,
                'trailing_atr_mult': 1.5
            }
        },
        {
            'name': 'Wide SL (3x ATR) + R:R 3:1',
            'params': {
                'ema_period': 200,
                'atr_sl_mult': 3.0,
                'rr_ratio': 3.0,
                'use_trailing': False
            }
        },
        {
            'name': 'Conservative (EMA 200 + Trailing)',
            'params': {
                'ema_period': 200,
                'atr_sl_mult': 2.5,
                'use_trailing': True,
                'trailing_atr_mult': 2.0
            }
        }
    ]

    all_results = []

    for pair in pairs:
        print(f"\n{'='*60}")
        print(f"📊 {pair} (Daily)")
        print('='*60)

        try:
            df = load_daily_data(pair)
            print(f"   Data: {len(df)} candles ({df['time'].min().strftime('%Y-%m-%d')} → {df['time'].max().strftime('%Y-%m-%d')})")

            for config in configs:
                strategy = PositionalStrategy(**config['params'])
                result = strategy.backtest(df, pair)
                result['config'] = config['name']
                all_results.append(result)

                # Indicador de resultado
                if result['profit_factor'] >= 1.5:
                    indicator = "🟢"
                elif result['profit_factor'] >= 1.0:
                    indicator = "🟡"
                else:
                    indicator = "🔴"

                print(f"   {indicator} {config['name']:<30} | Trades: {result['total_trades']:3} | "
                      f"Win: {result['win_rate']:5.1f}% | Net: {result['net_pips']:8.1f} | "
                      f"PF: {result['profit_factor']:.2f} | Avg Hold: {result['avg_holding_days']:.0f}d")

        except Exception as e:
            print(f"   ❌ Error: {e}")

    # Resumen de mejores resultados
    print("\n" + "=" * 80)
    print("🏆 TOP RESULTS (PF > 1.0)")
    print("=" * 80)

    profitable = [r for r in all_results if r['profit_factor'] >= 1.0 and r['total_trades'] >= 10]
    profitable.sort(key=lambda x: x['profit_factor'], reverse=True)

    if profitable:
        print(f"{'Config':<35} {'Pair':<10} {'Trades':>7} {'Win%':>7} {'Net':>10} {'PF':>6}")
        print("-" * 80)
        for r in profitable[:10]:
            print(f"{r['config']:<35} {r['pair']:<10} {r['total_trades']:>7} "
                  f"{r['win_rate']:>6.1f}% {r['net_pips']:>10.1f} {r['profit_factor']:>6.2f}")
    else:
        print("   ❌ Ninguna configuración fue rentable con >10 trades")

    # Análisis por año del mejor resultado
    if profitable:
        best = profitable[0]
        print(f"\n📅 Análisis Anual - Mejor Config: {best['config']} ({best['pair']})")
        print("-" * 50)
        for year, data in best.get('yearly_results', {}).items():
            indicator = "✅" if data['pips'] > 0 else "❌"
            print(f"   {year}: {indicator} {data['trades']:2} trades | {data['pips']:>8.1f} pips | Win: {data['win_rate']:.0f}%")

    # Consistencia: cuántos años fueron rentables
    print("\n" + "=" * 80)
    print("📊 ANÁLISIS DE CONSISTENCIA (años rentables / total años)")
    print("=" * 80)

    for r in profitable[:5]:
        yearly = r.get('yearly_results', {})
        profitable_years = sum(1 for y in yearly.values() if y['pips'] > 0)
        total_years = len(yearly)
        consistency = profitable_years / total_years * 100 if total_years > 0 else 0

        print(f"   {r['config']:<35} {r['pair']:<10} → {profitable_years}/{total_years} años ({consistency:.0f}%)")


if __name__ == "__main__":
    run_positional_test()
