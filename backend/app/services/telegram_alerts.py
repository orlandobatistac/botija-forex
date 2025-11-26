"""
Telegram alerts system for Forex Trading
"""

import requests
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class TelegramAlerts:
    """Telegram bot for Forex trading alerts"""

    def __init__(self, token: str, chat_id: str):
        """Initialize Telegram bot"""
        self.token = token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{token}/sendMessage"
        self.logger = logger

    def send_message(self, message: str) -> bool:
        """Send a message to Telegram chat"""
        if not self.token or not self.chat_id:
            self.logger.debug("Telegram not configured, skipping message")
            return False

        try:
            payload = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }

            response = requests.post(self.api_url, json=payload, timeout=10)

            if response.status_code == 200:
                self.logger.info("Telegram message sent")
                return True
            else:
                self.logger.error(f"Telegram error: {response.text}")
                return False
        except Exception as e:
            self.logger.error(f"Error sending Telegram message: {e}")
            return False

    def send_buy_signal(
        self,
        instrument: str,
        price: float,
        units: int,
        stop_loss_pips: float,
        take_profit_pips: float,
        confidence: float
    ) -> bool:
        """Send buy signal alert"""
        message = f"""
🟢 <b>BUY {instrument}</b> 🟢

💰 Entry: <code>{price:.5f}</code>
📊 Units: <code>{units:,}</code>
🛑 SL: <code>{stop_loss_pips:.0f} pips</code>
🎯 TP: <code>{take_profit_pips:.0f} pips</code>
📈 Confidence: <code>{confidence:.0%}</code>

<i>Order sent to OANDA</i>
"""
        return self.send_message(message)

    def send_sell_signal(
        self,
        instrument: str,
        price: float,
        units: int,
        profit_loss: float,
        profit_loss_pips: float = 0,
        trigger: str = 'AI_SIGNAL'
    ) -> bool:
        """Send sell/close signal alert"""
        pnl_emoji = '📈' if profit_loss >= 0 else '📉'

        message = f"""
🔴 <b>CLOSE {instrument}</b> 🔴

📍 Exit Price: <code>{price:.5f}</code>
📊 Units: <code>{abs(units):,}</code>
{pnl_emoji} P/L: <code>${profit_loss:+,.2f}</code> ({profit_loss_pips:+.1f} pips)
🎫 Trigger: <code>{trigger}</code>

<i>Position closed on OANDA</i>
"""
        return self.send_message(message)

    def send_forex_short_signal(
        self,
        instrument: str,
        price: float,
        units: int,
        stop_loss_pips: float,
        take_profit_pips: float,
        confidence: float
    ) -> bool:
        """Send short signal notification"""
        message = f"""
🔴 <b>SHORT {instrument}</b> 🔴

📍 Entry Price: <code>{price:.5f}</code>
📊 Units: <code>{units:,}</code>
🛑 Stop Loss: <code>{stop_loss_pips:.1f}</code> pips
🎯 Take Profit: <code>{take_profit_pips:.1f}</code> pips
🤖 AI Confidence: <code>{confidence:.0%}</code>

<i>Bearish position opened on OANDA</i>
"""
        return self.send_message(message)

    def send_cycle_summary(
        self,
        instrument: str,
        price: float,
        signal: str,
        confidence: float,
        action: str,
        balance: float,
        position_units: int
    ) -> bool:
        """Send trading cycle summary"""
        signal_emoji = '🟢' if signal == 'BUY' else '🔴' if signal == 'SELL' else '⚪'
        position_str = f"{position_units:,} units" if position_units != 0 else "Flat"

        message = f"""
📊 <b>CYCLE COMPLETE</b> 📊

💱 {instrument}: <code>{price:.5f}</code>
{signal_emoji} Signal: <code>{signal}</code> ({confidence:.0%})
⚡ Action: <code>{action}</code>
💰 Balance: <code>${balance:,.2f}</code>
📈 Position: <code>{position_str}</code>
"""
        return self.send_message(message)

    def send_daily_status(
        self,
        instrument: str,
        balance: float,
        nav: float,
        position_units: int,
        daily_pnl: float
    ) -> bool:
        """Send daily status report"""
        pnl_emoji = '📈' if daily_pnl >= 0 else '📉'
        position_str = f"{position_units:,} units" if position_units != 0 else "Flat"

        message = f"""
📊 <b>DAILY STATUS</b> 📊

💱 Instrument: <code>{instrument}</code>
💰 Balance: <code>${balance:,.2f}</code>
💼 NAV: <code>${nav:,.2f}</code>
📈 Position: <code>{position_str}</code>
{pnl_emoji} Daily P/L: <code>${daily_pnl:+,.2f}</code>

⏰ <i>Status: {'🟢 ACTIVE' if position_units != 0 else '⚪ MONITORING'}</i>
"""
        return self.send_message(message)

    def send_error_alert(self, error_message: str, severity: str = 'HIGH') -> bool:
        """Send error alert"""
        severity_emoji = '🔴' if severity == 'HIGH' else '🟡' if severity == 'MEDIUM' else '⚪'

        message = f"""
{severity_emoji} <b>BOT ERROR</b> {severity_emoji}

<b>Severity:</b> <code>{severity}</code>

<b>Error:</b>
<pre>{error_message[:500]}</pre>

<i>Check bot status</i>
"""
        return self.send_message(message)

    def send_bot_started(self, instrument: str, mode: str) -> bool:
        """Send bot started notification"""
        message = f"""
🚀 <b>BOTIJA FOREX STARTED</b> 🚀

💱 Instrument: <code>{instrument}</code>
🎮 Mode: <code>{mode}</code>

<i>Bot is now monitoring the market</i>
"""
        return self.send_message(message)

    def send_bot_stopped(self, instrument: str) -> bool:
        """Send bot stopped notification"""
        message = f"""
🛑 <b>BOTIJA FOREX STOPPED</b> 🛑

💱 Instrument: <code>{instrument}</code>

<i>Bot has been stopped</i>
"""
        return self.send_message(message)
