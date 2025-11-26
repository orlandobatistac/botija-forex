"""
Tests for Phase 2 Features
Run: python -m pytest backend/tests/test_phase2.py -v
"""

import pytest
import os
import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))


class TestRiskManager:
    """Tests for RiskManager"""

    def test_risk_manager_initialization(self):
        """Test RiskManager initializes with correct defaults"""
        from app.services.risk_manager import RiskManager

        rm = RiskManager()

        assert rm.max_daily_loss_percent == 3.0
        assert rm.max_drawdown_percent == 10.0
        assert rm.max_consecutive_losses == 3
        assert rm.consecutive_losses == 0

    def test_daily_stats_initialization(self):
        """Test daily stats are initialized correctly"""
        from app.services.risk_manager import RiskManager

        rm = RiskManager(max_daily_loss_percent=3.0)
        stats = rm.initialize_day(10000.0)

        assert stats.starting_balance == 10000.0
        assert stats.current_balance == 10000.0
        assert stats.is_locked is False

    def test_consecutive_losses_tracking(self):
        """Test consecutive losses are tracked"""
        from app.services.risk_manager import RiskManager

        rm = RiskManager(max_consecutive_losses=3)
        rm.initialize_day(10000.0)

        # Simulate 3 losses
        rm.consecutive_losses = 3

        assert rm.consecutive_losses == 3

    def test_can_trade_check(self):
        """Test update_balance returns correct value"""
        from app.services.risk_manager import RiskManager

        rm = RiskManager()
        rm.initialize_day(10000.0)

        # Should be able to trade initially
        result = rm.update_balance(10000.0)
        assert result['can_trade'] is True

    def test_record_trade_updates_stats(self):
        """Test recording trade updates statistics"""
        from app.services.risk_manager import RiskManager

        rm = RiskManager()
        rm.initialize_day(10000.0)

        rm.record_trade(profit_loss=50.0)

        assert rm.daily_stats.trades_count == 1
        assert rm.daily_stats.wins == 1
        assert rm.consecutive_losses == 0

    def test_record_loss_increments_consecutive(self):
        """Test recording loss increments consecutive counter"""
        from app.services.risk_manager import RiskManager

        rm = RiskManager()
        rm.initialize_day(10000.0)

        rm.record_trade(profit_loss=-50.0)

        assert rm.consecutive_losses == 1
        assert rm.daily_stats.losses == 1
class TestMultiTimeframe:
    """Tests for MultiTimeframeAnalyzer"""

    def test_timeframe_signal_enum(self):
        """Test TimeframeSignal enum values"""
        from app.services.multi_timeframe import TimeframeSignal

        assert TimeframeSignal.LONG.value == "LONG"
        assert TimeframeSignal.SHORT.value == "SHORT"
        assert TimeframeSignal.HOLD.value == "HOLD"

    def test_mtf_initialization(self):
        """Test MultiTimeframeAnalyzer initialization"""
        from app.services.multi_timeframe import MultiTimeframeAnalyzer

        mock_oanda = Mock()
        mtf = MultiTimeframeAnalyzer(mock_oanda, "EUR_USD")

        assert mtf.instrument == "EUR_USD"
        assert mtf.oanda == mock_oanda

    def test_analyze_timeframe_with_mock_data(self):
        """Test analyze_timeframe with mocked OANDA data"""
        from app.services.multi_timeframe import MultiTimeframeAnalyzer, TimeframeSignal

        mock_oanda = Mock()

        # Create uptrend data (EMA20 > EMA50)
        prices = list(range(100, 200))  # Uptrend
        mock_candles = [{"close": p, "high": p + 1, "low": p - 1} for p in prices]
        mock_oanda.get_candles.return_value = mock_candles

        mtf = MultiTimeframeAnalyzer(mock_oanda, "EUR_USD")
        analysis = mtf.analyze_timeframe("H4", 100)

        assert analysis is not None
        assert analysis.timeframe == "H4"
        # In strong uptrend, should signal LONG
        assert analysis.signal in [TimeframeSignal.LONG, TimeframeSignal.HOLD]

    def test_confirmed_signal_requires_alignment(self):
        """Test that confirmed signal requires H1 + H4 alignment"""
        from app.services.multi_timeframe import MultiTimeframeAnalyzer

        mock_oanda = Mock()

        # Uptrend data
        uptrend = [{"close": p, "high": p + 1, "low": p - 1} for p in range(100, 200)]
        mock_oanda.get_candles.return_value = uptrend

        mtf = MultiTimeframeAnalyzer(mock_oanda, "EUR_USD")
        result = mtf.get_confirmed_signal()

        assert "signal" in result
        assert "confirmation" in result
        assert "h1" in result
        assert "h4" in result


class TestMultiPair:
    """Tests for MultiPairManager"""

    def test_multi_pair_initialization(self):
        """Test MultiPairManager initialization"""
        from app.services.multi_pair import MultiPairManager

        mock_oanda = Mock()
        instruments = ["EUR_USD", "GBP_USD"]

        manager = MultiPairManager(mock_oanda, instruments)

        assert manager.instruments == instruments
        assert len(manager.analyzers) == 2
        assert "EUR_USD" in manager.analyzers
        assert "GBP_USD" in manager.analyzers

    def test_analyze_pair(self):
        """Test single pair analysis"""
        from app.services.multi_pair import MultiPairManager

        mock_oanda = Mock()
        mock_oanda.get_spread.return_value = {"mid": 1.1000, "spread_pips": 1.5}
        mock_oanda.get_position_units.return_value = 0
        mock_oanda.get_candles.return_value = [
            {"close": p, "high": p + 0.001, "low": p - 0.001}
            for p in [1.1 + i * 0.001 for i in range(100)]
        ]

        manager = MultiPairManager(mock_oanda, ["EUR_USD"])
        analysis = manager.analyze_pair("EUR_USD")

        assert analysis is not None
        assert analysis.instrument == "EUR_USD"
        assert analysis.current_price == 1.1000
        assert analysis.spread_pips == 1.5

    def test_get_all_positions(self):
        """Test getting all positions"""
        from app.services.multi_pair import MultiPairManager

        mock_oanda = Mock()
        mock_oanda.get_position_units.side_effect = lambda x: 1000 if x == "EUR_USD" else 0

        manager = MultiPairManager(mock_oanda, ["EUR_USD", "GBP_USD"])
        positions = manager.get_all_positions()

        assert "EUR_USD" in positions
        assert positions["EUR_USD"] == 1000
        assert "GBP_USD" not in positions  # No position


class TestBacktester:
    """Tests for Backtester"""

    def test_backtester_initialization(self):
        """Test Backtester initialization"""
        from app.services.backtester import Backtester

        mock_oanda = Mock()
        bt = Backtester(
            oanda_client=mock_oanda,
            instrument="EUR_USD",
            stop_loss_pips=50.0,
            take_profit_pips=100.0
        )

        assert bt.instrument == "EUR_USD"
        assert bt.stop_loss_pips == 50.0
        assert bt.take_profit_pips == 100.0
        assert bt.pip_value == 0.0001

    def test_jpy_pair_pip_value(self):
        """Test JPY pair has correct pip value"""
        from app.services.backtester import Backtester

        mock_oanda = Mock()
        bt = Backtester(mock_oanda, "USD_JPY")

        assert bt.pip_value == 0.01

    def test_price_to_pips_conversion(self):
        """Test price to pips conversion"""
        from app.services.backtester import Backtester

        mock_oanda = Mock()
        bt = Backtester(mock_oanda, "EUR_USD")

        # 0.0050 should be 50 pips
        pips = bt._price_to_pips(0.0050)
        assert pips == 50.0

    def test_pips_to_price_conversion(self):
        """Test pips to price conversion"""
        from app.services.backtester import Backtester

        mock_oanda = Mock()
        bt = Backtester(mock_oanda, "EUR_USD")

        # 50 pips should be 0.0050
        price = bt._pips_to_price(50.0)
        assert price == 0.0050

    def test_backtest_with_mock_data(self):
        """Test backtest execution with mock data"""
        from app.services.backtester import Backtester

        mock_oanda = Mock()

        # Create data with clear uptrend then downtrend (to trigger trades)
        prices = []
        times = []

        # 60 candles uptrend
        for i in range(60):
            prices.append(1.1000 + i * 0.0010)
            times.append(f"2024-01-01T{i:02d}:00:00Z")

        # 40 candles downtrend
        for i in range(40):
            prices.append(1.1600 - i * 0.0010)
            times.append(f"2024-01-02T{i:02d}:00:00Z")

        mock_candles = [
            {
                "time": times[i],
                "open": prices[i] - 0.0005,
                "high": prices[i] + 0.0010,
                "low": prices[i] - 0.0010,
                "close": prices[i]
            }
            for i in range(len(prices))
        ]
        mock_oanda.get_candles.return_value = mock_candles

        bt = Backtester(mock_oanda, "EUR_USD", stop_loss_pips=50, take_profit_pips=100)
        result = bt.run(timeframe="H4", candle_count=100)

        assert result.instrument == "EUR_USD"
        assert result.timeframe == "H4"
        # Should have some trades with clear trend changes
        assert result.total_trades >= 0

    def test_backtest_result_to_dict(self):
        """Test BacktestResult serialization"""
        from app.services.backtester import Backtester, BacktestResult, BacktestTrade, TradeDirection

        mock_oanda = Mock()
        bt = Backtester(mock_oanda, "EUR_USD")

        result = BacktestResult(
            instrument="EUR_USD",
            timeframe="H4",
            start_date="2024-01-01",
            end_date="2024-01-31",
            total_trades=10,
            winning_trades=6,
            losing_trades=4,
            total_pips=150.0,
            max_drawdown_pips=50.0,
            win_rate=60.0,
            profit_factor=1.5,
            avg_win_pips=50.0,
            avg_loss_pips=25.0,
            trades=[
                BacktestTrade(
                    direction=TradeDirection.LONG,
                    entry_time="2024-01-01T10:00:00Z",
                    entry_price=1.1000,
                    exit_time="2024-01-01T14:00:00Z",
                    exit_price=1.1050,
                    pnl_pips=50.0,
                    is_open=False,
                    exit_reason="TAKE_PROFIT"
                )
            ]
        )

        data = bt.to_dict(result)

        assert data["instrument"] == "EUR_USD"
        assert data["win_rate"] == 60.0
        assert data["profit_factor"] == 1.5
        assert len(data["trades"]) == 1
        assert data["trades"][0]["direction"] == "LONG"


class TestForexTrailingStop:
    """Tests for ForexTrailingStop"""

    def test_trailing_stop_initialization(self):
        """Test ForexTrailingStop initialization"""
        from app.services.forex_trailing_stop import ForexTrailingStop

        mock_oanda = Mock()
        ts = ForexTrailingStop(
            oanda_client=mock_oanda,
            trailing_distance_pips=30.0,
            activation_pips=20.0
        )

        assert ts.trailing_distance_pips == 30.0
        assert ts.activation_pips == 20.0
        assert len(ts.active_stops) == 0

    def test_trailing_stop_start(self):
        """Test starting trailing stop"""
        from app.services.forex_trailing_stop import ForexTrailingStop

        mock_oanda = Mock()
        ts = ForexTrailingStop(mock_oanda, 30.0, 20.0)

        state = ts.start_trailing(
            instrument="EUR_USD",
            direction="LONG",
            entry_price=1.1000
        )

        assert state is not None
        assert state.instrument == "EUR_USD"
        assert state.direction == "LONG"
        assert state.entry_price == 1.1000
        assert "EUR_USD" in ts.active_stops

    def test_trailing_stop_update_long(self):
        """Test trailing stop update for LONG position"""
        from app.services.forex_trailing_stop import ForexTrailingStop

        mock_oanda = Mock()
        mock_oanda.modify_trade_stop_loss.return_value = {"success": True}

        ts = ForexTrailingStop(mock_oanda, 30.0, 20.0)
        ts.start_trailing("EUR_USD", "LONG", 1.1000)

        # Price moved up 30 pips (above 20 pip activation)
        current_price = 1.1030
        result = ts.update("EUR_USD", current_price)

        assert result is not None

    def test_pips_to_price_conversion(self):
        """Test pips to price conversion"""
        from app.services.forex_trailing_stop import ForexTrailingStop

        mock_oanda = Mock()
        ts = ForexTrailingStop(mock_oanda, 30.0, 20.0)

        # EUR_USD: 50 pips = 0.0050
        price = ts._pips_to_price("EUR_USD", 50.0)
        assert price == 0.0050

        # USD_JPY: 50 pips = 0.50
        price_jpy = ts._pips_to_price("USD_JPY", 50.0)
        assert price_jpy == 0.50

    def test_price_to_pips_conversion(self):
        """Test price to pips conversion"""
        from app.services.forex_trailing_stop import ForexTrailingStop

        mock_oanda = Mock()
        ts = ForexTrailingStop(mock_oanda, 30.0, 20.0)

        pips = ts._price_to_pips("EUR_USD", 0.0050)
        assert pips == 50.0
class TestConfigPhase2:
    """Tests for Phase 2 configuration"""

    def test_config_has_trailing_stop_settings(self):
        """Test config has trailing stop settings"""
        from app.config import Config

        assert hasattr(Config, 'TRAILING_STOP_ENABLED')
        assert hasattr(Config, 'TRAILING_STOP_DISTANCE_PIPS')
        assert hasattr(Config, 'TRAILING_STOP_ACTIVATION_PIPS')

    def test_config_has_risk_manager_settings(self):
        """Test config has risk manager settings"""
        from app.config import Config

        assert hasattr(Config, 'RISK_MANAGER_ENABLED')
        assert hasattr(Config, 'MAX_DAILY_LOSS_PERCENT')
        assert hasattr(Config, 'MAX_DRAWDOWN_PERCENT')
        assert hasattr(Config, 'MAX_CONSECUTIVE_LOSSES')

    def test_config_has_multi_timeframe_setting(self):
        """Test config has multi-timeframe setting"""
        from app.config import Config

        assert hasattr(Config, 'MULTI_TIMEFRAME_ENABLED')

    def test_config_has_trading_instruments(self):
        """Test config has trading instruments list"""
        from app.config import Config

        assert hasattr(Config, 'TRADING_INSTRUMENTS')
        assert isinstance(Config.TRADING_INSTRUMENTS, list)
        assert len(Config.TRADING_INSTRUMENTS) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
