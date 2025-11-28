"""
High Win Rate Strategy Test
============================
Buscar estrategias con Win Rate > 60%

Run: cd backend && python -m tests.high_winrate_test
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
import pandas as pd
import numpy as np
from typing import Dict, List


def load_data(instrument: str, timeframe: str) -> pd.DataFrame:
    """Load from SQLite database."""
    conn = sqlite3.connect("tests/historical_data.db")
    df = pd.read_sql_query(
        "SELECT time, open, high, low, close FROM candles WHERE instrument = ? AND timeframe = ? ORDER BY time",
        conn, params=(instrument, timeframe)
    )
    conn.close()
    return df


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate all needed indicators."""
    df = df.copy()

    # EMAs
    df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()

    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 0.0001)
    df['rsi'] = 100 - (100 / (1 + rs))

    # ATR
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = tr.rolling(14).mean()

    # Bollinger Bands
    df['bb_mid'] = df['close'].rolling(20).mean()
    df['bb_std'] = df['close'].rolling(20).std()
    df['bb_upper'] = df['bb_mid'] + (df['bb_std'] * 2)
    df['bb_lower'] = df['bb_mid'] - (df['bb_std'] * 2)

    # MACD
    ema_12 = df['close'].ewm(span=12, adjust=False).mean()
    ema_26 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = ema_12 - ema_26
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']

    # Stochastic
    low_14 = df['low'].rolling(14).min()
    high_14 = df['high'].rolling(14).max()
    df['stoch_k'] = 100 * (df['close'] - low_14) / (high_14 - low_14 + 0.0001)
    df['stoch_d'] = df['stoch_k'].rolling(3).mean()

    # Candle patterns
    df['body'] = abs(df['close'] - df['open'])
    df['upper_wick'] = df['high'] - df[['close', 'open']].max(axis=1)
    df['lower_wick'] = df[['close', 'open']].min(axis=1) - df['low']
    df['is_green'] = df['close'] > df['open']

    # Consecutive candles
    df['green_streak'] = df['is_green'].groupby((df['is_green'] != df['is_green'].shift()).cumsum()).cumcount() + 1
    df['green_streak'] = df['green_streak'].where(df['is_green'], 0)
    df['red_streak'] = (~df['is_green']).groupby((df['is_green'] != df['is_green'].shift()).cumsum()).cumcount() + 1
    df['red_streak'] = df['red_streak'].where(~df['is_green'], 0)

    return df


def backtest_strategy(df: pd.DataFrame, strategy: str, pip_value: float = 0.0001, spread: float = 1.5) -> Dict:
    """Run backtest for a specific strategy."""

    trades = []
    current_trade = None

    start_idx = 220

    for i in range(start_idx, len(df)):
        row = df.iloc[i]
        prev = df.iloc[i-1]
        price = row['close']
        atr = row['atr']

        if pd.isna(atr) or atr == 0:
            continue

        # Check exit
        if current_trade:
            high, low = row['high'], row['low']
            direction = current_trade['direction']

            if direction == 'LONG':
                if low <= current_trade['sl']:
                    pnl = (current_trade['sl'] - current_trade['entry']) / pip_value - spread
                    trades.append({'pnl': pnl, 'exit': 'SL'})
                    current_trade = None
                elif high >= current_trade['tp']:
                    pnl = (current_trade['tp'] - current_trade['entry']) / pip_value - spread
                    trades.append({'pnl': pnl, 'exit': 'TP'})
                    current_trade = None
            else:
                if high >= current_trade['sl']:
                    pnl = (current_trade['entry'] - current_trade['sl']) / pip_value - spread
                    trades.append({'pnl': pnl, 'exit': 'SL'})
                    current_trade = None
                elif low <= current_trade['tp']:
                    pnl = (current_trade['entry'] - current_trade['tp']) / pip_value - spread
                    trades.append({'pnl': pnl, 'exit': 'TP'})
                    current_trade = None
            continue

        # Entry signals by strategy
        signal = None
        sl_mult = 1.5
        tp_mult = 1.0  # Default 1:1 for high win rate

        # ================================================================
        # ESTRATEGIA 1: Mean Reversion Bollinger
        # Compra en banda inferior, vende en media
        # ================================================================
        if strategy == "bb_mean_reversion":
            if price < row['bb_lower'] and row['rsi'] < 35:
                signal = 'LONG'
                sl_mult = 2.0
                tp_mult = 1.0  # Solo hasta la media
            elif price > row['bb_upper'] and row['rsi'] > 65:
                signal = 'SHORT'
                sl_mult = 2.0
                tp_mult = 1.0

        # ================================================================
        # ESTRATEGIA 2: RSI Extremo + Reversión
        # RSI muy extremo (< 20 o > 80) con confirmación de vela
        # ================================================================
        elif strategy == "rsi_extreme":
            if row['rsi'] < 20 and row['is_green'] and prev['rsi'] < 25:
                signal = 'LONG'
                sl_mult = 1.5
                tp_mult = 1.2
            elif row['rsi'] > 80 and not row['is_green'] and prev['rsi'] > 75:
                signal = 'SHORT'
                sl_mult = 1.5
                tp_mult = 1.2

        # ================================================================
        # ESTRATEGIA 3: Stochastic Oversold/Overbought
        # Stoch cruzando desde extremos
        # ================================================================
        elif strategy == "stoch_cross":
            prev_k = df.iloc[i-1]['stoch_k']
            prev_d = df.iloc[i-1]['stoch_d']

            # Cruce alcista desde sobreventa
            if row['stoch_k'] > row['stoch_d'] and prev_k <= prev_d and row['stoch_k'] < 30:
                signal = 'LONG'
                sl_mult = 1.5
                tp_mult = 1.5
            # Cruce bajista desde sobrecompra
            elif row['stoch_k'] < row['stoch_d'] and prev_k >= prev_d and row['stoch_k'] > 70:
                signal = 'SHORT'
                sl_mult = 1.5
                tp_mult = 1.5

        # ================================================================
        # ESTRATEGIA 4: Trend + Pullback to EMA
        # Precio toca EMA 20 en tendencia fuerte
        # ================================================================
        elif strategy == "ema_pullback":
            trend_up = row['ema_20'] > row['ema_50'] > row['ema_200']
            trend_down = row['ema_20'] < row['ema_50'] < row['ema_200']

            touched_ema = abs(row['low'] - row['ema_20']) < atr * 0.3
            bounced = row['is_green'] and row['close'] > row['ema_20']

            if trend_up and touched_ema and bounced:
                signal = 'LONG'
                sl_mult = 1.0
                tp_mult = 2.0

            touched_ema = abs(row['high'] - row['ema_20']) < atr * 0.3
            bounced = not row['is_green'] and row['close'] < row['ema_20']

            if trend_down and touched_ema and bounced:
                signal = 'SHORT'
                sl_mult = 1.0
                tp_mult = 2.0

        # ================================================================
        # ESTRATEGIA 5: MACD Divergence Confirmation
        # MACD cruce + RSI confirmando
        # ================================================================
        elif strategy == "macd_rsi":
            prev_macd = df.iloc[i-1]['macd']
            prev_signal = df.iloc[i-1]['macd_signal']

            # MACD cruce alcista + RSI no sobrecomprado
            if row['macd'] > row['macd_signal'] and prev_macd <= prev_signal:
                if row['rsi'] < 60 and row['rsi'] > 40:
                    signal = 'LONG'
                    sl_mult = 1.5
                    tp_mult = 2.0
            # MACD cruce bajista + RSI no sobrevendido
            elif row['macd'] < row['macd_signal'] and prev_macd >= prev_signal:
                if row['rsi'] > 40 and row['rsi'] < 60:
                    signal = 'SHORT'
                    sl_mult = 1.5
                    tp_mult = 2.0

        # ================================================================
        # ESTRATEGIA 6: Exhaustion Candle
        # Después de 4+ velas en una dirección, buscar reversión
        # ================================================================
        elif strategy == "exhaustion":
            if row['red_streak'] >= 4 and row['rsi'] < 35:
                # 4 velas rojas seguidas + RSI bajo = posible reversión
                signal = 'LONG'
                sl_mult = 1.0
                tp_mult = 1.5
            elif row['green_streak'] >= 4 and row['rsi'] > 65:
                signal = 'SHORT'
                sl_mult = 1.0
                tp_mult = 1.5

        # ================================================================
        # ESTRATEGIA 7: Double Bottom/Top Pattern
        # Precio hace segundo mínimo más alto
        # ================================================================
        elif strategy == "double_bottom":
            # Buscar patrón de doble suelo
            lookback = 20
            if i > lookback + 5:
                lows = df.iloc[i-lookback:i]['low'].values
                min_idx = np.argmin(lows)

                # Segundo mínimo cerca del primero pero más alto
                if min_idx < lookback - 5:  # Primer mínimo no muy reciente
                    first_low = lows[min_idx]
                    recent_low = min(lows[-5:])

                    if recent_low > first_low * 0.998 and recent_low < first_low * 1.01:
                        if row['is_green'] and row['rsi'] < 45:
                            signal = 'LONG'
                            sl_mult = 1.5
                            tp_mult = 2.5

        # ================================================================
        # ESTRATEGIA 8: Support/Resistance Bounce
        # Rebote en niveles clave (round numbers)
        # ================================================================
        elif strategy == "sr_bounce":
            # Niveles redondos (cada 50 pips para EUR/USD)
            round_level = round(price * 100) / 100  # Redondear a 0.01
            distance_to_level = abs(price - round_level)

            if distance_to_level < atr * 0.2:  # Cerca de nivel redondo
                if row['is_green'] and row['lower_wick'] > row['body']:
                    signal = 'LONG'
                    sl_mult = 1.0
                    tp_mult = 1.5
                elif not row['is_green'] and row['upper_wick'] > row['body']:
                    signal = 'SHORT'
                    sl_mult = 1.0
                    tp_mult = 1.5

        # ================================================================
        # ESTRATEGIA 9: Scalp con Trailing Mental
        # Entrada rápida, TP pequeño pero dinámico
        # ================================================================
        elif strategy == "smart_scalp":
            # Solo en tendencia clara
            trend_up = price > row['ema_50'] and row['ema_50'] > row['ema_200']
            trend_down = price < row['ema_50'] and row['ema_50'] < row['ema_200']

            # Entrada en retroceso ligero
            if trend_up and row['rsi'] < 45 and row['rsi'] > 35 and row['is_green']:
                signal = 'LONG'
                sl_mult = 0.8
                tp_mult = 1.2
            elif trend_down and row['rsi'] > 55 and row['rsi'] < 65 and not row['is_green']:
                signal = 'SHORT'
                sl_mult = 0.8
                tp_mult = 1.2

        # ================================================================
        # ESTRATEGIA 10: Conservative Trend Follow
        # Solo entrar con múltiples confirmaciones
        # ================================================================
        elif strategy == "conservative":
            trend_up = price > row['ema_200']
            macd_up = row['macd'] > row['macd_signal']
            rsi_ok = 40 < row['rsi'] < 60
            green = row['is_green']

            if trend_up and macd_up and rsi_ok and green:
                signal = 'LONG'
                sl_mult = 1.5
                tp_mult = 2.0

            trend_down = price < row['ema_200']
            macd_down = row['macd'] < row['macd_signal']

            if trend_down and macd_down and rsi_ok and not green:
                signal = 'SHORT'
                sl_mult = 1.5
                tp_mult = 2.0

        # Open trade
        if signal:
            entry = price
            if signal == 'LONG':
                sl = entry - (atr * sl_mult)
                tp = entry + (atr * tp_mult)
            else:
                sl = entry + (atr * sl_mult)
                tp = entry - (atr * tp_mult)

            current_trade = {
                'direction': signal,
                'entry': entry,
                'sl': sl,
                'tp': tp
            }

    # Calculate results
    if not trades:
        return {'trades': 0, 'win_rate': 0, 'net_pips': 0, 'pf': 0}

    wins = [t for t in trades if t['pnl'] > 0]
    losses = [t for t in trades if t['pnl'] <= 0]

    gross_profit = sum(t['pnl'] for t in wins)
    gross_loss = abs(sum(t['pnl'] for t in losses))

    return {
        'trades': len(trades),
        'wins': len(wins),
        'win_rate': round(len(wins) / len(trades) * 100, 1),
        'net_pips': round(sum(t['pnl'] for t in trades), 1),
        'pf': round(gross_profit / gross_loss, 2) if gross_loss > 0 else 0,
        'avg_win': round(gross_profit / len(wins), 1) if wins else 0,
        'avg_loss': round(gross_loss / len(losses), 1) if losses else 0
    }


def main():
    print("=" * 80)
    print("🎯 HIGH WIN RATE STRATEGY SEARCH")
    print("=" * 80)
    print("Objetivo: Encontrar estrategias con Win Rate > 55%\n")

    strategies = [
        "bb_mean_reversion",
        "rsi_extreme",
        "stoch_cross",
        "ema_pullback",
        "macd_rsi",
        "exhaustion",
        "double_bottom",
        "sr_bounce",
        "smart_scalp",
        "conservative"
    ]

    # Test en múltiples instrumentos y timeframes
    scenarios = [
        ("EUR_USD", "H1"),
        ("EUR_USD", "H4"),
        ("USD_JPY", "H4"),
        ("GBP_USD", "H4"),
    ]

    all_results = []

    for instrument, timeframe in scenarios:
        print(f"\n{'='*60}")
        print(f"📊 {instrument} {timeframe}")
        print(f"{'='*60}")

        df = load_data(instrument, timeframe)
        if len(df) < 500:
            print("   Not enough data")
            continue

        print(f"   Data: {len(df):,} candles ({df['time'].iloc[0][:10]} → {df['time'].iloc[-1][:10]})")

        df = calculate_indicators(df)
        pip_value = 0.01 if "JPY" in instrument else 0.0001

        for strat in strategies:
            result = backtest_strategy(df, strat, pip_value)
            result['strategy'] = strat
            result['instrument'] = instrument
            result['timeframe'] = timeframe
            all_results.append(result)

            if result['trades'] > 0:
                icon = "🟢" if result['win_rate'] >= 55 else ("🟡" if result['win_rate'] >= 45 else "🔴")
                pf_icon = "⭐" if result['pf'] >= 1.5 else ""
                print(f"   {icon} {strat:<22} | Trades:{result['trades']:>5} | Win:{result['win_rate']:>5}% | Net:{result['net_pips']:>8} | PF:{result['pf']:>5} {pf_icon}")

    # Summary
    print("\n" + "=" * 90)
    print("📈 TOP 10 STRATEGIES BY WIN RATE (minimum 50 trades)")
    print("=" * 90)

    filtered = [r for r in all_results if r['trades'] >= 50]
    sorted_by_wr = sorted(filtered, key=lambda x: x['win_rate'], reverse=True)[:10]

    print(f"{'Strategy':<25} {'Pair':<10} {'TF':<4} {'Trades':>7} {'Win%':>7} {'Net':>10} {'PF':>6}")
    print("-" * 90)

    for r in sorted_by_wr:
        star = "⭐" if r['pf'] >= 1.5 and r['win_rate'] >= 55 else ""
        print(f"{r['strategy']:<25} {r['instrument']:<10} {r['timeframe']:<4} {r['trades']:>7} {r['win_rate']:>6}% {r['net_pips']:>10} {r['pf']:>5} {star}")

    print("\n" + "=" * 90)
    print("📈 TOP 10 BY PROFIT FACTOR (minimum 50 trades)")
    print("=" * 90)

    sorted_by_pf = sorted(filtered, key=lambda x: x['pf'], reverse=True)[:10]

    print(f"{'Strategy':<25} {'Pair':<10} {'TF':<4} {'Trades':>7} {'Win%':>7} {'Net':>10} {'PF':>6}")
    print("-" * 90)

    for r in sorted_by_pf:
        star = "⭐" if r['pf'] >= 1.5 and r['win_rate'] >= 55 else ""
        print(f"{r['strategy']:<25} {r['instrument']:<10} {r['timeframe']:<4} {r['trades']:>7} {r['win_rate']:>6}% {r['net_pips']:>10} {r['pf']:>5} {star}")

    # Best overall
    print("\n" + "=" * 60)
    print("🏆 BEST OVERALL (Win Rate > 50% AND PF > 1.3)")
    print("=" * 60)

    best = [r for r in all_results if r['win_rate'] >= 50 and r['pf'] >= 1.3 and r['trades'] >= 30]
    best_sorted = sorted(best, key=lambda x: x['pf'] * x['win_rate'], reverse=True)

    for r in best_sorted[:5]:
        print(f"   ⭐ {r['strategy']} on {r['instrument']} {r['timeframe']}")
        print(f"      Win: {r['win_rate']}% | PF: {r['pf']} | Net: {r['net_pips']} pips | Trades: {r['trades']}")


if __name__ == "__main__":
    main()
