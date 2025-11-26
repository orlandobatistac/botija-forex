"""
Paper trading mode - simulates trades with real market data
"""

import logging
import requests
from datetime import datetime
from typing import Dict, Tuple
from .base import TradingEngine

logger = logging.getLogger(__name__)

class PaperTradingEngine(TradingEngine):
    """Paper trading engine - simulates trades using database"""
    
    def __init__(self):
        """Initialize paper trading engine"""
        self.logger = logger
        self._init_bot_status()
    
    def _init_bot_status(self):
        """Initialize or get bot status from database"""
        from ...database import SessionLocal
        from ...models import BotStatus
        
        db = SessionLocal()
        try:
            status = db.query(BotStatus).filter(BotStatus.trading_mode == "PAPER").first()
            if not status:
                # Create default paper trading status
                status = BotStatus(
                    is_running=True,
                    trading_mode="PAPER",
                    btc_balance=0.0,
                    usd_balance=1000.0,  # Start with $1000
                    last_buy_price=None,
                    trailing_stop_price=None
                )
                db.add(status)
                db.commit()
                self.logger.info("Created new PAPER trading status with $1000 USD")
        except Exception as e:
            self.logger.error(f"Error initializing bot status: {e}")
            db.rollback()
        finally:
            db.close()
    
    def _get_status(self):
        """Get current bot status from database"""
        from ...database import SessionLocal
        from ...models import BotStatus
        
        db = SessionLocal()
        try:
            return db.query(BotStatus).filter(BotStatus.trading_mode == "PAPER").first()
        finally:
            db.close()
    
    def _update_status(self, **kwargs):
        """Update bot status in database"""
        from ...database import SessionLocal
        from ...models import BotStatus
        
        db = SessionLocal()
        try:
            status = db.query(BotStatus).filter(BotStatus.trading_mode == "PAPER").first()
            if status:
                for key, value in kwargs.items():
                    setattr(status, key, value)
                db.commit()
        except Exception as e:
            self.logger.error(f"Error updating status: {e}")
            db.rollback()
        finally:
            db.close()
    
    def _save_trade(self, order_type: str, price: float, quantity: float, status_obj=None):
        """Save trade to database"""
        from ...database import SessionLocal
        from ...models import Trade
        import uuid
        
        db = SessionLocal()
        try:
            trade = Trade(
                trade_id=f"PAPER-{uuid.uuid4().hex[:8]}",
                order_type=order_type,
                symbol="BTCUSD",
                entry_price=price,
                quantity=quantity,
                status="CLOSED" if order_type == "SELL" else "OPEN",
                trading_mode="PAPER"
            )
            db.add(trade)
            db.commit()
            self.logger.info(f"Trade saved to DB: {order_type} {quantity:.8f} BTC at ${price:.2f}")
        except Exception as e:
            self.logger.error(f"Error saving trade: {e}")
            db.rollback()
        finally:
            db.close()
    
    def load_balances(self) -> Dict[str, float]:
        """Load simulated balances from database"""
        status = self._get_status()
        if status:
            return {
                'btc': status.btc_balance,
                'usd': status.usd_balance
            }
        return {'btc': 0.0, 'usd': 1000.0}
    
    def buy(self, price: float, usd_amount: float) -> Tuple[bool, str]:
        """Execute simulated buy order"""
        status = self._get_status()
        
        if not status:
            return False, "Bot status not found"
        
        if status.usd_balance < usd_amount:
            return False, f"Insufficient USD balance: ${status.usd_balance:.2f}"
        
        # Calculate BTC quantity
        btc_quantity = usd_amount / price
        
        # Initialize trailing stop at 99% of entry price
        initial_stop = price * 0.99
        
        # Update balances and set trailing stop
        self._update_status(
            usd_balance=status.usd_balance - usd_amount,
            btc_balance=status.btc_balance + btc_quantity,
            last_buy_price=price,
            trailing_stop_price=initial_stop
        )
        
        # Save trade
        self._save_trade("BUY", price, btc_quantity, status)
        
        msg = f"📈 PAPER BUY: {btc_quantity:.8f} BTC at ${price:.2f} = ${usd_amount:.2f}"
        self.logger.info(msg)
        return True, msg
    
    def sell(self, price: float, btc_amount: float) -> Tuple[bool, str]:
        """Execute simulated sell order"""
        status = self._get_status()
        
        if not status:
            return False, "Bot status not found"
        
        if status.btc_balance < btc_amount:
            return False, f"Insufficient BTC balance: {status.btc_balance:.8f}"
        
        # Calculate USD proceeds
        usd_proceeds = btc_amount * price
        
        # Update balances
        self._update_status(
            usd_balance=status.usd_balance + usd_proceeds,
            btc_balance=status.btc_balance - btc_amount,
            last_buy_price=None,
            trailing_stop_price=None
        )
        
        # Save trade
        self._save_trade("SELL", price, btc_amount, status)
        
        msg = f"📉 PAPER SELL: {btc_amount:.8f} BTC at ${price:.2f} = ${usd_proceeds:.2f}"
        self.logger.info(msg)
        return True, msg
    
    def get_market_price(self) -> float:
        """Get current BTC price from Kraken"""
        try:
            response = requests.get('https://api.kraken.com/0/public/Ticker?pair=XBTUSD', timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'result' in data and 'XXBTZUSD' in data['result']:
                    price = float(data['result']['XXBTZUSD']['c'][0])
                    return price
        except Exception as e:
            self.logger.error(f"Error fetching price: {e}")
        
        return 0.0
    
    def update_trailing_stop(self, price: float) -> Dict:
        """Update trailing stop simulation"""
        status = self._get_status()
        
        if not status or status.btc_balance == 0:
            return {
                'engine': 'paper',
                'current_price': price,
                'trailing_stop': None,
                'btc_balance': 0.0,
                'should_sell': False
            }
        
        # Initialize trailing stop if needed
        current_stop = status.trailing_stop_price or (price * 0.99)
        
        # Move stop up if price went higher
        new_stop = max(current_stop, price * 0.99)
        
        if new_stop > current_stop:
            self._update_status(trailing_stop_price=new_stop)
            self.logger.info(f"📊 Trailing stop updated to ${new_stop:,.2f}")
        
        # Check if should sell
        should_sell = price <= new_stop
        
        return {
            'engine': 'paper',
            'current_price': price,
            'trailing_stop': new_stop,
            'btc_balance': status.btc_balance,
            'should_sell': should_sell,
            'distance_to_stop': price - new_stop
        }
    
    def get_open_position(self) -> Dict:
        """Get simulated open position"""
        status = self._get_status()
        
        if status and status.btc_balance > 0:
            return {
                'btc_balance': status.btc_balance,
                'entry_price': status.last_buy_price,
                'trailing_stop': status.trailing_stop_price,
                'mode': 'paper'
            }
        return {}
    
    def close_position(self) -> bool:
        """Close simulated position"""
        try:
            self._update_status(
                btc_balance=0.0,
                last_buy_price=None,
                trailing_stop_price=None
            )
            return True
        except Exception as e:
            self.logger.error(f"Error closing position: {e}")
            return False
    
    def reset_wallet(self, initial_usd: float = 1000.0):
        """Reset wallet to initial state"""
        from ...database import SessionLocal
        from ...models import BotStatus
        
        db = SessionLocal()
        try:
            status = db.query(BotStatus).filter(BotStatus.trading_mode == "PAPER").first()
            if status:
                status.usd_balance = initial_usd
                status.btc_balance = 0.0
                status.last_buy_price = None
                status.trailing_stop_price = None
                db.commit()
                self.logger.info(f"💰 Paper wallet reset to ${initial_usd:.2f}")
        except Exception as e:
            self.logger.error(f"Error resetting wallet: {e}")
            db.rollback()
        finally:
            db.close()
    
    def get_wallet_summary(self) -> Dict:
        """Get complete wallet summary"""
        status = self._get_status()
        
        if status:
            return {
                'mode': 'paper',
                'usd_balance': status.usd_balance,
                'btc_balance': status.btc_balance,
                'last_buy_price': status.last_buy_price,
                'trailing_stop': status.trailing_stop_price
            }
        
        return {
            'mode': 'paper',
            'usd_balance': 0.0,
            'btc_balance': 0.0,
            'last_buy_price': None,
            'trailing_stop': None
        }
    
    def get_balance(self) -> Dict[str, float]:
        """Get current balances"""
        return self.load_balances()
    
    def get_current_price(self) -> float:
        """Get current BTC price from Kraken public API"""
        return self.get_market_price()
