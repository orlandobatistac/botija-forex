"""
Forex Trailing Stop Manager
Moves stop loss dynamically as position gains profit
"""

import logging
from typing import Optional, Dict
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class TrailingStopState:
    """State of a trailing stop"""
    instrument: str
    direction: str  # LONG or SHORT
    entry_price: float
    current_stop: float
    trailing_distance_pips: float
    best_price: float  # Highest for LONG, Lowest for SHORT
    activated: bool  # Only activate after minimum profit
    activation_pips: float
    created_at: datetime
    updated_at: datetime


class ForexTrailingStop:
    """
    Dynamic trailing stop for Forex positions.

    For LONG: Stop moves UP as price increases
    For SHORT: Stop moves DOWN as price decreases
    """

    def __init__(
        self,
        oanda_client,
        trailing_distance_pips: float = 30,
        activation_pips: float = 20
    ):
        """
        Initialize trailing stop manager.

        Args:
            oanda_client: OANDA client for modifying orders
            trailing_distance_pips: Distance to maintain from best price
            activation_pips: Minimum profit before trailing activates
        """
        self.oanda = oanda_client
        self.trailing_distance_pips = trailing_distance_pips
        self.activation_pips = activation_pips
        self.logger = logger

        # Track active trailing stops by instrument
        self.active_stops: Dict[str, TrailingStopState] = {}

    def _pips_to_price(self, instrument: str, pips: float) -> float:
        """Convert pips to price difference"""
        # For JPY pairs, 1 pip = 0.01, for others 1 pip = 0.0001
        if 'JPY' in instrument:
            return pips * 0.01
        return pips * 0.0001

    def _price_to_pips(self, instrument: str, price_diff: float) -> float:
        """Convert price difference to pips"""
        if 'JPY' in instrument:
            return price_diff / 0.01
        return price_diff / 0.0001

    def start_trailing(
        self,
        instrument: str,
        direction: str,
        entry_price: float,
        initial_stop: Optional[float] = None
    ) -> TrailingStopState:
        """
        Start trailing stop for a new position.

        Args:
            instrument: Currency pair (EUR_USD)
            direction: LONG or SHORT
            entry_price: Entry price of position
            initial_stop: Initial stop loss price (optional)
        """
        # Calculate initial stop if not provided
        if initial_stop is None:
            pip_value = self._pips_to_price(instrument, self.trailing_distance_pips)
            if direction == 'LONG':
                initial_stop = entry_price - pip_value
            else:  # SHORT
                initial_stop = entry_price + pip_value

        state = TrailingStopState(
            instrument=instrument,
            direction=direction,
            entry_price=entry_price,
            current_stop=initial_stop,
            trailing_distance_pips=self.trailing_distance_pips,
            best_price=entry_price,
            activated=False,
            activation_pips=self.activation_pips,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        self.active_stops[instrument] = state
        self.logger.info(
            f"📍 Trailing stop started: {instrument} {direction} "
            f"entry={entry_price:.5f} stop={initial_stop:.5f}"
        )

        return state

    def update(self, instrument: str, current_price: float) -> Dict:
        """
        Update trailing stop based on current price.

        Returns dict with:
            - should_close: Whether to close position
            - stop_updated: Whether stop was moved
            - new_stop: New stop price (if updated)
            - profit_pips: Current profit in pips
        """
        if instrument not in self.active_stops:
            return {'should_close': False, 'stop_updated': False}

        state = self.active_stops[instrument]
        result = {
            'should_close': False,
            'stop_updated': False,
            'new_stop': state.current_stop,
            'profit_pips': 0,
            'activated': state.activated
        }

        pip_value = self._pips_to_price(instrument, 1)
        trailing_distance = self._pips_to_price(instrument, self.trailing_distance_pips)
        activation_distance = self._pips_to_price(instrument, self.activation_pips)

        if state.direction == 'LONG':
            # Calculate profit
            profit = current_price - state.entry_price
            result['profit_pips'] = self._price_to_pips(instrument, profit)

            # Check if stop hit
            if current_price <= state.current_stop:
                result['should_close'] = True
                self.logger.warning(
                    f"🛑 Trailing stop HIT: {instrument} "
                    f"price={current_price:.5f} stop={state.current_stop:.5f}"
                )
                return result

            # Check activation
            if not state.activated and profit >= activation_distance:
                state.activated = True
                self.logger.info(f"✅ Trailing stop ACTIVATED: {instrument} +{result['profit_pips']:.1f} pips")

            # Update best price and trail stop
            if state.activated and current_price > state.best_price:
                state.best_price = current_price
                new_stop = current_price - trailing_distance

                # Only move stop UP (never down)
                if new_stop > state.current_stop:
                    old_stop = state.current_stop
                    state.current_stop = new_stop
                    state.updated_at = datetime.now()
                    result['stop_updated'] = True
                    result['new_stop'] = new_stop

                    self.logger.info(
                        f"📈 Trailing stop MOVED: {instrument} "
                        f"{old_stop:.5f} → {new_stop:.5f} (+{result['profit_pips']:.1f} pips)"
                    )

                    # Update stop on OANDA
                    self._update_oanda_stop(instrument, new_stop)

        else:  # SHORT
            # Calculate profit (inverse for short)
            profit = state.entry_price - current_price
            result['profit_pips'] = self._price_to_pips(instrument, profit)

            # Check if stop hit
            if current_price >= state.current_stop:
                result['should_close'] = True
                self.logger.warning(
                    f"🛑 Trailing stop HIT: {instrument} "
                    f"price={current_price:.5f} stop={state.current_stop:.5f}"
                )
                return result

            # Check activation
            if not state.activated and profit >= activation_distance:
                state.activated = True
                self.logger.info(f"✅ Trailing stop ACTIVATED: {instrument} +{result['profit_pips']:.1f} pips")

            # Update best price and trail stop
            if state.activated and current_price < state.best_price:
                state.best_price = current_price
                new_stop = current_price + trailing_distance

                # Only move stop DOWN (never up)
                if new_stop < state.current_stop:
                    old_stop = state.current_stop
                    state.current_stop = new_stop
                    state.updated_at = datetime.now()
                    result['stop_updated'] = True
                    result['new_stop'] = new_stop

                    self.logger.info(
                        f"📉 Trailing stop MOVED: {instrument} "
                        f"{old_stop:.5f} → {new_stop:.5f} (+{result['profit_pips']:.1f} pips)"
                    )

                    # Update stop on OANDA
                    self._update_oanda_stop(instrument, new_stop)

        return result

    def _update_oanda_stop(self, instrument: str, new_stop: float) -> bool:
        """Update stop loss on OANDA"""
        try:
            if not self.oanda:
                return False

            # Get open trades for instrument
            trades = self.oanda.get_open_trades()
            if not trades:
                return False

            for trade in trades:
                if trade.get('instrument') == instrument:
                    trade_id = trade.get('id')
                    result = self.oanda.modify_trade_stop_loss(trade_id, new_stop)
                    return result.get('success', False)

            return False

        except Exception as e:
            self.logger.error(f"Error updating OANDA stop: {e}")
            return False

    def stop_trailing(self, instrument: str) -> Optional[TrailingStopState]:
        """Stop trailing and remove from active stops"""
        if instrument in self.active_stops:
            state = self.active_stops.pop(instrument)
            self.logger.info(f"🔴 Trailing stop removed: {instrument}")
            return state
        return None

    def get_state(self, instrument: str) -> Optional[TrailingStopState]:
        """Get current trailing stop state"""
        return self.active_stops.get(instrument)

    def get_all_states(self) -> Dict[str, TrailingStopState]:
        """Get all active trailing stops"""
        return self.active_stops.copy()
