"""
Telegram alerts system
"""

import requests
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class TelegramAlerts:
    """Telegram bot for trading alerts"""
    
    def __init__(self, token: str, chat_id: str):
        """Initialize Telegram bot"""
        self.token = token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{token}/sendMessage"
        self.logger = logger
    
    def send_message(self, message: str) -> bool:
        """Send a message to Telegram chat"""
        try:
            payload = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            
            response = requests.post(self.api_url, json=payload, timeout=10)
            
            if response.status_code == 200:
                self.logger.info("Telegram message sent successfully")
                return True
            else:
                self.logger.error(f"Telegram error: {response.text}")
                return False
        except Exception as e:
            self.logger.error(f"Error sending Telegram message: {e}")
            return False
    
    def send_buy_signal(self, price: float, quantity: float, confidence: float) -> bool:
        """Send buy signal alert"""
        message = f"""
🟢 <b>BUY SIGNAL</b> 🟢

💰 Entry Price: <code>${price:,.2f}</code>
📊 Quantity: <code>{quantity:.8f} BTC</code>
🎯 Confidence: <code>{confidence*100:.1f}%</code>

<i>Order placed on Kraken</i>
"""
        return self.send_message(message)
    
    def send_sell_signal(
        self, 
        entry_price: float, 
        exit_price: float, 
        profit_loss: float,
        trigger: str = 'AI_SIGNAL'
    ) -> bool:
        """Send sell signal alert"""
        pnl_emoji = '📈' if profit_loss > 0 else '📉'
        
        message = f"""
🔴 <b>SELL SIGNAL</b> 🔴

📍 Entry Price: <code>${entry_price:,.2f}</code>
📍 Exit Price: <code>${exit_price:,.2f}</code>
{pnl_emoji} P/L: <code>${profit_loss:+,.2f}</code>

🎫 Trigger: <code>{trigger}</code>

<i>Order executed on Kraken</i>
"""
        return self.send_message(message)
    
    def send_trailing_stop_update(self, current_price: float, trailing_stop: float) -> bool:
        """Send trailing stop update"""
        message = f"""
📌 <b>TRAILING STOP UPDATE</b> 📌

💹 Current Price: <code>${current_price:,.2f}</code>
🛑 Trailing Stop: <code>${trailing_stop:,.2f}</code>
📊 Profit Lock: <code>${current_price - trailing_stop:,.2f}</code>

<i>Stop automatically adjusted</i>
"""
        return self.send_message(message)
    
    def send_daily_status(
        self,
        btc_balance: float,
        usd_balance: float,
        open_trades: int,
        daily_pnl: float
    ) -> bool:
        """Send daily status report"""
        pnl_emoji = '📈' if daily_pnl > 0 else '📉'
        
        message = f"""
📊 <b>DAILY BOT STATUS</b> 📊

💼 Portfolio:
   • BTC: <code>{btc_balance:.8f}</code>
   • USD: <code>${usd_balance:,.2f}</code>

📈 Open Trades: <code>{open_trades}</code>
{pnl_emoji} Daily P/L: <code>${daily_pnl:+,.2f}</code>

⏰ <i>Status: {('🟢 ACTIVE' if btc_balance > 0 or open_trades > 0 else '⚪ MONITORING')}</i>
"""
        return self.send_message(message)
    
    def send_error_alert(self, error_message: str, severity: str = 'HIGH') -> bool:
        """Send error alert"""
        severity_emoji = '🔴' if severity == 'HIGH' else '🟡' if severity == 'MEDIUM' else '⚪'
        
        message = f"""
{severity_emoji} <b>BOT ERROR ALERT</b> {severity_emoji}

<b>Severity:</b> <code>{severity}</code>

<b>Error:</b>
<pre>{error_message[:500]}</pre>

<i>Please check bot status immediately</i>
"""
        return self.send_message(message)
