"""
Trailing stop logic for profit protection
"""

import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)

class TrailingStop:
    """Dynamic trailing stop management"""
    
    def __init__(self, entry_price: float, trailing_percentage: float = 0.99):
        """Initialize trailing stop
        
        Args:
            entry_price: Entry price of the position
            trailing_percentage: Trailing stop percentage (0.99 = 1% below highest)
        """
        self.entry_price = entry_price
        self.trailing_percentage = trailing_percentage
        self.highest_price = entry_price
        self.trailing_stop = entry_price * trailing_percentage
        self.logger = logger
    
    def update(self, current_price: float) -> Dict:
        """Update trailing stop based on current price
        
        Returns:
            Dict with updated stop info and whether to sell
        """
        # Update highest price if current is higher
        if current_price > self.highest_price:
            self.highest_price = current_price
            # Update trailing stop - only move up, never down
            new_trailing = self.highest_price * self.trailing_percentage
            if new_trailing > self.trailing_stop:
                self.trailing_stop = new_trailing
                self.logger.info(
                    f"Trailing stop updated: ${self.trailing_stop:,.2f} "
                    f"(highest: ${self.highest_price:,.2f})"
                )
        
        # Check if should sell
        should_sell = current_price <= self.trailing_stop
        
        return {
            'current_price': current_price,
            'trailing_stop': self.trailing_stop,
            'highest_price': self.highest_price,
            'entry_price': self.entry_price,
            'profit_locked': self.trailing_stop - self.entry_price,
            'current_profit': current_price - self.entry_price,
            'should_sell': should_sell,
            'distance_to_stop': current_price - self.trailing_stop,
            'stop_percentage': ((current_price - self.trailing_stop) / self.trailing_stop) * 100
        }
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for storage"""
        return {
            'entry_price': self.entry_price,
            'highest_price': self.highest_price,
            'trailing_stop': self.trailing_stop,
            'trailing_percentage': self.trailing_percentage
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'TrailingStop':
        """Create from dictionary"""
        ts = cls(
            entry_price=data['entry_price'],
            trailing_percentage=data['trailing_percentage']
        )
        ts.highest_price = data['highest_price']
        ts.trailing_stop = data['trailing_stop']
        return ts
