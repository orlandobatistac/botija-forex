"""
Kraken API client for trading operations
"""

import krakenex
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

class KrakenClient:
    """Kraken Spot API client"""
    
    def __init__(self, api_key: str, api_secret: str):
        """Initialize Kraken API client"""
        self.api = krakenex.API()
        if api_key and api_secret:
            self.api.load_key(api_key, api_secret)
        self.logger = logger
    
    def get_account_balance(self) -> Dict[str, float]:
        """Get current account balances"""
        try:
            response = self.api.query_private('Balance')
            if response.get('error'):
                self.logger.error(f"Balance error: {response['error']}")
                return {}
            return response.get('result', {})
        except Exception as e:
            self.logger.error(f"Error getting balance: {e}")
            return {}
    
    def get_btc_balance(self) -> float:
        """Get BTC balance"""
        balance = self.get_account_balance()
        # Kraken returns XBT for Bitcoin
        return float(balance.get('XXBT', 0.0))
    
    def get_usd_balance(self) -> float:
        """Get USD balance"""
        balance = self.get_account_balance()
        return float(balance.get('ZUSD', 0.0))
    
    def get_ticker(self, pair: str = "XBTUSDT") -> Dict:
        """Get ticker data for a pair"""
        try:
            response = self.api.query_public('Ticker', {'pair': pair})
            if response.get('error'):
                self.logger.error(f"Ticker error: {response['error']}")
                return {}
            return response.get('result', {}).get(pair, {})
        except Exception as e:
            self.logger.error(f"Error getting ticker: {e}")
            return {}
    
    def get_ohlc(self, pair: str = "XBTUSDT", interval: int = 60) -> List:
        """Get OHLC data for technical analysis"""
        try:
            response = self.api.query_public('OHLC', {
                'pair': pair,
                'interval': interval
            })
            if response.get('error'):
                self.logger.error(f"OHLC error: {response['error']}")
                return []
            return response.get('result', {}).get(pair, [])
        except Exception as e:
            self.logger.error(f"Error getting OHLC: {e}")
            return []
    
    def place_limit_order(
        self, 
        pair: str, 
        side: str, 
        price: float, 
        volume: float
    ) -> Dict:
        """Place a limit order"""
        try:
            params = {
                'pair': pair,
                'type': side,  # buy or sell
                'ordertype': 'limit',
                'price': str(price),
                'volume': str(volume)
            }
            response = self.api.query_private('AddOrder', params)
            
            if response.get('error'):
                self.logger.error(f"Order error: {response['error']}")
                return {'success': False, 'error': response['error']}
            
            result = response.get('result', {})
            self.logger.info(f"Order placed: {result}")
            return {
                'success': True,
                'order_id': result.get('txid', [None])[0],
                'description': result.get('descr', {})
            }
        except Exception as e:
            self.logger.error(f"Error placing order: {e}")
            return {'success': False, 'error': str(e)}
    
    def place_market_order(
        self, 
        pair: str, 
        side: str, 
        volume: float
    ) -> Dict:
        """Place a market order"""
        try:
            params = {
                'pair': pair,
                'type': side,  # buy or sell
                'ordertype': 'market',
                'volume': str(volume)
            }
            response = self.api.query_private('AddOrder', params)
            
            if response.get('error'):
                self.logger.error(f"Market order error: {response['error']}")
                return {'success': False, 'error': response['error']}
            
            result = response.get('result', {})
            self.logger.info(f"Market order placed: {result}")
            return {
                'success': True,
                'order_id': result.get('txid', [None])[0],
                'description': result.get('descr', {})
            }
        except Exception as e:
            self.logger.error(f"Error placing market order: {e}")
            return {'success': False, 'error': str(e)}
    
    def cancel_order(self, txid: str) -> Dict:
        """Cancel an open order"""
        try:
            response = self.api.query_private('CancelOrder', {'txid': txid})
            
            if response.get('error'):
                self.logger.error(f"Cancel error: {response['error']}")
                return {'success': False, 'error': response['error']}
            
            self.logger.info(f"Order cancelled: {txid}")
            return {'success': True}
        except Exception as e:
            self.logger.error(f"Error cancelling order: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_open_orders(self) -> List[Dict]:
        """Get list of open orders"""
        try:
            response = self.api.query_private('OpenOrders')
            if response.get('error'):
                self.logger.error(f"Open orders error: {response['error']}")
                return []
            return response.get('result', {}).get('open', {})
        except Exception as e:
            self.logger.error(f"Error getting open orders: {e}")
            return []
