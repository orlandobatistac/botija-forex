"""
Forex Trading Bot Orchestration - OANDA
"""

import logging
import time
from typing import Dict, Optional
from datetime import datetime

from .oanda_client import OandaClient
from .technical_indicators import TechnicalIndicators
from .ai_validator import AISignalValidator
from .telegram_alerts import TelegramAlerts
from ..config import Config

logger = logging.getLogger(__name__)


class ForexTradingBot:
    """Main Forex trading bot orchestrator for OANDA"""

    def __init__(
        self,
        oanda_api_key: str,
        oanda_account_id: str,
        oanda_environment: str = "demo",
        openai_api_key: str = "",
        telegram_token: str = "",
        telegram_chat_id: str = "",
        instrument: str = "EUR_USD",
        trade_amount_usd: float = 0,
        trade_amount_percent: float = 10,
        min_balance_usd: float = 0,
        min_balance_percent: float = 20,
        stop_loss_pips: float = 50,
        take_profit_pips: float = 100,
        trailing_stop_pips: float = 30
    ):
        """Initialize Forex trading bot"""

        # OANDA client
        self.oanda = OandaClient(oanda_api_key, oanda_account_id, oanda_environment) if oanda_api_key else None

        # AI and notifications
        self.ai = AISignalValidator(openai_api_key) if openai_api_key else None
        self.telegram = TelegramAlerts(telegram_token, telegram_chat_id) if telegram_token else None

        # Trading parameters
        self.instrument = instrument
        self.trade_amount_usd = trade_amount_usd
        self.trade_amount_percent = trade_amount_percent
        self.min_balance_usd = min_balance_usd
        self.min_balance_percent = min_balance_percent
        self.stop_loss_pips = stop_loss_pips
        self.take_profit_pips = take_profit_pips
        self.trailing_stop_pips = trailing_stop_pips

        self.is_running = False
        self.logger = logger

        env_display = oanda_environment.upper() if oanda_api_key else "DEMO"
        self.logger.info(f"ForexTradingBot initialized: {instrument} ({env_display})")

    def _calculate_trade_amount(self, balance: float) -> float:
        """Calculate trade amount based on config"""
        if self.trade_amount_usd > 0:
            return self.trade_amount_usd
        return balance * (self.trade_amount_percent / 100)

    def _calculate_min_balance(self, balance: float) -> float:
        """Calculate minimum balance to keep"""
        if self.min_balance_usd > 0:
            return self.min_balance_usd
        return balance * (self.min_balance_percent / 100)

    async def analyze_market(self) -> Dict:
        """Analyze current Forex market conditions"""
        try:
            if not self.oanda:
                self.logger.warning("OANDA client not initialized - using mock data")
                return self._get_mock_analysis()

            # Get current price and spread
            spread_info = self.oanda.get_spread(self.instrument)
            if not spread_info:
                self.logger.warning("No price data available")
                return {}

            current_price = spread_info['mid']
            spread_pips = spread_info['spread_pips']

            # Get account balance
            balance = self.oanda.get_balance()
            nav = self.oanda.get_nav()

            # Get current position
            position_units = self.oanda.get_position_units(self.instrument)
            has_position = position_units != 0

            # Get OHLC data for indicators
            granularity = Config.OANDA_GRANULARITY
            candles = self.oanda.get_candles(
                instrument=self.instrument,
                granularity=granularity,
                count=100
            )

            if not candles:
                self.logger.warning("No candle data available")
                return {}

            # Extract closing prices
            closes = [c['close'] for c in candles]

            # Calculate technical indicators
            tech_signals = TechnicalIndicators.analyze_signals(
                closes,
                ema20_period=Config.EMA_FAST_PERIOD,
                ema50_period=Config.EMA_SLOW_PERIOD,
                rsi_period=Config.RSI_PERIOD
            )

            # Get AI signal
            if self.ai:
                ai_signal = self.ai.get_signal(
                    instrument=self.instrument,
                    price=current_price,
                    ema_fast=tech_signals.get('ema20', 0),
                    ema_slow=tech_signals.get('ema50', 0),
                    rsi=tech_signals.get('rsi14', 0),
                    spread_pips=spread_pips,
                    position_units=position_units,
                    balance=balance
                )
            else:
                ai_signal = {'signal': 'HOLD', 'confidence': 0.5, 'reason': 'No AI configured'}

            # Calculate trade parameters
            trade_amount = self._calculate_trade_amount(balance)
            min_balance_required = self._calculate_min_balance(balance)
            available_to_trade = balance - min_balance_required

            # Calculate units to trade
            units_to_trade = self.oanda.calculate_units_from_usd(trade_amount, self.instrument) if self.oanda else 0

            return {
                'timestamp': datetime.now().isoformat(),
                'instrument': self.instrument,
                'current_price': current_price,
                'bid': spread_info['bid'],
                'ask': spread_info['ask'],
                'spread_pips': spread_pips,
                'balance': balance,
                'nav': nav,
                'position_units': position_units,
                'has_position': has_position,
                'tech_signals': tech_signals,
                'ai_signal': ai_signal,
                'trade_amount_usd': trade_amount,
                'units_to_trade': units_to_trade,
                'min_balance_required': min_balance_required,
                'available_to_trade': available_to_trade,
                'should_buy': (
                    ai_signal['signal'] == 'BUY' and
                    available_to_trade >= trade_amount and
                    not has_position
                ),
                'should_sell': (
                    ai_signal['signal'] == 'SELL' and
                    has_position and
                    position_units > 0  # Long position to close
                ),
                'should_short': (
                    ai_signal['signal'] == 'SELL' and
                    not has_position
                )
            }

        except Exception as e:
            self.logger.error(f"Error analyzing market: {e}")
            if self.telegram:
                self.telegram.send_error_alert(str(e), 'HIGH')
            return {}

    def _get_mock_analysis(self) -> Dict:
        """Return mock analysis for paper trading without OANDA"""
        return {
            'timestamp': datetime.now().isoformat(),
            'instrument': self.instrument,
            'current_price': 1.0850,
            'bid': 1.0849,
            'ask': 1.0851,
            'spread_pips': 2.0,
            'balance': 100000.0,
            'nav': 100000.0,
            'position_units': 0,
            'has_position': False,
            'tech_signals': {'ema20': 1.0840, 'ema50': 1.0820, 'rsi14': 55},
            'ai_signal': {'signal': 'HOLD', 'confidence': 0.5, 'reason': 'Mock data'},
            'trade_amount_usd': 10000.0,
            'units_to_trade': 9200,
            'should_buy': False,
            'should_sell': False,
            'should_short': False
        }

    async def execute_buy(self, analysis: Dict) -> Dict:
        """Execute a buy (long) order"""
        try:
            units = analysis.get('units_to_trade', 0)
            if units <= 0:
                return {'success': False, 'error': 'Invalid units'}

            self.logger.info(f"Executing BUY: {units} units {self.instrument}")

            result = self.oanda.place_market_order(
                instrument=self.instrument,
                units=units,  # Positive = buy/long
                stop_loss_pips=self.stop_loss_pips if self.stop_loss_pips > 0 else None,
                take_profit_pips=self.take_profit_pips if self.take_profit_pips > 0 else None
            )

            if result['success']:
                self.logger.info(f"BUY executed: {result}")

                if self.telegram:
                    self.telegram.send_forex_buy_signal(
                        instrument=self.instrument,
                        price=result.get('price', analysis['current_price']),
                        units=units,
                        stop_loss_pips=self.stop_loss_pips,
                        take_profit_pips=self.take_profit_pips,
                        confidence=analysis['ai_signal']['confidence']
                    )
            else:
                self.logger.error(f"BUY failed: {result.get('error')}")
                if self.telegram:
                    self.telegram.send_error_alert(f"Buy failed: {result.get('error')}")

            return result

        except Exception as e:
            self.logger.error(f"Error executing buy: {e}")
            return {'success': False, 'error': str(e)}

    async def execute_sell(self, analysis: Dict) -> Dict:
        """Execute a sell (close long position)"""
        try:
            self.logger.info(f"Executing SELL/CLOSE: {self.instrument}")

            result = self.oanda.close_position(self.instrument)

            if result['success']:
                self.logger.info(f"SELL executed: {result}")

                if self.telegram:
                    self.telegram.send_forex_sell_signal(
                        instrument=self.instrument,
                        price=result.get('price', analysis['current_price']),
                        units=result.get('units', 0),
                        profit_loss=result.get('pl', 0),
                        trigger='AI_SIGNAL'
                    )
            else:
                self.logger.error(f"SELL failed: {result.get('error')}")
                if self.telegram:
                    self.telegram.send_error_alert(f"Sell failed: {result.get('error')}")

            return result

        except Exception as e:
            self.logger.error(f"Error executing sell: {e}")
            return {'success': False, 'error': str(e)}

    async def run_cycle(self, trigger: str = "scheduled") -> Dict:
        """Execute one trading cycle"""
        from ..models import TradingCycle
        from ..database import SessionLocal

        start_time = time.time()
        cycle_data = {
            'instrument': self.instrument,
            'price': 0,
            'ema_fast': 0,
            'ema_slow': 0,
            'rsi': 0,
            'balance': 0,
            'position_units': 0,
            'ai_signal': 'HOLD',
            'ai_confidence': 0,
            'ai_reason': None,
            'action': 'ERROR',
            'trade_id': None,
            'profit_loss': None,
            'trading_mode': Config.TRADING_MODE,
            'error_message': None
        }

        try:
            self.logger.info(f"📊 Analyzing {self.instrument}...")
            analysis = await self.analyze_market()

            if not analysis:
                self.logger.warning("⚠️ Analysis failed - no data")
                cycle_data['error_message'] = 'Analysis failed - no data'
                cycle_data['action'] = 'ERROR'
                self._save_cycle(cycle_data, int((time.time() - start_time) * 1000), trigger)
                return {'success': False, 'reason': 'Analysis failed'}

            # Update cycle data
            cycle_data['price'] = analysis.get('current_price', 0)
            cycle_data['balance'] = analysis.get('balance', 0)
            cycle_data['position_units'] = analysis.get('position_units', 0)

            tech = analysis.get('tech_signals', {})
            cycle_data['ema_fast'] = tech.get('ema20', 0)
            cycle_data['ema_slow'] = tech.get('ema50', 0)
            cycle_data['rsi'] = tech.get('rsi14', 0)

            ai_sig = analysis.get('ai_signal', {})
            cycle_data['ai_signal'] = ai_sig.get('signal', 'HOLD')
            cycle_data['ai_confidence'] = ai_sig.get('confidence', 0)
            cycle_data['ai_reason'] = ai_sig.get('reason')

            # Log market data
            self.logger.info(f"💱 {self.instrument}: {analysis.get('current_price', 0):.5f} (spread: {analysis.get('spread_pips', 0):.1f} pips)")
            self.logger.info(f"💰 Balance: ${analysis.get('balance', 0):,.2f} | Position: {analysis.get('position_units', 0)} units")
            self.logger.info(f"📈 EMA{Config.EMA_FAST_PERIOD}: {tech.get('ema20', 0):.5f} | EMA{Config.EMA_SLOW_PERIOD}: {tech.get('ema50', 0):.5f} | RSI: {tech.get('rsi14', 0):.1f}")
            self.logger.info(f"🤖 AI Signal: {ai_sig.get('signal', 'N/A')} (confidence: {ai_sig.get('confidence', 0):.0%})")

            # Execute based on signals
            if analysis.get('should_buy'):
                self.logger.info("✅ BUY signal detected - executing")
                result = await self.execute_buy(analysis)
                cycle_data['action'] = 'BOUGHT' if result.get('success') else 'BUY_FAILED'
                cycle_data['trade_id'] = result.get('order_id')

            elif analysis.get('should_sell'):
                self.logger.info("✅ SELL signal detected - closing position")
                result = await self.execute_sell(analysis)
                cycle_data['action'] = 'SOLD' if result.get('success') else 'SELL_FAILED'
                cycle_data['trade_id'] = result.get('order_id')
                cycle_data['profit_loss'] = result.get('pl')

            else:
                self.logger.info("⏸️ No trading signal - HOLD")
                cycle_data['action'] = 'HOLD'

            # Save cycle to database
            execution_time = int((time.time() - start_time) * 1000)
            self._save_cycle(cycle_data, execution_time, trigger)

            return {'success': True, 'analysis': analysis, 'action': cycle_data['action']}

        except Exception as e:
            self.logger.error(f"❌ Error in trading cycle: {e}")
            cycle_data['error_message'] = str(e)
            cycle_data['action'] = 'ERROR'
            self._save_cycle(cycle_data, int((time.time() - start_time) * 1000), trigger)

            if self.telegram:
                self.telegram.send_error_alert(str(e), 'HIGH')

            return {'success': False, 'error': str(e)}

    def _save_cycle(self, cycle_data: Dict, execution_time_ms: int, trigger: str = "scheduled"):
        """Save trading cycle to database"""
        try:
            from ..models import TradingCycle
            from ..database import SessionLocal

            db = SessionLocal()
            cycle = TradingCycle(
                instrument=cycle_data['instrument'],
                price=cycle_data['price'],
                ema_fast=cycle_data['ema_fast'],
                ema_slow=cycle_data['ema_slow'],
                rsi=cycle_data['rsi'],
                balance=cycle_data['balance'],
                position_units=cycle_data['position_units'],
                ai_signal=cycle_data['ai_signal'],
                ai_confidence=cycle_data['ai_confidence'],
                ai_reason=cycle_data['ai_reason'],
                action=cycle_data['action'],
                trade_id=cycle_data['trade_id'],
                profit_loss=cycle_data['profit_loss'],
                execution_time_ms=execution_time_ms,
                trading_mode=cycle_data['trading_mode'],
                trigger=trigger,
                error_message=cycle_data['error_message']
            )
            db.add(cycle)
            db.commit()
            db.close()
            self.logger.info(f"💾 Cycle saved ({execution_time_ms}ms, trigger={trigger})")
        except Exception as e:
            self.logger.error(f"Error saving cycle: {e}")

    async def start(self):
        """Start the trading bot"""
        self.is_running = True
        self.logger.info(f"🟢 Forex Trading Bot started - {self.instrument}")
        if self.telegram:
            self.telegram.send_message(f"🟢 <b>Forex Bot Started</b> 🟢\n\n📊 Instrument: {self.instrument}")

    async def stop(self):
        """Stop the trading bot"""
        self.is_running = False
        self.logger.info(f"🔴 Forex Trading Bot stopped - {self.instrument}")
        if self.telegram:
            self.telegram.send_message(f"🔴 <b>Forex Bot Stopped</b> 🔴\n\n📊 Instrument: {self.instrument}")


# Alias for backwards compatibility
TradingBot = ForexTradingBot
