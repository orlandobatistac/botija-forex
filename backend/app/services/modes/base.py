"""
Base trading engine interface
"""

from abc import ABC, abstractmethod
from typing import Dict, Tuple

class TradingEngine(ABC):
    """Abstract base class for trading engines (Real and Paper)"""
    
    @abstractmethod
    def load_balances(self) -> Dict[str, float]:
        """Load current balances
        
        Returns:
            Dict with 'btc' and 'usd' keys
        """
        pass
    
    @abstractmethod
    def buy(self, price: float, usd_amount: float) -> Tuple[bool, str]:
        """Execute a buy operation
        
        Args:
            price: Current BTC price
            usd_amount: Amount in USD to spend
            
        Returns:
            (success: bool, message: str)
        """
        pass
    
    @abstractmethod
    def sell(self, price: float, btc_amount: float) -> Tuple[bool, str]:
        """Execute a sell operation
        
        Args:
            price: Current BTC price
            btc_amount: Amount of BTC to sell
            
        Returns:
            (success: bool, message: str)
        """
        pass
    
    @abstractmethod
    def update_trailing_stop(self, price: float) -> Dict:
        """Update trailing stop
        
        Args:
            price: Current BTC price
            
        Returns:
            Dict with stop info
        """
        pass
    
    @abstractmethod
    def get_open_position(self) -> Dict:
        """Get current open position if any
        
        Returns:
            Dict with position info or empty dict
        """
        pass
    
    @abstractmethod
    def close_position(self) -> bool:
        """Close any open position
        
        Returns:
            bool: Success status
        """
        pass
    
    @abstractmethod
    def get_balance(self) -> Dict[str, float]:
        """Get current balances
        
        Returns:
            Dict with 'btc' and 'usd' keys
        """
        pass
    
    @abstractmethod
    def get_current_price(self) -> float:
        """Get current BTC price
        
        Returns:
            float: Current BTC price in USD
        """
        pass
