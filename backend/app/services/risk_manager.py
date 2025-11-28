"""
Risk Manager for Forex Trading
Controls position sizing, drawdown limits, and daily loss limits
"""

import logging
from typing import Dict, Optional, List, Set
from datetime import datetime, date
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# Portfolio Configuration - Approved pairs and strategies
PORTFOLIO_CONFIG = {
    "EUR_USD": {"strategy": "hybrid", "enabled": True},
    "USD_JPY": {"strategy": "hybrid", "enabled": True},
    "GBP_USD": {"strategy": "macd_only", "enabled": True},  # Breakout disabled
    "AUD_USD": {"strategy": None, "enabled": False},  # Excluded
    "USD_CAD": {"strategy": None, "enabled": False},  # Excluded
}


@dataclass
class OpenPosition:
    """Track open position risk"""
    pair: str
    units: int
    risk_percent: float
    entry_time: datetime


@dataclass
class DailyStats:
    """Daily trading statistics"""
    date: date
    starting_balance: float
    current_balance: float
    peak_balance: float
    trades_count: int = 0
    wins: int = 0
    losses: int = 0
    total_profit: float = 0.0
    total_loss: float = 0.0
    max_drawdown: float = 0.0
    is_locked: bool = False
    lock_reason: Optional[str] = None


class RiskManager:
    """
    Risk management for Forex trading.

    Features:
    - Daily loss limit
    - Maximum drawdown protection
    - Dynamic position sizing based on volatility
    - Consecutive loss protection
    - Portfolio aggregate risk limit (max 3% total exposure)
    - Per-pair strategy configuration
    """

    def __init__(
        self,
        max_daily_loss_percent: float = 3.0,
        max_drawdown_percent: float = 10.0,
        max_consecutive_losses: int = 3,
        position_size_reduction_after_loss: float = 0.5,
        base_risk_per_trade_percent: float = 1.0,
        max_aggregate_risk_percent: float = 3.0
    ):
        """
        Initialize risk manager.

        Args:
            max_daily_loss_percent: Maximum daily loss as % of starting balance (default 3%)
            max_drawdown_percent: Maximum drawdown from peak (default 10%)
            max_consecutive_losses: Lock trading after N consecutive losses (default 3)
            position_size_reduction_after_loss: Reduce size to X% after loss (default 50%)
            base_risk_per_trade_percent: Base risk per trade as % of balance (default 1%)
            max_aggregate_risk_percent: Maximum total risk across all open positions (default 3%)
        """
        self.max_daily_loss_percent = max_daily_loss_percent
        self.max_drawdown_percent = max_drawdown_percent
        self.max_consecutive_losses = max_consecutive_losses
        self.position_size_reduction = position_size_reduction_after_loss
        self.base_risk_percent = base_risk_per_trade_percent
        self.max_aggregate_risk = max_aggregate_risk_percent

        self.logger = logger
        self.daily_stats: Optional[DailyStats] = None
        self.consecutive_losses = 0
        self.last_trade_was_loss = False

        # Portfolio tracking
        self.open_positions: Dict[str, OpenPosition] = {}
        self.portfolio_config = PORTFOLIO_CONFIG

    def initialize_day(self, balance: float) -> DailyStats:
        """Initialize daily statistics"""
        today = date.today()

        # Check if we need to reset (new day)
        if self.daily_stats is None or self.daily_stats.date != today:
            self.daily_stats = DailyStats(
                date=today,
                starting_balance=balance,
                current_balance=balance,
                peak_balance=balance
            )
            self.consecutive_losses = 0
            self.logger.info(f"📊 Risk Manager: New day initialized | Balance: ${balance:,.2f}")

        return self.daily_stats

    def update_balance(self, new_balance: float) -> Dict:
        """
        Update balance and check risk limits.

        Returns:
            Dict with risk status and any warnings
        """
        if not self.daily_stats:
            self.initialize_day(new_balance)

        stats = self.daily_stats
        stats.current_balance = new_balance

        # Update peak balance
        if new_balance > stats.peak_balance:
            stats.peak_balance = new_balance

        # Calculate metrics
        daily_pnl = new_balance - stats.starting_balance
        daily_pnl_percent = (daily_pnl / stats.starting_balance) * 100

        drawdown = stats.peak_balance - new_balance
        drawdown_percent = (drawdown / stats.peak_balance) * 100 if stats.peak_balance > 0 else 0

        # Update max drawdown
        if drawdown_percent > stats.max_drawdown:
            stats.max_drawdown = drawdown_percent

        result = {
            'daily_pnl': daily_pnl,
            'daily_pnl_percent': daily_pnl_percent,
            'drawdown': drawdown,
            'drawdown_percent': drawdown_percent,
            'can_trade': True,
            'warnings': [],
            'position_size_multiplier': 1.0
        }

        # Check daily loss limit
        if daily_pnl_percent <= -self.max_daily_loss_percent:
            stats.is_locked = True
            stats.lock_reason = f"Daily loss limit reached ({daily_pnl_percent:.1f}%)"
            result['can_trade'] = False
            result['warnings'].append(f"🔒 LOCKED: {stats.lock_reason}")
            self.logger.warning(f"🔒 Trading LOCKED: {stats.lock_reason}")

        # Check max drawdown
        elif drawdown_percent >= self.max_drawdown_percent:
            stats.is_locked = True
            stats.lock_reason = f"Max drawdown reached ({drawdown_percent:.1f}%)"
            result['can_trade'] = False
            result['warnings'].append(f"🔒 LOCKED: {stats.lock_reason}")
            self.logger.warning(f"🔒 Trading LOCKED: {stats.lock_reason}")

        # Check consecutive losses
        elif self.consecutive_losses >= self.max_consecutive_losses:
            stats.is_locked = True
            stats.lock_reason = f"Consecutive losses limit ({self.consecutive_losses})"
            result['can_trade'] = False
            result['warnings'].append(f"🔒 LOCKED: {stats.lock_reason}")
            self.logger.warning(f"🔒 Trading LOCKED: {stats.lock_reason}")

        # Reduce position size after loss
        if self.last_trade_was_loss and result['can_trade']:
            result['position_size_multiplier'] = self.position_size_reduction
            result['warnings'].append(f"⚠️ Reduced position size to {self.position_size_reduction:.0%}")

        return result

    def record_trade(self, profit_loss: float):
        """Record a completed trade"""
        if not self.daily_stats:
            return

        stats = self.daily_stats
        stats.trades_count += 1

        if profit_loss >= 0:
            stats.wins += 1
            stats.total_profit += profit_loss
            self.consecutive_losses = 0
            self.last_trade_was_loss = False
            self.logger.info(f"✅ Trade recorded: +${profit_loss:,.2f} | W/L: {stats.wins}/{stats.losses}")
        else:
            stats.losses += 1
            stats.total_loss += abs(profit_loss)
            self.consecutive_losses += 1
            self.last_trade_was_loss = True
            self.logger.warning(f"❌ Trade recorded: -${abs(profit_loss):,.2f} | Consecutive losses: {self.consecutive_losses}")

    def calculate_position_size(
        self,
        balance: float,
        stop_loss_pips: float,
        pip_value: float = 0.0001
    ) -> Dict:
        """
        Calculate position size based on risk parameters.

        Args:
            balance: Current account balance
            stop_loss_pips: Stop loss distance in pips
            pip_value: Value per pip (0.0001 for majors, 0.01 for JPY)

        Returns:
            Dict with units and risk info
        """
        # Base risk amount
        risk_amount = balance * (self.base_risk_percent / 100)

        # Apply multiplier if needed
        risk_status = self.update_balance(balance)
        multiplier = risk_status.get('position_size_multiplier', 1.0)
        adjusted_risk = risk_amount * multiplier

        # Calculate position size
        # Risk = Units × Stop Loss Pips × Pip Value
        # Units = Risk / (Stop Loss Pips × Pip Value)
        if stop_loss_pips > 0:
            risk_per_unit = stop_loss_pips * pip_value
            units = int(adjusted_risk / risk_per_unit)
        else:
            units = int(adjusted_risk / pip_value)  # Fallback

        return {
            'units': units,
            'risk_amount': adjusted_risk,
            'risk_percent': self.base_risk_percent * multiplier,
            'multiplier': multiplier,
            'can_trade': risk_status['can_trade'],
            'warnings': risk_status['warnings']
        }

    def get_status(self) -> Dict:
        """Get current risk manager status"""
        if not self.daily_stats:
            return {
                'initialized': False,
                'can_trade': True
            }

        stats = self.daily_stats
        return {
            'initialized': True,
            'date': stats.date.isoformat(),
            'starting_balance': stats.starting_balance,
            'current_balance': stats.current_balance,
            'peak_balance': stats.peak_balance,
            'daily_pnl': stats.current_balance - stats.starting_balance,
            'max_drawdown': stats.max_drawdown,
            'trades_today': stats.trades_count,
            'wins': stats.wins,
            'losses': stats.losses,
            'win_rate': (stats.wins / stats.trades_count * 100) if stats.trades_count > 0 else 0,
            'consecutive_losses': self.consecutive_losses,
            'is_locked': stats.is_locked,
            'lock_reason': stats.lock_reason,
            'can_trade': not stats.is_locked
        }

    def reset_lock(self):
        """Manually reset trading lock (use with caution)"""
        if self.daily_stats:
            self.daily_stats.is_locked = False
            self.daily_stats.lock_reason = None
            self.consecutive_losses = 0
            self.logger.info("🔓 Trading lock manually reset")

    # ==================== PORTFOLIO MANAGEMENT ====================

    def is_pair_enabled(self, pair: str) -> bool:
        """Check if a pair is enabled for trading"""
        config = self.portfolio_config.get(pair, {})
        return config.get("enabled", False)

    def get_pair_strategy(self, pair: str) -> Optional[str]:
        """Get the approved strategy for a pair"""
        config = self.portfolio_config.get(pair, {})
        if not config.get("enabled", False):
            return None
        return config.get("strategy")

    def is_breakout_allowed(self, pair: str) -> bool:
        """Check if breakout strategy is allowed for a pair"""
        strategy = self.get_pair_strategy(pair)
        return strategy == "hybrid"  # Only hybrid allows breakout

    def get_current_aggregate_risk(self) -> float:
        """Calculate total risk across all open positions"""
        return sum(pos.risk_percent for pos in self.open_positions.values())

    def can_open_position(self, pair: str, risk_percent: float) -> Dict:
        """
        Check if a new position can be opened based on portfolio rules.

        Args:
            pair: Currency pair
            risk_percent: Risk for the new position as % of balance

        Returns:
            Dict with can_open, reason, and available_risk
        """
        result = {
            "can_open": True,
            "reason": None,
            "current_risk": self.get_current_aggregate_risk(),
            "available_risk": 0.0,
            "warnings": []
        }

        # Check if pair is enabled
        if not self.is_pair_enabled(pair):
            result["can_open"] = False
            result["reason"] = f"❌ {pair} is not in the approved portfolio"
            self.logger.warning(result["reason"])
            return result

        # Check if we already have a position in this pair
        if pair in self.open_positions:
            result["can_open"] = False
            result["reason"] = f"⚠️ Already have open position in {pair}"
            return result

        # Check aggregate risk limit
        current_risk = result["current_risk"]
        available_risk = self.max_aggregate_risk - current_risk
        result["available_risk"] = available_risk

        if risk_percent > available_risk:
            result["can_open"] = False
            result["reason"] = (
                f"🛑 Aggregate risk limit reached: {current_risk:.1f}% used of {self.max_aggregate_risk}% max. "
                f"Available: {available_risk:.1f}%, Requested: {risk_percent:.1f}%"
            )
            self.logger.warning(result["reason"])
            return result

        # Add warning if approaching limit
        if current_risk + risk_percent > self.max_aggregate_risk * 0.8:
            result["warnings"].append(
                f"⚠️ Approaching aggregate risk limit: {current_risk + risk_percent:.1f}% of {self.max_aggregate_risk}%"
            )

        return result

    def register_position(self, pair: str, units: int, risk_percent: float):
        """Register a new open position"""
        self.open_positions[pair] = OpenPosition(
            pair=pair,
            units=units,
            risk_percent=risk_percent,
            entry_time=datetime.utcnow()
        )
        self.logger.info(
            f"📊 Position registered: {pair} | Risk: {risk_percent:.1f}% | "
            f"Total aggregate: {self.get_current_aggregate_risk():.1f}%"
        )

    def close_position(self, pair: str):
        """Remove a closed position from tracking"""
        if pair in self.open_positions:
            pos = self.open_positions.pop(pair)
            self.logger.info(
                f"📊 Position closed: {pair} | Released risk: {pos.risk_percent:.1f}% | "
                f"Remaining aggregate: {self.get_current_aggregate_risk():.1f}%"
            )

    def get_portfolio_status(self) -> Dict:
        """Get current portfolio risk status"""
        current_risk = self.get_current_aggregate_risk()
        return {
            "open_positions": len(self.open_positions),
            "positions": {
                pair: {
                    "units": pos.units,
                    "risk_percent": pos.risk_percent,
                    "entry_time": pos.entry_time.isoformat()
                }
                for pair, pos in self.open_positions.items()
            },
            "aggregate_risk_percent": current_risk,
            "max_aggregate_risk": self.max_aggregate_risk,
            "available_risk": self.max_aggregate_risk - current_risk,
            "utilization_percent": (current_risk / self.max_aggregate_risk * 100) if self.max_aggregate_risk > 0 else 0,
            "enabled_pairs": [p for p, c in self.portfolio_config.items() if c.get("enabled")],
            "excluded_pairs": [p for p, c in self.portfolio_config.items() if not c.get("enabled")]
        }
