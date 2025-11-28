"""
Test final de AdaptiveStrategy en producción
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
import pandas as pd
from pathlib import Path
from app.services.strategies.adaptive import AdaptiveStrategy


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


def backtest_adaptive(pair: str = "EUR_USD"):
    """Backtest de estrategia adaptativa"""
    print(f"\n{'='*60}")
    print(f"📊 BACKTEST ADAPTIVE STRATEGY - {pair}")
    print('='*60)

    df = load_data(pair)
    print(f"Data: {len(df)} candles ({df['time'].min().date()} → {df['time'].max().date()})")

    strategy = AdaptiveStrategy()

    pip_mult = 100 if 'JPY' in pair else 10000
    spread = 1.5 if 'JPY' in pair else 1.0

    trades = []
    position = None

    # Convert to list of dicts for generate_signal
    candles = df.to_dict('records')

    for i in range(250, len(df)):
        # Pass historical candles up to current point
        historical = candles[:i+1]
        signal = strategy.generate_signal(historical)

        row = df.iloc[i]

        # Manage open position
        if position:
            exit_price = None
            exit_reason = None

            if position['direction'] == 'long':
                if row['low'] <= position['sl']:
                    exit_price = position['sl']
                    exit_reason = 'stop_loss'
                elif row['high'] >= position['tp']:
                    exit_price = position['tp']
                    exit_reason = 'take_profit'
                elif signal.direction == 'SHORT':
                    exit_price = row['close']
                    exit_reason = 'signal_reverse'
            else:
                if row['high'] >= position['sl']:
                    exit_price = position['sl']
                    exit_reason = 'stop_loss'
                elif row['low'] <= position['tp']:
                    exit_price = position['tp']
                    exit_reason = 'take_profit'
                elif signal.direction == 'LONG':
                    exit_price = row['close']
                    exit_reason = 'signal_reverse'

            if exit_price:
                if position['direction'] == 'long':
                    pips = (exit_price - position['entry']) * pip_mult - spread
                else:
                    pips = (position['entry'] - exit_price) * pip_mult - spread

                trades.append({
                    'year': position['entry_time'].year,
                    'direction': position['direction'],
                    'pips': pips,
                    'exit_reason': exit_reason,
                    'regime': position['regime']
                })
                position = None
                continue

        # New entry
        if position is None and signal.direction in ['LONG', 'SHORT']:
            position = {
                'entry': signal.entry_price,
                'entry_time': row['time'],
                'direction': signal.direction.lower(),
                'sl': signal.stop_loss,
                'tp': signal.take_profit,
                'regime': signal.regime
            }

    # Calculate metrics
    if not trades:
        print("❌ No trades generated")
        return

    wins = [t for t in trades if t['pips'] > 0]
    losses = [t for t in trades if t['pips'] <= 0]

    total_wins = sum(t['pips'] for t in wins)
    total_losses = abs(sum(t['pips'] for t in losses))
    pf = total_wins / total_losses if total_losses > 0 else float('inf')

    print(f"\n📈 Resultados:")
    print(f"   Trades: {len(trades)}")
    print(f"   Win Rate: {len(wins)/len(trades)*100:.1f}%")
    print(f"   Net Pips: {sum(t['pips'] for t in trades):.1f}")
    print(f"   Profit Factor: {pf:.2f}")

    # By year
    print(f"\n📅 Por Año:")
    years = sorted(set(t['year'] for t in trades))
    profitable_years = 0
    for year in years:
        year_trades = [t for t in trades if t['year'] == year]
        year_pips = sum(t['pips'] for t in year_trades)
        indicator = "✅" if year_pips > 0 else "❌"
        if year_pips > 0:
            profitable_years += 1
        print(f"   {year}: {indicator} {len(year_trades):2} trades | {year_pips:>8.1f} pips")

    print(f"\n🎯 Consistencia: {profitable_years}/{len(years)} años rentables ({profitable_years/len(years)*100:.0f}%)")

    return {
        'trades': len(trades),
        'win_rate': len(wins)/len(trades)*100,
        'net_pips': sum(t['pips'] for t in trades),
        'pf': pf,
        'consistency': profitable_years/len(years)*100
    }


if __name__ == "__main__":
    print("=" * 60)
    print("🧪 TEST FINAL - ADAPTIVE STRATEGY (PRODUCCIÓN)")
    print("=" * 60)

    results = {}
    for pair in ['EUR_USD', 'USD_JPY', 'GBP_USD']:
        results[pair] = backtest_adaptive(pair)

    print("\n" + "=" * 60)
    print("📊 RESUMEN FINAL")
    print("=" * 60)
    print(f"{'Pair':<10} {'Trades':>7} {'Win%':>7} {'Net':>10} {'PF':>6} {'Consist':>8}")
    print("-" * 60)
    for pair, r in results.items():
        if r:
            print(f"{pair:<10} {r['trades']:>7} {r['win_rate']:>6.1f}% {r['net_pips']:>10.1f} {r['pf']:>6.2f} {r['consistency']:>7.0f}%")
