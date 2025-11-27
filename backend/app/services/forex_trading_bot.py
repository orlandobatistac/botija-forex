"""
Forex Trading Bot Orchestration - OANDA
"""

import logging
import time
from typing import Dict, Optional
from datetime import datetime

import pandas as pd

from .oanda_client import OandaClient
from .technical_indicators import TechnicalIndicators
from .ai_validator import AISignalValidator
from .telegram_alerts import TelegramAlerts
from .forex_trailing_stop import ForexTrailingStop
from .multi_timeframe import MultiTimeframeAnalyzer
from .strategies import TripleEMAStrategy, TripleEMASignal
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
        trailing_stop_enabled: bool = True,
        trailing_stop_distance_pips: float = 30,
        trailing_stop_activation_pips: float = 20,
        use_triple_ema_strategy: bool = False,
        triple_ema_rr_ratio: float = 2.0
    ):
        """Initialize Forex trading bot"""

        # Logger first
        self.logger = logger
        self.is_running = False

        # OANDA client
        self.oanda = OandaClient(oanda_api_key, oanda_account_id, oanda_environment) if oanda_api_key else None

        # Triple EMA Strategy (Fase 0)
        self.use_triple_ema = use_triple_ema_strategy
        self.triple_ema_strategy = None
        if self.use_triple_ema:
            self.triple_ema_strategy = TripleEMAStrategy(
                rr_ratio=triple_ema_rr_ratio,
                use_adx_filter=True,
                use_slope_filter=True
            )
            self.logger.info("📈 Triple EMA Strategy enabled (Fase 0)")

        # AI and notifications (always create AI validator to show warning if not configured)
        self.ai = AISignalValidator(openai_api_key)
        self.telegram = TelegramAlerts(telegram_token, telegram_chat_id) if telegram_token else None

        # Trailing Stop
        self.trailing_stop_enabled = trailing_stop_enabled
        self.trailing_stop = None
        if trailing_stop_enabled and self.oanda:
            self.trailing_stop = ForexTrailingStop(
                oanda_client=self.oanda,
                trailing_distance_pips=trailing_stop_distance_pips,
                activation_pips=trailing_stop_activation_pips
            )
            self.logger.info(f"📍 Trailing stop enabled: {trailing_stop_distance_pips} pips (activates at +{trailing_stop_activation_pips} pips)")

        # Risk Manager
        self.risk_manager = None

        # Multi-timeframe Analyzer
        self.multi_tf_enabled = Config.MULTI_TIMEFRAME_ENABLED if hasattr(Config, 'MULTI_TIMEFRAME_ENABLED') else True
        self.multi_tf = None
        if self.multi_tf_enabled and self.oanda:
            self.multi_tf = MultiTimeframeAnalyzer(self.oanda, instrument)
            self.logger.info("📊 Multi-timeframe analysis enabled (H1+H4)")

        # Trading parameters
        self.instrument = instrument
        self.trade_amount_usd = trade_amount_usd
        self.trade_amount_percent = trade_amount_percent
        self.min_balance_usd = min_balance_usd
        self.min_balance_percent = min_balance_percent
        self.stop_loss_pips = stop_loss_pips
        self.take_profit_pips = take_profit_pips

        env_display = oanda_environment.upper() if oanda_api_key else "DEMO"
        self.logger.info(f"ForexTradingBot initialized: {instrument} ({env_display})")

    def set_risk_manager(self, risk_manager):
        """Set external risk manager"""
        self.risk_manager = risk_manager
        self.logger.info("🛡️ Risk Manager attached")

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

    def _candles_to_dataframe(self, candles: list) -> pd.DataFrame:
        """Convert OANDA candles to pandas DataFrame for strategy analysis."""
        df = pd.DataFrame(candles)
        # Ensure required columns exist
        required = ['open', 'high', 'low', 'close']
        for col in required:
            if col not in df.columns:
                self.logger.error(f"Missing column in candles: {col}")
                return pd.DataFrame()
        return df

    def _analyze_with_triple_ema(self, candles: list) -> TripleEMASignal:
        """Analyze market using Triple EMA strategy."""
        if not self.triple_ema_strategy:
            return TripleEMASignal(direction="WAIT", reason="Strategy not initialized")

        df = self._candles_to_dataframe(candles)
        if df.empty:
            return TripleEMASignal(direction="WAIT", reason="No valid candle data")

        signal = self.triple_ema_strategy.analyze(df)

        self.logger.info(
            f"Triple EMA Signal: {signal.direction} | "
            f"Confidence: {signal.confidence:.0%} | "
            f"Reason: {signal.reason}"
        )

        return signal

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

            # Get OHLC data for indicators (need 250 for EMA 200)
            granularity = Config.OANDA_GRANULARITY
            candle_count = 250 if self.use_triple_ema else 100
            candles = self.oanda.get_candles(
                instrument=self.instrument,
                granularity=granularity,
                count=candle_count
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

            # ═══════════════════════════════════════════════════════════════
            # TRIPLE EMA STRATEGY (if enabled)
            # ═══════════════════════════════════════════════════════════════
            triple_ema_signal = None
            if self.use_triple_ema:
                triple_ema_signal = self._analyze_with_triple_ema(candles)

            # Get AI signal (fallback or complementary)
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
                ai_signal = {'signal': 'HOLD', 'confidence': 0.0, 'reason': '⚠️ AI not initialized'}

            # Multi-timeframe confirmation
            mtf_signal = None
            mtf_confirmed = True  # Default to True if MTF disabled

            if self.multi_tf and self.multi_tf_enabled:
                mtf_signal = self.multi_tf.get_confirmed_signal()
                mtf_confirmed = mtf_signal.get('confirmation', False)

                if not mtf_confirmed:
                    self.logger.info(f"⏳ Multi-TF not confirmed: {mtf_signal.get('reason', 'waiting')}")

            # Calculate trade parameters
            trade_amount = self._calculate_trade_amount(balance)
            min_balance_required = self._calculate_min_balance(balance)
            available_to_trade = balance - min_balance_required

            # Calculate units to trade
            units_to_trade = self.oanda.calculate_units_from_usd(trade_amount, self.instrument) if self.oanda else 0

            # ═══════════════════════════════════════════════════════════════
            # DECISION LOGIC: Triple EMA vs AI
            # ═══════════════════════════════════════════════════════════════
            if self.use_triple_ema and triple_ema_signal:
                # Use Triple EMA strategy
                should_buy = (
                    triple_ema_signal.direction == 'LONG' and
                    triple_ema_signal.confidence >= 0.6 and
                    available_to_trade >= trade_amount and
                    not has_position
                )
                should_short = (
                    triple_ema_signal.direction == 'SHORT' and
                    triple_ema_signal.confidence >= 0.6 and
                    available_to_trade >= trade_amount and
                    not has_position
                )
                # Use Triple EMA levels for SL/TP
                strategy_sl = triple_ema_signal.stop_loss
                strategy_tp = triple_ema_signal.take_profit
                strategy_entry = triple_ema_signal.entry_price
            else:
                # Use AI signal (original behavior)
                should_buy = (
                    ai_signal['signal'] == 'BUY' and
                    ai_signal.get('confidence', 0) >= 0.6 and
                    mtf_confirmed and
                    available_to_trade >= trade_amount and
                    not has_position
                )
                should_short = (
                    ai_signal['signal'] == 'SELL' and
                    ai_signal.get('confidence', 0) >= 0.6 and
                    mtf_confirmed and
                    available_to_trade >= trade_amount and
                    not has_position
                )
                strategy_sl = None
                strategy_tp = None
                strategy_entry = None

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
                'triple_ema_signal': triple_ema_signal.to_dict() if triple_ema_signal else None,
                'mtf_signal': mtf_signal,
                'mtf_confirmed': mtf_confirmed,
                'trade_amount_usd': trade_amount,
                'units_to_trade': units_to_trade,
                'min_balance_required': min_balance_required,
                'available_to_trade': available_to_trade,
                # Strategy-calculated levels
                'strategy_entry': strategy_entry,
                'strategy_sl': strategy_sl,
                'strategy_tp': strategy_tp,
                'should_buy': should_buy,
                'should_sell': (
                    ai_signal['signal'] == 'SELL' and
                    has_position and
                    position_units > 0  # Long position to close
                ),
                'should_short': should_short,
                'should_cover': (
                    ai_signal['signal'] == 'BUY' and
                    has_position and
                    position_units < 0  # Short position to close
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

            # Use strategy SL/TP if available (Triple EMA), otherwise use default pips
            strategy_sl = analysis.get('strategy_sl')
            strategy_tp = analysis.get('strategy_tp')

            if strategy_sl and strategy_tp:
                # Triple EMA provides absolute price levels
                self.logger.info(f"Using Triple EMA levels - SL: {strategy_sl}, TP: {strategy_tp}")
                result = self.oanda.place_market_order(
                    instrument=self.instrument,
                    units=units,
                    stop_loss_price=strategy_sl,
                    take_profit_price=strategy_tp
                )
            else:
                # Default: use pips
                result = self.oanda.place_market_order(
                    instrument=self.instrument,
                    units=units,
                    stop_loss_pips=self.stop_loss_pips if self.stop_loss_pips > 0 else None,
                    take_profit_pips=self.take_profit_pips if self.take_profit_pips > 0 else None
                )

            if result['success']:
                self.logger.info(f"BUY executed: {result}")

                # Start trailing stop
                if self.trailing_stop:
                    self.trailing_stop.start_trailing(
                        instrument=self.instrument,
                        direction='LONG',
                        entry_price=result.get('price', analysis['current_price'])
                    )

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

                # Stop trailing stop
                if self.trailing_stop:
                    self.trailing_stop.stop_trailing(self.instrument)

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

    async def execute_short(self, analysis: Dict) -> Dict:
        """Execute a short (sell) order - open short position"""
        try:
            units = analysis.get('units_to_trade', 0)
            if units <= 0:
                return {'success': False, 'error': 'Invalid units'}

            self.logger.info(f"Executing SHORT: {units} units {self.instrument}")

            # Use strategy SL/TP if available (Triple EMA), otherwise use default pips
            strategy_sl = analysis.get('strategy_sl')
            strategy_tp = analysis.get('strategy_tp')

            if strategy_sl and strategy_tp:
                # Triple EMA provides absolute price levels
                self.logger.info(f"Using Triple EMA levels - SL: {strategy_sl}, TP: {strategy_tp}")
                result = self.oanda.place_market_order(
                    instrument=self.instrument,
                    units=-units,  # Negative = sell/short
                    stop_loss_price=strategy_sl,
                    take_profit_price=strategy_tp
                )
            else:
                # Default: use pips
                result = self.oanda.place_market_order(
                    instrument=self.instrument,
                    units=-units,
                    stop_loss_pips=self.stop_loss_pips if self.stop_loss_pips > 0 else None,
                    take_profit_pips=self.take_profit_pips if self.take_profit_pips > 0 else None
                )

            if result['success']:
                self.logger.info(f"SHORT executed: {result}")

                # Start trailing stop for SHORT
                if self.trailing_stop:
                    self.trailing_stop.start_trailing(
                        instrument=self.instrument,
                        direction='SHORT',
                        entry_price=result.get('price', analysis['current_price'])
                    )

                if self.telegram:
                    self.telegram.send_forex_short_signal(
                        instrument=self.instrument,
                        price=result.get('price', analysis['current_price']),
                        units=units,
                        stop_loss_pips=self.stop_loss_pips,
                        take_profit_pips=self.take_profit_pips,
                        confidence=analysis['ai_signal']['confidence']
                    )
            else:
                self.logger.error(f"SHORT failed: {result.get('error')}")
                if self.telegram:
                    self.telegram.send_error_alert(f"Short failed: {result.get('error')}")

            return result

        except Exception as e:
            self.logger.error(f"Error executing short: {e}")
            return {'success': False, 'error': str(e)}

    async def run_cycle(self, trigger: str = "scheduled") -> Dict:
        """Execute one trading cycle"""
        from ..models import TradingCycle
        from ..database import SessionLocal

        start_time = time.time()
        strategy_name = "Triple EMA" if self.use_triple_ema else "Legacy"
        cycle_data = {
            'instrument': self.instrument,
            'price': 0,
            'ema_fast': 0,
            'ema_slow': 0,
            'rsi': 0,
            'balance': 0,
            'position_units': 0,
            'ai_signal': 'NEUTRAL',
            'ai_confidence': 0,
            'ai_reason': None,
            'action': 'ERROR',
            'trade_id': None,
            'profit_loss': None,
            'trading_mode': Config.TRADING_MODE,
            'strategy': strategy_name,
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

            # Signal: use Triple EMA if enabled, otherwise AI
            triple_ema_result = analysis.get('triple_ema_signal')
            if self.use_triple_ema and triple_ema_result:
                # Map Triple EMA direction to signal format
                direction = triple_ema_result.get('direction', 'WAIT')
                if direction == 'LONG':
                    cycle_data['ai_signal'] = 'BUY'
                elif direction == 'SHORT':
                    cycle_data['ai_signal'] = 'SELL'
                else:
                    cycle_data['ai_signal'] = 'NEUTRAL'
                cycle_data['ai_confidence'] = triple_ema_result.get('confidence', 0)
                cycle_data['ai_reason'] = triple_ema_result.get('reason', '')
            else:
                ai_sig = analysis.get('ai_signal', {})
                cycle_data['ai_signal'] = ai_sig.get('signal', 'HOLD')
                cycle_data['ai_confidence'] = ai_sig.get('confidence', 0)
                cycle_data['ai_reason'] = ai_sig.get('reason')

            # Log market data
            self.logger.info(f"💱 {self.instrument}: {analysis.get('current_price', 0):.5f} (spread: {analysis.get('spread_pips', 0):.1f} pips)")
            self.logger.info(f"💰 Balance: ${analysis.get('balance', 0):,.2f} | Position: {analysis.get('position_units', 0)} units")
            self.logger.info(f"📈 EMA{Config.EMA_FAST_PERIOD}: {tech.get('ema20', 0):.5f} | EMA{Config.EMA_SLOW_PERIOD}: {tech.get('ema50', 0):.5f} | RSI: {tech.get('rsi14', 0):.1f}")
            self.logger.info(f"🤖 Signal: {cycle_data['ai_signal']} (confidence: {cycle_data['ai_confidence']:.0%}) - Strategy: {strategy_name}")

            # Update trailing stop if position exists
            trailing_result = None
            if self.trailing_stop and analysis.get('has_position'):
                trailing_result = self.trailing_stop.update(
                    self.instrument,
                    analysis.get('current_price', 0)
                )
                if trailing_result.get('activated'):
                    self.logger.info(f"📍 Trailing: +{trailing_result.get('profit_pips', 0):.1f} pips | Stop: {trailing_result.get('new_stop', 0):.5f}")

                # Check if trailing stop was hit
                if trailing_result.get('should_close'):
                    self.logger.warning("🛑 TRAILING STOP HIT - closing position")
                    result = await self.execute_sell(analysis)
                    cycle_data['action'] = 'TRAILING_STOP' if result.get('success') else 'TRAILING_FAILED'
                    cycle_data['trade_id'] = result.get('order_id')
                    cycle_data['profit_loss'] = result.get('pl')

                    # Record trade in risk manager
                    if self.risk_manager and result.get('pl'):
                        self.risk_manager.record_trade(result.get('pl'))

                    execution_time = int((time.time() - start_time) * 1000)
                    self._save_cycle(cycle_data, execution_time, trigger)
                    return {'success': True, 'analysis': analysis, 'action': cycle_data['action']}

            # Check risk manager before trading
            risk_status = None
            if self.risk_manager:
                risk_status = self.risk_manager.update_balance(analysis.get('balance', 0))
                if not risk_status['can_trade']:
                    self.logger.warning(f"🛡️ Risk Manager: Trading blocked - {risk_status.get('warnings', [])}")
                    cycle_data['action'] = 'RISK_BLOCKED'
                    execution_time = int((time.time() - start_time) * 1000)
                    self._save_cycle(cycle_data, execution_time, trigger)
                    return {'success': True, 'analysis': analysis, 'action': 'RISK_BLOCKED', 'reason': risk_status.get('warnings')}

            # Execute based on signals
            if analysis.get('should_buy'):
                self.logger.info("✅ BUY signal detected - opening LONG")
                result = await self.execute_buy(analysis)
                cycle_data['action'] = 'BOUGHT' if result.get('success') else 'BUY_FAILED'
                cycle_data['trade_id'] = result.get('order_id')

            elif analysis.get('should_sell'):
                self.logger.info("✅ SELL signal detected - closing LONG position")
                result = await self.execute_sell(analysis)
                cycle_data['action'] = 'SOLD' if result.get('success') else 'SELL_FAILED'
                cycle_data['trade_id'] = result.get('order_id')
                cycle_data['profit_loss'] = result.get('pl')

                # Record trade in risk manager
                if self.risk_manager and result.get('success') and result.get('pl') is not None:
                    self.risk_manager.record_trade(result.get('pl'))

            elif analysis.get('should_short'):
                self.logger.info("✅ SHORT signal detected - opening SHORT")
                result = await self.execute_short(analysis)
                cycle_data['action'] = 'SHORTED' if result.get('success') else 'SHORT_FAILED'
                cycle_data['trade_id'] = result.get('order_id')

            elif analysis.get('should_cover'):
                self.logger.info("✅ COVER signal detected - closing SHORT position")
                result = await self.execute_sell(analysis)  # Close position works for both
                cycle_data['action'] = 'COVERED' if result.get('success') else 'COVER_FAILED'
                cycle_data['trade_id'] = result.get('order_id')
                cycle_data['profit_loss'] = result.get('pl')

                # Record trade in risk manager
                if self.risk_manager and result.get('success') and result.get('pl') is not None:
                    self.risk_manager.record_trade(result.get('pl'))

            else:
                self.logger.info("⏸️ No trading signal - SKIP")
                cycle_data['action'] = 'SKIP'

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
                strategy=cycle_data.get('strategy', 'Legacy'),
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
