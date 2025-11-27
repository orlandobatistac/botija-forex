"""
Backtesting engine for Forex trading strategies
Uses OANDA historical data for strategy validation.
Dynamically uses the currently configured strategy.
"""

import logging
import pandas as pd
from typing import Dict, List, Optional, Protocol
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .oanda_client import OandaClient
from ..config import Config

logger = logging.getLogger(__name__)


class TradeDirection(Enum):
    LONG = "LONG"
    SHORT = "SHORT"


@dataclass
class BacktestTrade:
    """Single backtest trade"""
    direction: TradeDirection
    entry_time: str
    entry_price: float
    exit_time: str = ""
    exit_price: float = 0.0
    pnl_pips: float = 0.0
    is_open: bool = True
    stop_loss: float = 0.0
    take_profit: float = 0.0
    exit_reason: str = ""


@dataclass
class BacktestResult:
    """Backtest results summary"""
    instrument: str
    timeframe: str
    strategy: str
    start_date: str
    end_date: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    gross_pips: float  # Before spread
    total_pips: float  # After spread (net)
    spread_cost_pips: float  # Total spread paid
    max_drawdown_pips: float
    win_rate: float
    profit_factor: float
    avg_win_pips: float
    avg_loss_pips: float
    trades: List[BacktestTrade] = field(default_factory=list)


class StrategyProtocol(Protocol):
    """Protocol that all strategies must implement for backtesting."""

    def generate_signal(self, df: pd.DataFrame) -> object:
        """Generate a signal from DataFrame with OHLC data."""
        ...


class Backtester:
    """
    Dynamic backtesting engine using OANDA historical data.
    Automatically uses the currently configured strategy.
    """

    def __init__(
        self,
        oanda_client: OandaClient,
        instrument: str = "EUR_USD",
        strategy: Optional[StrategyProtocol] = None
    ):
        """
        Initialize backtester.

        Args:
            oanda_client: OANDA API client
            instrument: Currency pair
            strategy: Strategy instance (if None, uses configured strategy)
        """
        self.oanda = oanda_client
        self.instrument = instrument
        self.logger = logger

        # Pip value for calculations
        self.pip_value = 0.0001 if "JPY" not in instrument else 0.01
        
        # Spread cost per trade (realistic for major pairs)
        self.spread_pips = 1.5  # EUR_USD typical spread

        # Load strategy
        self.strategy = strategy or self._load_configured_strategy()
        self.strategy_name = self.strategy.__class__.__name__ if self.strategy else "Unknown"

    def _load_configured_strategy(self) -> Optional[StrategyProtocol]:
        """Load the currently configured strategy."""
        try:
            use_triple_ema = getattr(Config, 'USE_TRIPLE_EMA_STRATEGY', True)

            if use_triple_ema:
                from .strategies.triple_ema import TripleEMAStrategy
                return TripleEMAStrategy(
                    rr_ratio=getattr(Config, 'TRIPLE_EMA_RR_RATIO', 2.0),
                    use_adx_filter=True,
                    use_slope_filter=True
                )

            # Add more strategies here as they are implemented
            # elif getattr(Config, 'USE_OTHER_STRATEGY', False):
            #     from .strategies.other import OtherStrategy
            #     return OtherStrategy()

            # Default fallback
            from .strategies.triple_ema import TripleEMAStrategy
            return TripleEMAStrategy()

        except Exception as e:
            self.logger.error(f"Failed to load strategy: {e}")
            return None

    def _price_to_pips(self, price_diff: float) -> float:
        """Convert price difference to pips"""
        return price_diff / self.pip_value

    def _pips_to_price(self, pips: float) -> float:
        """Convert pips to price difference"""
        return pips * self.pip_value

    def _candles_to_dataframe(self, candles: List[Dict]) -> pd.DataFrame:
        """Convert OANDA candles to pandas DataFrame."""
        df = pd.DataFrame(candles)
        for col in ['open', 'high', 'low', 'close']:
            if col in df.columns:
                df[col] = df[col].astype(float)
        return df

    def run(
        self,
        timeframe: str = "H4",
        candle_count: int = 500
    ) -> BacktestResult:
        """
        Run backtest on historical data using configured strategy.

        Args:
            timeframe: Candle granularity (H1, H4, D)
            candle_count: Number of historical candles

        Returns:
            BacktestResult with strategy performance
        """
        self.logger.info(
            f"🔬 Starting backtest: {self.instrument} {timeframe} "
            f"({candle_count} candles) - Strategy: {self.strategy_name}"
        )

        if not self.strategy:
            self.logger.error("No strategy loaded")
            return self._empty_result(timeframe)

        try:
            # Get historical data
            candles = self.oanda.get_candles(
                instrument=self.instrument,
                granularity=timeframe,
                count=candle_count
            )

            if not candles or len(candles) < 250:
                self.logger.error(f"Insufficient data: {len(candles) if candles else 0} candles")
                return self._empty_result(timeframe)

            # Convert to DataFrame
            df = self._candles_to_dataframe(candles)
            times = [c['time'] for c in candles]

            # Trading simulation
            trades: List[BacktestTrade] = []
            current_trade: Optional[BacktestTrade] = None

            # Need enough data for EMA 200
            start_idx = 250

            for i in range(start_idx, len(candles)):
                # Get slice of data up to current candle (no lookahead)
                df_slice = df.iloc[:i+1].copy()

                current_price = float(df.iloc[i]['close'])
                current_high = float(df.iloc[i]['high'])
                current_low = float(df.iloc[i]['low'])
                current_time = times[i]

                # Get signal from strategy
                signal = self.strategy.generate_signal(df_slice)

                # Check open position
                if current_trade and current_trade.is_open:
                    closed = self._check_exit(
                        current_trade, current_high, current_low,
                        current_price, current_time
                    )

                    if closed:
                        trades.append(current_trade)
                        current_trade = None

                # Entry signals (only if no open trade)
                if not current_trade and signal:
                    direction = getattr(signal, 'direction', None)
                    confidence = getattr(signal, 'confidence', 0)
                    entry_price = getattr(signal, 'entry_price', current_price)
                    stop_loss = getattr(signal, 'stop_loss', None)
                    take_profit = getattr(signal, 'take_profit', None)

                    if direction == 'LONG' and confidence >= 0.6:
                        current_trade = BacktestTrade(
                            direction=TradeDirection.LONG,
                            entry_time=current_time,
                            entry_price=entry_price or current_price,
                            stop_loss=stop_loss or (current_price - self._pips_to_price(50)),
                            take_profit=take_profit or (current_price + self._pips_to_price(100))
                        )

                    elif direction == 'SHORT' and confidence >= 0.6:
                        current_trade = BacktestTrade(
                            direction=TradeDirection.SHORT,
                            entry_time=current_time,
                            entry_price=entry_price or current_price,
                            stop_loss=stop_loss or (current_price + self._pips_to_price(50)),
                            take_profit=take_profit or (current_price - self._pips_to_price(100))
                        )

            # Close any remaining open trade at last price
            if current_trade and current_trade.is_open:
                last_price = float(df.iloc[-1]['close'])
                current_trade.exit_price = last_price
                current_trade.exit_time = times[-1]
                if current_trade.direction == TradeDirection.LONG:
                    current_trade.pnl_pips = self._price_to_pips(last_price - current_trade.entry_price)
                else:
                    current_trade.pnl_pips = self._price_to_pips(current_trade.entry_price - last_price)
                current_trade.exit_reason = "END_OF_DATA"
                current_trade.is_open = False
                trades.append(current_trade)

            # Calculate statistics
            return self._calculate_results(trades, timeframe, times[0], times[-1])

        except Exception as e:
            self.logger.error(f"Backtest error: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return self._empty_result(timeframe)

    def _check_exit(
        self,
        trade: BacktestTrade,
        high: float,
        low: float,
        close: float,
        time: str
    ) -> bool:
        """Check if trade should exit. Returns True if closed."""

        if trade.direction == TradeDirection.LONG:
            # Stop loss hit
            if low <= trade.stop_loss:
                trade.exit_price = trade.stop_loss
                trade.exit_time = time
                trade.pnl_pips = self._price_to_pips(trade.stop_loss - trade.entry_price)
                trade.exit_reason = "STOP_LOSS"
                trade.is_open = False
                return True
            # Take profit hit
            elif high >= trade.take_profit:
                trade.exit_price = trade.take_profit
                trade.exit_time = time
                trade.pnl_pips = self._price_to_pips(trade.take_profit - trade.entry_price)
                trade.exit_reason = "TAKE_PROFIT"
                trade.is_open = False
                return True

        elif trade.direction == TradeDirection.SHORT:
            # Stop loss hit (price goes up)
            if high >= trade.stop_loss:
                trade.exit_price = trade.stop_loss
                trade.exit_time = time
                trade.pnl_pips = self._price_to_pips(trade.entry_price - trade.stop_loss)
                trade.exit_reason = "STOP_LOSS"
                trade.is_open = False
                return True
            # Take profit hit (price goes down)
            elif low <= trade.take_profit:
                trade.exit_price = trade.take_profit
                trade.exit_time = time
                trade.pnl_pips = self._price_to_pips(trade.entry_price - trade.take_profit)
                trade.exit_reason = "TAKE_PROFIT"
                trade.is_open = False
                return True

        return False

    def _calculate_results(
        self,
        trades: List[BacktestTrade],
        timeframe: str,
        start_date: str,
        end_date: str
    ) -> BacktestResult:
        """Calculate backtest statistics"""

        if not trades:
            return self._empty_result(timeframe)

        winning_trades = [t for t in trades if t.pnl_pips > 0]
        losing_trades = [t for t in trades if t.pnl_pips <= 0]

        gross_pips = sum(t.pnl_pips for t in trades)
        spread_cost = self.spread_pips * len(trades)
        net_pips = gross_pips - spread_cost
        
        gross_profit = sum(t.pnl_pips for t in winning_trades)
        gross_loss = abs(sum(t.pnl_pips for t in losing_trades))

        # Calculate max drawdown (including spread)
        cumulative_pips = 0.0
        peak_pips = 0.0
        max_drawdown = 0.0

        for trade in trades:
            cumulative_pips += (trade.pnl_pips - self.spread_pips)
            if cumulative_pips > peak_pips:
                peak_pips = cumulative_pips
            drawdown = peak_pips - cumulative_pips
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        result = BacktestResult(
            instrument=self.instrument,
            timeframe=timeframe,
            strategy=self.strategy_name,
            start_date=start_date,
            end_date=end_date,
            total_trades=len(trades),
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            gross_pips=round(gross_pips, 2),
            total_pips=round(net_pips, 2),
            spread_cost_pips=round(spread_cost, 2),
            max_drawdown_pips=round(max_drawdown, 2),
            win_rate=round(len(winning_trades) / len(trades) * 100, 2) if trades else 0,
            profit_factor=round(gross_profit / gross_loss, 2) if gross_loss > 0 else 0,
            avg_win_pips=round(gross_profit / len(winning_trades), 2) if winning_trades else 0,
            avg_loss_pips=round(gross_loss / len(losing_trades), 2) if losing_trades else 0,
            trades=trades
        )

        self.logger.info(
            f"📊 Backtest complete [{self.strategy_name}]: {result.total_trades} trades, "
            f"{result.win_rate}% win rate, {result.total_pips} pips, "
            f"PF: {result.profit_factor}"
        )

        return result

    def _empty_result(self, timeframe: str) -> BacktestResult:
        """Return empty result on error"""
        return BacktestResult(
            instrument=self.instrument,
            timeframe=timeframe,
            strategy=self.strategy_name,
            start_date="",
            end_date="",
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            gross_pips=0,
            total_pips=0,
            spread_cost_pips=0,
            max_drawdown_pips=0,
            win_rate=0,
            profit_factor=0,
            avg_win_pips=0,
            avg_loss_pips=0
        )

    def to_dict(self, result: BacktestResult) -> Dict:
        """Convert result to JSON-serializable dict"""
        return {
            "instrument": result.instrument,
            "timeframe": result.timeframe,
            "strategy": result.strategy,
            "start_date": result.start_date,
            "end_date": result.end_date,
            "total_trades": result.total_trades,
            "winning_trades": result.winning_trades,
            "losing_trades": result.losing_trades,
            "gross_pips": result.gross_pips,
            "total_pips": result.total_pips,
            "spread_cost_pips": result.spread_cost_pips,
            "max_drawdown_pips": result.max_drawdown_pips,
            "win_rate": result.win_rate,
            "profit_factor": result.profit_factor,
            "avg_win_pips": result.avg_win_pips,
            "avg_loss_pips": result.avg_loss_pips,
            "trades": [
                {
                    "direction": t.direction.value,
                    "entry_time": t.entry_time,
                    "entry_price": round(t.entry_price, 5),
                    "exit_time": t.exit_time,
                    "exit_price": round(t.exit_price, 5),
                    "pnl_pips": round(t.pnl_pips, 2),
                    "exit_reason": t.exit_reason
                }
                for t in result.trades
            ]
        }
