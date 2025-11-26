"""
Real trading mode - executes actual trades on Kraken
"""

import logging
from typing import Dict, Tuple
from ..kraken_client import KrakenClient
from .base import TradingEngine

logger = logging.getLogger(__name__)

class RealTradingEngine(TradingEngine):
    """Real trading engine using Kraken Spot API"""
    
    def __init__(self, kraken_client: KrakenClient):
        """Initialize real trading engine
        
        Args:
            kraken_client: Initialized KrakenClient instance
        """
        self.kraken = kraken_client
        self.logger = logger
        self.active_position = None
    
    def load_balances(self) -> Dict[str, float]:
        """Load balances from Kraken"""
        try:
            balance = self.kraken.get_account_balance()
            return {
                'btc': float(balance.get('XXBT', 0.0)),
                'usd': float(balance.get('ZUSD', 0.0))
            }
        except Exception as e:
            self.logger.error(f"Error loading balances: {e}")
            return {'btc': 0.0, 'usd': 0.0}
    
    def buy(self, price: float, usd_amount: float) -> Tuple[bool, str]:
        """Execute real buy order on Kraken"""
        try:
            volume = usd_amount / price
            
            self.logger.info(f"REAL BUY: {volume:.8f} BTC at ${price:,.2f}")
            
            result = self.kraken.place_limit_order(
                pair='XBTUSDT',
                side='buy',
                price=price,
                volume=volume
            )
            
            if result['success']:
                self.active_position = {
                    'type': 'buy',
                    'price': price,
                    'volume': volume,
                    'order_id': result.get('order_id')
                }
                return True, f"Real buy executed: {volume:.8f} BTC at ${price:,.2f}"
            else:
                return False, f"Real buy failed: {result.get('error', 'Unknown error')}"
        
        except Exception as e:
            self.logger.error(f"Error in real buy: {e}")
            return False, f"Real buy error: {str(e)}"
    
    def sell(self, price: float, btc_amount: float) -> Tuple[bool, str]:
        """Execute real sell order on Kraken"""
        try:
            self.logger.info(f"REAL SELL: {btc_amount:.8f} BTC at ${price:,.2f}")
            
            result = self.kraken.place_market_order(
                pair='XBTUSDT',
                side='sell',
                volume=btc_amount
            )
            
            if result['success']:
                self.active_position = None
                return True, f"Real sell executed: {btc_amount:.8f} BTC at ${price:,.2f}"
            else:
                return False, f"Real sell failed: {result.get('error', 'Unknown error')}"
        
        except Exception as e:
            self.logger.error(f"Error in real sell: {e}")
            return False, f"Real sell error: {str(e)}"
    
    def update_trailing_stop(self, price: float) -> Dict:
        """Update trailing stop (managed by TrailingStop class)"""
        return {
            'engine': 'real',
            'current_price': price,
            'position': self.active_position
        }
    
    def get_open_position(self) -> Dict:
        """Get open position from Kraken"""
        if self.active_position:
            return self.active_position
        
        try:
            orders = self.kraken.get_open_orders()
            if orders:
                return {'open_orders': orders}
        except Exception as e:
            self.logger.error(f"Error getting open position: {e}")
        
        return {}
    
    def close_position(self) -> bool:
        """Close position by selling all BTC"""
        try:
            balances = self.load_balances()
            if balances['btc'] > 0:
                ticker = self.kraken.get_ticker()
                current_price = float(ticker.get('c', [0])[0])
                
                success, msg = self.sell(current_price, balances['btc'])
                return success
            return True
        except Exception as e:
            self.logger.error(f"Error closing position: {e}")
            return False
    
    def get_balance(self) -> Dict[str, float]:
        """Get current balances"""
        return self.load_balances()
    
    def get_current_price(self) -> float:
        """Get current BTC price from Kraken"""
        try:
            ticker = self.kraken.get_ticker()
            if ticker and 'c' in ticker:
                price = float(ticker['c'][0])
                return price
            return 0.0
        except Exception as e:
            self.logger.error(f"Error getting current price: {e}")
            return 0.0
