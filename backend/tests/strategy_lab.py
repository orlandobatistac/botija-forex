"""
Strategy Lab - Test different strategy configurations locally
=============================================================
Run: cd backend && python -m tests.strategy_lab
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import pandas as pd
import numpy as np

# Import OANDA client
from app.services.oanda_client import OandaClient
from app.config import Config


@dataclass
class LabResult:
    """Backtest result for lab testing."""
    name: str
    params: Dict[str, Any]
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    gross_pips: float
    net_pips: float
    profit_factor: float
    max_drawdown: float
    avg_win: float
    avg_loss: float


class StrategyLab:
    """Lab for testing strategy variations."""

    def __init__(self):
        self.oanda = OandaClient(
            api_key=Config.OANDA_API_KEY,
            account_id=Config.OANDA_ACCOUNT_ID,
            environment=Config.OANDA_ENVIRONMENT
        )
        self.spread_pips = 1.5
        self.pip_value = 0.0001

    def fetch_data(self, instrument: str = "EUR_USD", timeframe: str = "H1", count: int = 5000) -> pd.DataFrame:
        """Fetch historical data from OANDA."""
        print(f"📊 Fetching {count} {timeframe} candles for {instrument}...")
        candles = self.oanda.get_candles(instrument, timeframe, count)

        df = pd.DataFrame(candles)
        for col in ['open', 'high', 'low', 'close']:
            df[col] = df[col].astype(float)

        print(f"   Got {len(df)} candles from {df['time'].iloc[0][:10]} to {df['time'].iloc[-1][:10]}")
        return df

    def calculate_indicators(self, df: pd.DataFrame, config: Dict) -> pd.DataFrame:
        """Calculate all indicators needed."""
        df = df.copy()

        # RSI
        rsi_period = config.get('rsi_period', 14)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
        rs = gain / (loss + 0.0001)
        df['rsi'] = 100 - (100 / (1 + rs))

        # EMA 200
        df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()

        # ATR
        atr_period = config.get('atr_period', 14)
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift())
        low_close = abs(df['low'] - df['close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr'] = tr.rolling(atr_period).mean()

        # ADX (if needed)
        if config.get('use_adx', False):
            df['adx'] = self._calculate_adx(df, config.get('adx_period', 14))

        return df

    def _calculate_adx(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate ADX."""
        plus_dm = df['high'].diff()
        minus_dm = -df['low'].diff()

        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)

        tr = pd.concat([
            df['high'] - df['low'],
            abs(df['high'] - df['close'].shift()),
            abs(df['low'] - df['close'].shift())
        ], axis=1).max(axis=1)

        atr = tr.rolling(period).mean()
        plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(period).mean() / atr)

        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 0.0001)
        adx = dx.rolling(period).mean()

        return adx

    def run_backtest(self, df: pd.DataFrame, config: Dict) -> LabResult:
        """Run backtest with given configuration."""
        df = self.calculate_indicators(df, config)

        # Config parameters
        rsi_oversold = config.get('rsi_oversold', 30)
        rsi_overbought = config.get('rsi_overbought', 70)
        atr_sl_mult = config.get('atr_sl_multiplier', 1.5)
        atr_tp_mult = config.get('atr_tp_multiplier', 2.5)
        use_adx = config.get('use_adx', False)
        min_adx = config.get('min_adx', 25)
        require_trend = config.get('require_trend', True)

        trades = []
        current_trade = None

        # Start after indicators are ready
        start_idx = 220

        for i in range(start_idx, len(df)):
            row = df.iloc[i]
            price = row['close']
            rsi = row['rsi']
            ema_200 = row['ema_200']
            atr = row['atr']
            adx = row.get('adx', 100) if use_adx else 100

            if pd.isna(rsi) or pd.isna(ema_200) or pd.isna(atr):
                continue

            # Check exit for open trade
            if current_trade:
                high = row['high']
                low = row['low']

                if current_trade['direction'] == 'LONG':
                    if low <= current_trade['sl']:
                        pnl = (current_trade['sl'] - current_trade['entry']) / self.pip_value
                        trades.append({'pnl': pnl, 'exit': 'SL'})
                        current_trade = None
                    elif high >= current_trade['tp']:
                        pnl = (current_trade['tp'] - current_trade['entry']) / self.pip_value
                        trades.append({'pnl': pnl, 'exit': 'TP'})
                        current_trade = None
                else:  # SHORT
                    if high >= current_trade['sl']:
                        pnl = (current_trade['entry'] - current_trade['sl']) / self.pip_value
                        trades.append({'pnl': pnl, 'exit': 'SL'})
                        current_trade = None
                    elif low <= current_trade['tp']:
                        pnl = (current_trade['entry'] - current_trade['tp']) / self.pip_value
                        trades.append({'pnl': pnl, 'exit': 'TP'})
                        current_trade = None
                continue

            # Check for new signal
            bias = "BULLISH" if price > ema_200 * 1.001 else ("BEARISH" if price < ema_200 * 0.999 else "NEUTRAL")

            # ADX filter
            if use_adx and adx < min_adx:
                continue

            # LONG signal
            if rsi < rsi_oversold:
                if not require_trend or bias == "BULLISH":
                    sl = price - (atr * atr_sl_mult)
                    tp = price + (atr * atr_tp_mult)
                    current_trade = {
                        'direction': 'LONG',
                        'entry': price,
                        'sl': sl,
                        'tp': tp
                    }

            # SHORT signal
            elif rsi > rsi_overbought:
                if not require_trend or bias == "BEARISH":
                    sl = price + (atr * atr_sl_mult)
                    tp = price - (atr * atr_tp_mult)
                    current_trade = {
                        'direction': 'SHORT',
                        'entry': price,
                        'sl': sl,
                        'tp': tp
                    }

        # Calculate results
        if not trades:
            return LabResult(
                name=config.get('name', 'Unknown'),
                params=config,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=0,
                gross_pips=0,
                net_pips=0,
                profit_factor=0,
                max_drawdown=0,
                avg_win=0,
                avg_loss=0
            )

        winning = [t for t in trades if t['pnl'] > 0]
        losing = [t for t in trades if t['pnl'] <= 0]

        gross_pips = sum(t['pnl'] for t in trades)
        spread_cost = len(trades) * self.spread_pips
        net_pips = gross_pips - spread_cost

        gross_profit = sum(t['pnl'] for t in winning)
        gross_loss = abs(sum(t['pnl'] for t in losing))

        # Max drawdown
        cumulative = 0
        peak = 0
        max_dd = 0
        for t in trades:
            cumulative += t['pnl'] - self.spread_pips
            if cumulative > peak:
                peak = cumulative
            dd = peak - cumulative
            if dd > max_dd:
                max_dd = dd

        return LabResult(
            name=config.get('name', 'Unknown'),
            params=config,
            total_trades=len(trades),
            winning_trades=len(winning),
            losing_trades=len(losing),
            win_rate=round(len(winning) / len(trades) * 100, 1) if trades else 0,
            gross_pips=round(gross_pips, 1),
            net_pips=round(net_pips, 1),
            profit_factor=round(gross_profit / gross_loss, 2) if gross_loss > 0 else 0,
            max_drawdown=round(max_dd, 1),
            avg_win=round(gross_profit / len(winning), 1) if winning else 0,
            avg_loss=round(gross_loss / len(losing), 1) if losing else 0
        )

    def print_result(self, r: LabResult):
        """Print formatted result."""
        pf_color = "🟢" if r.profit_factor >= 1.5 else ("🟡" if r.profit_factor >= 1.0 else "🔴")
        wr_color = "🟢" if r.win_rate >= 40 else ("🟡" if r.win_rate >= 30 else "🔴")

        print(f"\n{'='*60}")
        print(f"📊 {r.name}")
        print(f"{'='*60}")
        print(f"   Trades: {r.total_trades} ({r.winning_trades}W / {r.losing_trades}L)")
        print(f"   {wr_color} Win Rate: {r.win_rate}%")
        print(f"   Gross Pips: {r.gross_pips}")
        print(f"   Net Pips: {r.net_pips} (after {r.total_trades * self.spread_pips} spread)")
        print(f"   {pf_color} Profit Factor: {r.profit_factor}")
        print(f"   Max Drawdown: {r.max_drawdown} pips")
        print(f"   Avg Win: +{r.avg_win} | Avg Loss: -{r.avg_loss}")

        # R:R efectivo
        if r.avg_loss > 0:
            rr = round(r.avg_win / r.avg_loss, 2)
            print(f"   R:R Efectivo: 1:{rr}")

    def compare_results(self, results: List[LabResult]):
        """Print comparison table."""
        print(f"\n{'='*80}")
        print("📈 COMPARISON TABLE")
        print(f"{'='*80}")
        print(f"{'Strategy':<25} {'Trades':>7} {'Win%':>7} {'Net Pips':>10} {'PF':>6} {'MaxDD':>8}")
        print(f"{'-'*80}")

        # Sort by profit factor
        sorted_results = sorted(results, key=lambda x: x.profit_factor, reverse=True)

        for r in sorted_results:
            pf_mark = "⭐" if r.profit_factor >= 1.5 else ""
            print(f"{r.name:<25} {r.total_trades:>7} {r.win_rate:>6}% {r.net_pips:>10} {r.profit_factor:>5} {r.max_drawdown:>7} {pf_mark}")

    def load_from_db(self, instrument: str, timeframe: str, db_path: str = "tests/historical_data.db") -> pd.DataFrame:
        """Load data from SQLite database."""
        import sqlite3

        conn = sqlite3.connect(db_path)
        query = f"""
            SELECT time, open, high, low, close, volume
            FROM candles
            WHERE instrument = ? AND timeframe = ?
            ORDER BY time ASC
        """
        df = pd.read_sql_query(query, conn, params=(instrument, timeframe))
        conn.close()

        if len(df) > 0:
            print(f"📂 Loaded {len(df):,} candles from DB: {instrument} {timeframe}")
            print(f"   Period: {df['time'].iloc[0][:10]} → {df['time'].iloc[-1][:10]}")

        return df


def main():
    print("🧪 Strategy Lab - 5 YEAR BACKTEST")
    print("=" * 60)

    lab = StrategyLab()

    # Best strategy configs to test
    best_configs = [
        {
            "name": "RSI+EMA200 Baseline",
            "rsi_oversold": 30,
            "rsi_overbought": 70,
            "atr_sl_multiplier": 1.5,
            "atr_tp_multiplier": 2.5,
            "use_adx": False,
            "require_trend": True
        },
        {
            "name": "RSI+EMA200 + ADX>25",
            "rsi_oversold": 30,
            "rsi_overbought": 70,
            "atr_sl_multiplier": 1.5,
            "atr_tp_multiplier": 2.5,
            "use_adx": True,
            "min_adx": 25,
            "require_trend": True
        },
    ]

    # Test scenarios - using DB data (5 years)
    scenarios = [
        {"instrument": "EUR_USD", "timeframe": "H1"},
        {"instrument": "EUR_USD", "timeframe": "H4"},
        {"instrument": "USD_JPY", "timeframe": "H1"},
        {"instrument": "USD_JPY", "timeframe": "H4"},
        {"instrument": "GBP_USD", "timeframe": "H1"},
        {"instrument": "GBP_USD", "timeframe": "H4"},
    ]

    all_results = []

    for scenario in scenarios:
        instrument = scenario["instrument"]
        timeframe = scenario["timeframe"]

        print(f"\n{'='*70}")
        print(f"🔬 SCENARIO: {instrument} {timeframe} (5 YEARS)")
        print(f"{'='*70}")

        # Adjust pip value for JPY pairs
        lab.pip_value = 0.01 if "JPY" in instrument else 0.0001

        try:
            # Load from database
            df = lab.load_from_db(instrument, timeframe)

            if len(df) < 500:
                print(f"   ⚠️ Not enough data, skipping...")
                continue

            for config in best_configs:
                config_copy = config.copy()
                config_copy["name"] = f"{instrument} {timeframe} - {config['name']}"
                result = lab.run_backtest(df, config_copy)
                lab.print_result(result)
                all_results.append(result)
        except Exception as e:
            print(f"   ❌ Error: {e}")
            import traceback
            traceback.print_exc()

    # Final comparison across all scenarios
    print(f"\n{'='*90}")
    print("📈 FULL COMPARISON - ALL SCENARIOS (5 YEARS)")
    print(f"{'='*90}")
    lab.compare_results(all_results)

    # Summary by timeframe
    print(f"\n{'='*70}")
    print("📊 BEST BY TIMEFRAME (sorted by Profit Factor)")
    print(f"{'='*70}")

    timeframes = ["H1", "H4", "D"]
    for tf in timeframes:
        tf_results = [r for r in all_results if tf in r.name]
        if tf_results:
            best = max(tf_results, key=lambda x: x.profit_factor)
            print(f"\n🏆 {tf}: {best.name}")
            print(f"   PF: {best.profit_factor} | Win: {best.win_rate}% | Net: {best.net_pips} pips | DD: {best.max_drawdown}")

    print("\n✅ Lab complete!")


if __name__ == "__main__":
    main()
