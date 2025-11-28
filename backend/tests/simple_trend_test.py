"""
Simple Trend Strategy Test
===========================
Prueba tu hipótesis: seguir tendencia con TP pequeño y fijo.

Run: cd backend && python -m tests.simple_trend_test
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import List, Dict


@dataclass
class TradeResult:
    pnl_pips: float
    exit_reason: str
    bars_held: int


def run_simple_backtest(
    df: pd.DataFrame,
    tp_pips: float = 10,  # Take profit fijo
    sl_pips: float = 20,  # Stop loss fijo
    use_trend_filter: bool = True,
    ema_period: int = 50,
    entry_type: str = "any_close",  # any_close, ema_cross, momentum
    pip_value: float = 0.0001,
    spread_pips: float = 1.5
) -> Dict:
    """
    Backtest ultra-simple de seguir tendencia.

    Estrategias de entrada:
    - any_close: Entra en cada vela si está en tendencia
    - ema_cross: Entra cuando precio cruza EMA
    - momentum: Entra después de 3 velas en misma dirección
    """

    df = df.copy()

    # Calcular EMA
    df['ema'] = df['close'].ewm(span=ema_period, adjust=False).mean()
    df['ema_slow'] = df['close'].ewm(span=200, adjust=False).mean()

    # Momentum: 3 velas consecutivas
    df['up_count'] = (df['close'] > df['close'].shift(1)).astype(int)
    df['down_count'] = (df['close'] < df['close'].shift(1)).astype(int)

    trades = []
    current_trade = None
    bars_in_trade = 0

    # Empezar después de warmup
    start_idx = max(ema_period, 200) + 10

    for i in range(start_idx, len(df)):
        row = df.iloc[i]
        price = row['close']
        high = row['high']
        low = row['low']
        ema = row['ema']
        ema_slow = row['ema_slow']

        # Determinar tendencia
        if use_trend_filter:
            trend = "UP" if price > ema_slow else "DOWN"
        else:
            trend = "UP" if price > ema else "DOWN"

        # Si hay trade abierto, verificar SL/TP
        if current_trade:
            bars_in_trade += 1
            direction = current_trade['direction']
            entry = current_trade['entry']
            sl = current_trade['sl']
            tp = current_trade['tp']

            if direction == 'LONG':
                if low <= sl:
                    pnl = -sl_pips - spread_pips
                    trades.append(TradeResult(pnl, 'SL', bars_in_trade))
                    current_trade = None
                    bars_in_trade = 0
                elif high >= tp:
                    pnl = tp_pips - spread_pips
                    trades.append(TradeResult(pnl, 'TP', bars_in_trade))
                    current_trade = None
                    bars_in_trade = 0
            else:  # SHORT
                if high >= sl:
                    pnl = -sl_pips - spread_pips
                    trades.append(TradeResult(pnl, 'SL', bars_in_trade))
                    current_trade = None
                    bars_in_trade = 0
                elif low <= tp:
                    pnl = tp_pips - spread_pips
                    trades.append(TradeResult(pnl, 'TP', bars_in_trade))
                    current_trade = None
                    bars_in_trade = 0
            continue

        # Buscar entrada
        should_enter = False
        direction = None

        if entry_type == "any_close":
            # Entra en cada vela que cierra en dirección de tendencia
            if trend == "UP" and row['close'] > row['open']:
                should_enter = True
                direction = 'LONG'
            elif trend == "DOWN" and row['close'] < row['open']:
                should_enter = True
                direction = 'SHORT'

        elif entry_type == "ema_cross":
            # Entra cuando precio cruza EMA rápida
            prev_price = df.iloc[i-1]['close']
            prev_ema = df.iloc[i-1]['ema']

            if trend == "UP" and prev_price < prev_ema and price > ema:
                should_enter = True
                direction = 'LONG'
            elif trend == "DOWN" and prev_price > prev_ema and price < ema:
                should_enter = True
                direction = 'SHORT'

        elif entry_type == "momentum":
            # Entra después de 3 velas verdes/rojas consecutivas
            if i >= 3:
                last_3 = df.iloc[i-2:i+1]
                all_green = all(last_3['close'] > last_3['open'])
                all_red = all(last_3['close'] < last_3['open'])

                if trend == "UP" and all_green:
                    should_enter = True
                    direction = 'LONG'
                elif trend == "DOWN" and all_red:
                    should_enter = True
                    direction = 'SHORT'

        elif entry_type == "pullback":
            # Entra en pullback a EMA en dirección de tendencia
            prev_row = df.iloc[i-1]

            # Pullback: precio tocó EMA y rebotó
            if trend == "UP":
                touched_ema = prev_row['low'] <= prev_row['ema'] * 1.002
                bounced = row['close'] > row['open'] and row['close'] > prev_row['close']
                if touched_ema and bounced:
                    should_enter = True
                    direction = 'LONG'
            elif trend == "DOWN":
                touched_ema = prev_row['high'] >= prev_row['ema'] * 0.998
                bounced = row['close'] < row['open'] and row['close'] < prev_row['close']
                if touched_ema and bounced:
                    should_enter = True
                    direction = 'SHORT'

        if should_enter and direction:
            if direction == 'LONG':
                current_trade = {
                    'direction': 'LONG',
                    'entry': price,
                    'sl': price - (sl_pips * pip_value),
                    'tp': price + (tp_pips * pip_value)
                }
            else:
                current_trade = {
                    'direction': 'SHORT',
                    'entry': price,
                    'sl': price + (sl_pips * pip_value),
                    'tp': price - (tp_pips * pip_value)
                }
            bars_in_trade = 0

    # Calcular resultados
    if not trades:
        return {
            'trades': 0, 'win_rate': 0, 'net_pips': 0,
            'profit_factor': 0, 'max_dd': 0, 'avg_bars': 0
        }

    wins = [t for t in trades if t.pnl_pips > 0]
    losses = [t for t in trades if t.pnl_pips <= 0]

    gross_profit = sum(t.pnl_pips for t in wins)
    gross_loss = abs(sum(t.pnl_pips for t in losses))
    net_pips = sum(t.pnl_pips for t in trades)

    # Max drawdown
    cumulative = 0
    peak = 0
    max_dd = 0
    for t in trades:
        cumulative += t.pnl_pips
        if cumulative > peak:
            peak = cumulative
        dd = peak - cumulative
        if dd > max_dd:
            max_dd = dd

    return {
        'trades': len(trades),
        'wins': len(wins),
        'losses': len(losses),
        'win_rate': round(len(wins) / len(trades) * 100, 1),
        'net_pips': round(net_pips, 1),
        'profit_factor': round(gross_profit / gross_loss, 2) if gross_loss > 0 else 0,
        'max_dd': round(max_dd, 1),
        'avg_bars': round(sum(t.bars_held for t in trades) / len(trades), 1),
        'avg_win': round(gross_profit / len(wins), 1) if wins else 0,
        'avg_loss': round(gross_loss / len(losses), 1) if losses else 0
    }


def load_data(instrument: str, timeframe: str) -> pd.DataFrame:
    """Load from SQLite database."""
    conn = sqlite3.connect("tests/historical_data.db")
    df = pd.read_sql_query(
        "SELECT time, open, high, low, close FROM candles WHERE instrument = ? AND timeframe = ? ORDER BY time",
        conn, params=(instrument, timeframe)
    )
    conn.close()
    return df


def main():
    print("=" * 70)
    print("🧪 SIMPLE TREND STRATEGY TEST - Tu Hipótesis")
    print("=" * 70)
    print("\nProbando: Seguir tendencia con TP pequeño y fijo")
    print("Pregunta: ¿Es 'casi seguro' ganar pips pequeños siguiendo tendencia?\n")

    # Cargar datos
    df = load_data("EUR_USD", "H1")
    print(f"📊 Datos: EUR_USD H1 - {len(df):,} velas")
    print(f"   Período: {df['time'].iloc[0][:10]} → {df['time'].iloc[-1][:10]}\n")

    # Probar diferentes configuraciones
    configs = [
        # TP pequeño con SL normal (tu idea)
        {"name": "TP 5 pips / SL 15", "tp": 5, "sl": 15, "entry": "any_close"},
        {"name": "TP 10 pips / SL 20", "tp": 10, "sl": 20, "entry": "any_close"},
        {"name": "TP 15 pips / SL 30", "tp": 15, "sl": 30, "entry": "any_close"},

        # TP pequeño con SL ajustado
        {"name": "TP 10 / SL 10 (1:1)", "tp": 10, "sl": 10, "entry": "any_close"},
        {"name": "TP 10 / SL 5 (2:1 inv)", "tp": 10, "sl": 5, "entry": "any_close"},

        # Diferentes tipos de entrada
        {"name": "EMA Cross TP10/SL20", "tp": 10, "sl": 20, "entry": "ema_cross"},
        {"name": "Momentum TP10/SL20", "tp": 10, "sl": 20, "entry": "momentum"},
        {"name": "Pullback TP10/SL20", "tp": 10, "sl": 20, "entry": "pullback"},

        # TP más grande (comparación)
        {"name": "TP 30 pips / SL 15", "tp": 30, "sl": 15, "entry": "any_close"},
        {"name": "TP 50 pips / SL 25", "tp": 50, "sl": 25, "entry": "any_close"},
    ]

    results = []

    for cfg in configs:
        result = run_simple_backtest(
            df,
            tp_pips=cfg['tp'],
            sl_pips=cfg['sl'],
            entry_type=cfg['entry'],
            use_trend_filter=True
        )
        result['name'] = cfg['name']
        results.append(result)

        pf_icon = "🟢" if result['profit_factor'] >= 1.5 else ("🟡" if result['profit_factor'] >= 1 else "🔴")
        print(f"{pf_icon} {cfg['name']:<25} | Trades: {result['trades']:>5} | Win: {result['win_rate']:>5}% | Net: {result['net_pips']:>8} | PF: {result['profit_factor']:>5}")

    # Tabla resumen
    print("\n" + "=" * 90)
    print("📈 RESUMEN - Ordenado por Profit Factor")
    print("=" * 90)
    print(f"{'Estrategia':<28} {'Trades':>7} {'Win%':>7} {'Net Pips':>10} {'PF':>6} {'AvgBars':>8}")
    print("-" * 90)

    sorted_results = sorted(results, key=lambda x: x['profit_factor'], reverse=True)
    for r in sorted_results:
        star = "⭐" if r['profit_factor'] >= 1.5 else ""
        print(f"{r['name']:<28} {r['trades']:>7} {r['win_rate']:>6}% {r['net_pips']:>10} {r['profit_factor']:>5} {r['avg_bars']:>7} {star}")

    # Análisis
    print("\n" + "=" * 70)
    print("🎯 ANÁLISIS DE TU HIPÓTESIS")
    print("=" * 70)

    tp_pequeño = [r for r in results if r['name'].startswith('TP 5') or r['name'].startswith('TP 10')]
    tp_grande = [r for r in results if 'TP 30' in r['name'] or 'TP 50' in r['name']]

    avg_pf_pequeño = sum(r['profit_factor'] for r in tp_pequeño) / len(tp_pequeño) if tp_pequeño else 0
    avg_pf_grande = sum(r['profit_factor'] for r in tp_grande) / len(tp_grande) if tp_grande else 0

    print(f"\n   TP Pequeño (5-10 pips) - PF Promedio: {avg_pf_pequeño:.2f}")
    print(f"   TP Grande (30-50 pips) - PF Promedio: {avg_pf_grande:.2f}")

    if avg_pf_pequeño < 1:
        print("\n   ❌ CONCLUSIÓN: TP pequeño NO es 'casi seguro'")
        print("      El spread (1.5 pips) consume gran parte de la ganancia")
        print("      Necesitas ~30% de movimiento extra solo para cubrir spread")
    else:
        print("\n   ✅ CONCLUSIÓN: TP pequeño puede funcionar con buen entry")

    print("\n   💡 INSIGHT: El problema no es el TP pequeño,")
    print("      es la FRECUENCIA de entrada. Más trades = más spread pagado.")


if __name__ == "__main__":
    main()
