"""
Out-of-Sample Validation Test
=============================
Prueba final con datos de 2025 que NUNCA fueron parte del entrenamiento.

Si los parámetros del Walk-Forward funcionan aquí, NO hay overfitting.
"""

import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path


def calculate_indicators(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """Calcular indicadores"""
    df = df.copy()

    # EMA 200
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()

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
    atr_adx = tr.rolling(14).mean()

    plus_di = 100 * (plus_dm.rolling(14).mean() / atr_adx)
    minus_di = 100 * (minus_dm.rolling(14).mean() / atr_adx)
    di_sum = plus_di + minus_di
    di_sum = di_sum.replace(0, np.nan)
    dx = 100 * ((plus_di - minus_di).abs() / di_sum)
    df['adx'] = dx.rolling(14).mean()

    return df


def backtest_oos(df: pd.DataFrame, params: dict, test_year: int) -> dict:
    """
    Backtest Out-of-Sample.

    Usa datos HASTA test_year-1 para indicadores,
    pero solo cuenta trades de test_year.
    """
    pip_mult = 10000
    spread = 1.0

    df = calculate_indicators(df, params)
    df['year'] = df['time'].dt.year

    # Encontrar inicio del año de test
    test_start_idx = df[df['year'] == test_year].index[0]

    trades = []
    position = None

    for i in range(max(200, test_start_idx), len(df)):
        row = df.iloc[i]

        # Solo contar trades del año de test
        if row['year'] != test_year and position is None:
            continue

        # Gestionar posición
        if position:
            exit_price = None
            exit_reason = None

            if position['direction'] == 'long':
                if row['low'] <= position['sl']:
                    exit_price = position['sl']
                    exit_reason = 'SL'
                elif row['high'] >= position['tp']:
                    exit_price = position['tp']
                    exit_reason = 'TP'
            else:
                if row['high'] >= position['sl']:
                    exit_price = position['sl']
                    exit_reason = 'SL'
                elif row['low'] <= position['tp']:
                    exit_price = position['tp']
                    exit_reason = 'TP'

            if exit_price:
                if position['direction'] == 'long':
                    pips = (exit_price - position['entry']) * pip_mult - spread
                else:
                    pips = (position['entry'] - exit_price) * pip_mult - spread

                trades.append({
                    'entry_date': position['entry_date'],
                    'exit_date': row['time'],
                    'direction': position['direction'],
                    'pips': pips,
                    'exit_reason': exit_reason
                })
                position = None
                continue

        # Nueva entrada (solo en año de test y con ADX fuerte)
        if position is None and row['year'] == test_year:
            if pd.isna(row['adx']) or row['adx'] < params['adx_threshold']:
                continue

            atr = row['atr']
            close = row['close']

            if row['macd_cross_up'] and close > row['ema_200']:
                prev_macd = df.iloc[i-1]['macd']
                if prev_macd < 0:
                    position = {
                        'entry': close,
                        'entry_date': row['time'],
                        'direction': 'long',
                        'sl': close - (atr * params['atr_sl_mult']),
                        'tp': close + (atr * params['atr_sl_mult'] * params['rr_ratio'])
                    }

            elif row['macd_cross_down'] and close < row['ema_200']:
                prev_macd = df.iloc[i-1]['macd']
                if prev_macd > 0:
                    position = {
                        'entry': close,
                        'entry_date': row['time'],
                        'direction': 'short',
                        'sl': close + (atr * params['atr_sl_mult']),
                        'tp': close - (atr * params['atr_sl_mult'] * params['rr_ratio'])
                    }

    if not trades:
        return {'trades': 0, 'pf': 0, 'pips': 0, 'win_rate': 0}

    wins = [t for t in trades if t['pips'] > 0]
    losses = [t for t in trades if t['pips'] <= 0]

    total_wins = sum(t['pips'] for t in wins) if wins else 0
    total_losses = abs(sum(t['pips'] for t in losses)) if losses else 0.001

    return {
        'trades': len(trades),
        'wins': len(wins),
        'losses': len(losses),
        'pf': total_wins / total_losses,
        'pips': sum(t['pips'] for t in trades),
        'win_rate': len(wins) / len(trades) * 100,
        'trade_details': trades
    }


def run_oos_validation():
    """Ejecutar validación Out-of-Sample"""
    print("=" * 70)
    print("🔬 OUT-OF-SAMPLE VALIDATION TEST")
    print("=" * 70)
    print()
    print("Objetivo: Probar que los parámetros del Walk-Forward NO son overfitting")
    print("Método: Aplicar parámetros a datos que NUNCA fueron usados para optimizar")
    print()

    # Cargar datos
    db_path = Path(__file__).parent / "historical_data.db"
    conn = sqlite3.connect(db_path)
    df = pd.read_sql(
        "SELECT time, open, high, low, close FROM candles "
        "WHERE instrument='EUR_USD' AND timeframe='D' ORDER BY time",
        conn
    )
    conn.close()
    df['time'] = pd.to_datetime(df['time'])

    print(f"📊 Datos cargados: {len(df)} días")
    print(f"   Período: {df['time'].min().date()} → {df['time'].max().date()}")
    print()

    # Parámetros del Walk-Forward (EUR_USD)
    wf_params = {
        'adx_threshold': 20,
        'atr_sl_mult': 2.0,
        'rr_ratio': 2.5,
        'macd_fast': 12,
        'macd_slow': 26
    }

    print(f"🔧 Parámetros Walk-Forward: ADX>{wf_params['adx_threshold']}, "
          f"ATR×{wf_params['atr_sl_mult']}, R:R 1:{wf_params['rr_ratio']}")
    print()

    # Test en cada año
    print("=" * 70)
    print("📈 RESULTADOS POR AÑO")
    print("=" * 70)
    print()
    print(f"{'Año':<6} {'Trades':>7} {'Wins':>6} {'Losses':>7} {'Win%':>7} {'Pips':>10} {'PF':>6} {'Status':>10}")
    print("-" * 70)

    df['year'] = df['time'].dt.year
    years = sorted(df['year'].unique())

    total_pips = 0
    total_trades = 0
    profitable_years = 0

    for year in years:
        if year < 2020:  # Skip años con pocos datos
            continue

        result = backtest_oos(df, wf_params, year)

        if result['trades'] == 0:
            print(f"{year:<6} {'No trades':>7}")
            continue

        status = "✅ PASS" if result['pf'] >= 1.0 else "❌ FAIL"
        if result['pf'] >= 1.0:
            profitable_years += 1

        total_pips += result['pips']
        total_trades += result['trades']

        print(f"{year:<6} {result['trades']:>7} {result['wins']:>6} {result['losses']:>7} "
              f"{result['win_rate']:>6.1f}% {result['pips']:>10.1f} {result['pf']:>6.2f} {status:>10}")

    print("-" * 70)
    print(f"{'TOTAL':<6} {total_trades:>7} {'':<6} {'':<7} {'':<7} {total_pips:>10.1f}")
    print()

    # Veredicto final
    print("=" * 70)
    print("🎯 VEREDICTO FINAL")
    print("=" * 70)

    years_tested = len([y for y in years if y >= 2020])
    consistency = profitable_years / years_tested * 100 if years_tested > 0 else 0

    print(f"   Años testeados: {years_tested}")
    print(f"   Años rentables: {profitable_years}")
    print(f"   Consistencia: {consistency:.0f}%")
    print(f"   Total pips: {total_pips:.1f}")
    print()

    if consistency >= 80:
        print("   🏆 CONCLUSIÓN: Los parámetros son ROBUSTOS, NO hay overfitting")
        print("   ✅ Listos para producción")
    elif consistency >= 60:
        print("   🟡 CONCLUSIÓN: Parámetros ACEPTABLES con algo de variabilidad")
        print("   ⚠️ Monitorear en producción")
    else:
        print("   🔴 CONCLUSIÓN: Posible OVERFITTING detectado")
        print("   ❌ Requiere más análisis")

    print()

    # Mostrar detalle de trades 2025 (el más reciente)
    print("=" * 70)
    print("📋 DETALLE TRADES 2025 (datos más recientes)")
    print("=" * 70)

    result_2025 = backtest_oos(df, wf_params, 2025)

    if result_2025['trades'] > 0:
        for t in result_2025['trade_details']:
            indicator = "✅" if t['pips'] > 0 else "❌"
            print(f"   {indicator} {t['entry_date'].strftime('%Y-%m-%d')} → {t['exit_date'].strftime('%Y-%m-%d')} "
                  f"| {t['direction'].upper():<5} | {t['exit_reason']:<2} | {t['pips']:>7.1f} pips")
    else:
        print("   No trades en 2025")


if __name__ == "__main__":
    run_oos_validation()
