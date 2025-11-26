"""
Backtesting engine for Forex trading strategies
Uses OANDA historical data for strategy validation
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from .oanda_client import OandaClient
from .technical_indicators import TechnicalIndicators

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
    start_date: str
    end_date: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    total_pips: float
    max_drawdown_pips: float
    win_rate: float
    profit_factor: float
    avg_win_pips: float
    avg_loss_pips: float
    trades: List[BacktestTrade] = field(default_factory=list)


class Backtester:
    """
    Simple backtesting engine using OANDA historical data.
    Tests EMA crossover + RSI strategy.
    """

    def __init__(
        self,
        oanda_client: OandaClient,
        instrument: str = "EUR_USD",
        stop_loss_pips: float = 50.0,
        take_profit_pips: float = 100.0
    ):
        """
        Initialize backtester.

        Args:
            oanda_client: OANDA API client
            instrument: Currency pair
            stop_loss_pips: Stop loss in pips
            take_profit_pips: Take profit in pips
        """
        self.oanda = oanda_client
        self.instrument = instrument
        self.stop_loss_pips = stop_loss_pips
        self.take_profit_pips = take_profit_pips
        self.indicators = TechnicalIndicators()
        self.logger = logger

        # Pip value for calculations
        self.pip_value = 0.0001 if "JPY" not in instrument else 0.01

    def _price_to_pips(self, price_diff: float) -> float:
        """Convert price difference to pips"""
        return price_diff / self.pip_value

    def _pips_to_price(self, pips: float) -> float:
        """Convert pips to price difference"""
        return pips * self.pip_value

    def run(
        self,
        timeframe: str = "H4",
        candle_count: int = 500,
        ema_fast: int = 20,
        ema_slow: int = 50,
        rsi_period: int = 14
    ) -> BacktestResult:
        """
        Run backtest on historical data.

        Args:
            timeframe: Candle granularity (H1, H4, D)
            candle_count: Number of historical candles
            ema_fast: Fast EMA period
            ema_slow: Slow EMA period
            rsi_period: RSI period

        Returns:
            BacktestResult with strategy performance
        """
        self.logger.info(f"🔬 Starting backtest: {self.instrument} {timeframe} ({candle_count} candles)")

        try:
            # Get historical data
            candles = self.oanda.get_candles(
                instrument=self.instrument,
                granularity=timeframe,
                count=candle_count
            )

            if not candles or len(candles) < ema_slow + 10:
                self.logger.error(f"Insufficient data: {len(candles) if candles else 0} candles")
                return self._empty_result(timeframe)

            # Extract prices
            closes = [c['close'] for c in candles]
            highs = [c['high'] for c in candles]
            lows = [c['low'] for c in candles]
            times = [c['time'] for c in candles]

            # Calculate indicators
            ema_fast_values = self.indicators.calculate_ema(closes, ema_fast)
            ema_slow_values = self.indicators.calculate_ema(closes, ema_slow)
            rsi_values = self.indicators.calculate_rsi(closes, rsi_period)

            # Trading simulation
            trades: List[BacktestTrade] = []
            current_trade: Optional[BacktestTrade] = None

            # Start from where all indicators are available
            start_idx = max(ema_slow, rsi_period) + 1

            for i in range(start_idx, len(candles)):
                current_price = closes[i]
                current_high = highs[i]
                current_low = lows[i]
                current_time = times[i]

                ema_f = ema_fast_values[i]
                ema_s = ema_slow_values[i]
                rsi = rsi_values[i]

                prev_ema_f = ema_fast_values[i - 1]
                prev_ema_s = ema_slow_values[i - 1]

                # Check open position
                if current_trade and current_trade.is_open:
                    # Check stop loss / take profit for LONG
                    if current_trade.direction == TradeDirection.LONG:
                        # Stop loss hit
                        if current_low <= current_trade.stop_loss:
                            current_trade.exit_price = current_trade.stop_loss
                            current_trade.exit_time = current_time
                            current_trade.pnl_pips = -self.stop_loss_pips
                            current_trade.exit_reason = "STOP_LOSS"
                            current_trade.is_open = False
                        # Take profit hit
                        elif current_high >= current_trade.take_profit:
                            current_trade.exit_price = current_trade.take_profit
                            current_trade.exit_time = current_time
                            current_trade.pnl_pips = self.take_profit_pips
                            current_trade.exit_reason = "TAKE_PROFIT"
                            current_trade.is_open = False
                        # Exit on bearish crossover
                        elif ema_f < ema_s and prev_ema_f >= prev_ema_s:
                            current_trade.exit_price = current_price
                            current_trade.exit_time = current_time
                            current_trade.pnl_pips = self._price_to_pips(
                                current_price - current_trade.entry_price
                            )
                            current_trade.exit_reason = "SIGNAL"
                            current_trade.is_open = False

                    # Check stop loss / take profit for SHORT
                    elif current_trade.direction == TradeDirection.SHORT:
                        # Stop loss hit (price goes up)
                        if current_high >= current_trade.stop_loss:
                            current_trade.exit_price = current_trade.stop_loss
                            current_trade.exit_time = current_time
                            current_trade.pnl_pips = -self.stop_loss_pips
                            current_trade.exit_reason = "STOP_LOSS"
                            current_trade.is_open = False
                        # Take profit hit (price goes down)
                        elif current_low <= current_trade.take_profit:
                            current_trade.exit_price = current_trade.take_profit
                            current_trade.exit_time = current_time
                            current_trade.pnl_pips = self.take_profit_pips
                            current_trade.exit_reason = "TAKE_PROFIT"
                            current_trade.is_open = False
                        # Exit on bullish crossover
                        elif ema_f > ema_s and prev_ema_f <= prev_ema_s:
                            current_trade.exit_price = current_price
                            current_trade.exit_time = current_time
                            current_trade.pnl_pips = self._price_to_pips(
                                current_trade.entry_price - current_price
                            )
                            current_trade.exit_reason = "SIGNAL"
                            current_trade.is_open = False

                    # If trade closed, add to list
                    if not current_trade.is_open:
                        trades.append(current_trade)
                        current_trade = None

                # Entry signals (only if no open trade)
                if not current_trade:
                    # LONG: Bullish crossover + RSI not overbought
                    if ema_f > ema_s and prev_ema_f <= prev_ema_s and rsi < 70 and rsi > 30:
                        current_trade = BacktestTrade(
                            direction=TradeDirection.LONG,
                            entry_time=current_time,
                            entry_price=current_price,
                            stop_loss=current_price - self._pips_to_price(self.stop_loss_pips),
                            take_profit=current_price + self._pips_to_price(self.take_profit_pips)
                        )

                    # SHORT: Bearish crossover + RSI not oversold
                    elif ema_f < ema_s and prev_ema_f >= prev_ema_s and rsi > 30 and rsi < 70:
                        current_trade = BacktestTrade(
                            direction=TradeDirection.SHORT,
                            entry_time=current_time,
                            entry_price=current_price,
                            stop_loss=current_price + self._pips_to_price(self.stop_loss_pips),
                            take_profit=current_price - self._pips_to_price(self.take_profit_pips)
                        )

            # Close any remaining open trade at last price
            if current_trade and current_trade.is_open:
                current_trade.exit_price = closes[-1]
                current_trade.exit_time = times[-1]
                if current_trade.direction == TradeDirection.LONG:
                    current_trade.pnl_pips = self._price_to_pips(
                        closes[-1] - current_trade.entry_price
                    )
                else:
                    current_trade.pnl_pips = self._price_to_pips(
                        current_trade.entry_price - closes[-1]
                    )
                current_trade.exit_reason = "END_OF_DATA"
                current_trade.is_open = False
                trades.append(current_trade)

            # Calculate statistics
            return self._calculate_results(trades, timeframe, times[0], times[-1])

        except Exception as e:
            self.logger.error(f"Backtest error: {e}")
            return self._empty_result(timeframe)

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

        total_pips = sum(t.pnl_pips for t in trades)
        gross_profit = sum(t.pnl_pips for t in winning_trades)
        gross_loss = abs(sum(t.pnl_pips for t in losing_trades))

        # Calculate max drawdown
        cumulative_pips = 0.0
        peak_pips = 0.0
        max_drawdown = 0.0

        for trade in trades:
            cumulative_pips += trade.pnl_pips
            if cumulative_pips > peak_pips:
                peak_pips = cumulative_pips
            drawdown = peak_pips - cumulative_pips
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        result = BacktestResult(
            instrument=self.instrument,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            total_trades=len(trades),
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            total_pips=round(total_pips, 2),
            max_drawdown_pips=round(max_drawdown, 2),
            win_rate=round(len(winning_trades) / len(trades) * 100, 2) if trades else 0,
            profit_factor=round(gross_profit / gross_loss, 2) if gross_loss > 0 else 0,
            avg_win_pips=round(gross_profit / len(winning_trades), 2) if winning_trades else 0,
            avg_loss_pips=round(gross_loss / len(losing_trades), 2) if losing_trades else 0,
            trades=trades
        )

        self.logger.info(
            f"📊 Backtest complete: {result.total_trades} trades, "
            f"{result.win_rate}% win rate, {result.total_pips} pips, "
            f"PF: {result.profit_factor}"
        )

        return result

    def _empty_result(self, timeframe: str) -> BacktestResult:
        """Return empty result on error"""
        return BacktestResult(
            instrument=self.instrument,
            timeframe=timeframe,
            start_date="",
            end_date="",
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            total_pips=0,
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
            "start_date": result.start_date,
            "end_date": result.end_date,
            "total_trades": result.total_trades,
            "winning_trades": result.winning_trades,
            "losing_trades": result.losing_trades,
            "total_pips": result.total_pips,
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
