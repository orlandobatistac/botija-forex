"""
Multi-timeframe analysis for signal confirmation
Reduces false signals by confirming across H1 + H4 timeframes
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

from .technical_indicators import TechnicalIndicators

logger = logging.getLogger(__name__)


class TimeframeSignal(Enum):
    """Signal types"""
    LONG = "LONG"
    SHORT = "SHORT"
    HOLD = "HOLD"


@dataclass
class TimeframeAnalysis:
    """Analysis result for a single timeframe"""
    timeframe: str
    signal: TimeframeSignal
    ema20: float
    ema50: float
    rsi14: float
    trend_strength: float  # 0-100
    is_aligned: bool  # EMAs aligned with signal


class MultiTimeframeAnalyzer:
    """
    Multi-timeframe analysis for Forex trading.
    Uses H1 for entry timing and H4 for trend confirmation.
    """

    def __init__(self, oanda_client, instrument: str = "EUR_USD"):
        """
        Initialize multi-timeframe analyzer.

        Args:
            oanda_client: OANDA API client instance
            instrument: Currency pair to analyze
        """
        self.oanda = oanda_client
        self.instrument = instrument
        self.indicators = TechnicalIndicators()
        self.logger = logger

    def analyze_timeframe(
        self,
        timeframe: str,
        candle_count: int = 100
    ) -> Optional[TimeframeAnalysis]:
        """
        Analyze a single timeframe.

        Args:
            timeframe: OANDA granularity (H1, H4, D, etc.)
            candle_count: Number of candles to fetch

        Returns:
            TimeframeAnalysis or None on error
        """
        try:
            # Get candle data
            candles = self.oanda.get_candles(
                instrument=self.instrument,
                granularity=timeframe,
                count=candle_count
            )

            if not candles or len(candles) < 50:
                self.logger.warning(f"Insufficient data for {timeframe}: {len(candles)} candles")
                return None

            # Extract close prices
            prices = [c["close"] for c in candles]

            # Calculate indicators
            ema20 = self.indicators.calculate_ema(prices, 20)
            ema50 = self.indicators.calculate_ema(prices, 50)
            rsi = self.indicators.calculate_rsi(prices, 14)

            if not ema20 or not ema50 or not rsi:
                return None

            current_price = prices[-1]
            current_ema20 = ema20[-1]
            current_ema50 = ema50[-1]
            current_rsi = rsi[-1]

            # Calculate trend strength (distance between EMAs as % of price)
            ema_distance = abs(current_ema20 - current_ema50) / current_price * 100
            trend_strength = min(ema_distance * 50, 100)  # Normalize to 0-100

            # Determine signal
            signal = TimeframeSignal.HOLD
            is_aligned = False

            # LONG conditions: EMA20 > EMA50, RSI not overbought
            if current_ema20 > current_ema50:
                if current_rsi < 70:
                    signal = TimeframeSignal.LONG
                    is_aligned = True

            # SHORT conditions: EMA20 < EMA50, RSI not oversold
            elif current_ema20 < current_ema50:
                if current_rsi > 30:
                    signal = TimeframeSignal.SHORT
                    is_aligned = True

            return TimeframeAnalysis(
                timeframe=timeframe,
                signal=signal,
                ema20=round(current_ema20, 5),
                ema50=round(current_ema50, 5),
                rsi14=round(current_rsi, 2),
                trend_strength=round(trend_strength, 2),
                is_aligned=is_aligned
            )

        except Exception as e:
            self.logger.error(f"Error analyzing {timeframe}: {e}")
            return None

    def get_confirmed_signal(self) -> Dict:
        """
        Get signal confirmed by multiple timeframes.
        H1 for entry timing, H4 for trend confirmation.

        Returns:
            Dict with confirmed signal and analysis details
        """
        try:
            # Analyze both timeframes
            h1_analysis = self.analyze_timeframe("H1", 100)
            h4_analysis = self.analyze_timeframe("H4", 100)

            result = {
                "instrument": self.instrument,
                "signal": "HOLD",
                "confidence": 0,
                "h1": None,
                "h4": None,
                "confirmation": False,
                "reason": ""
            }

            # Store individual analyses
            if h1_analysis:
                result["h1"] = {
                    "signal": h1_analysis.signal.value,
                    "ema20": h1_analysis.ema20,
                    "ema50": h1_analysis.ema50,
                    "rsi14": h1_analysis.rsi14,
                    "trend_strength": h1_analysis.trend_strength,
                    "is_aligned": h1_analysis.is_aligned
                }

            if h4_analysis:
                result["h4"] = {
                    "signal": h4_analysis.signal.value,
                    "ema20": h4_analysis.ema20,
                    "ema50": h4_analysis.ema50,
                    "rsi14": h4_analysis.rsi14,
                    "trend_strength": h4_analysis.trend_strength,
                    "is_aligned": h4_analysis.is_aligned
                }

            # Check for errors
            if not h1_analysis or not h4_analysis:
                result["reason"] = "Insufficient data for analysis"
                return result

            # Check signal alignment
            h1_signal = h1_analysis.signal
            h4_signal = h4_analysis.signal

            # Signals must match (both LONG or both SHORT)
            if h1_signal == h4_signal and h1_signal != TimeframeSignal.HOLD:
                result["signal"] = h1_signal.value
                result["confirmation"] = True

                # Calculate confidence based on alignment and trend strength
                base_confidence = 60

                # Add confidence for trend strength
                avg_strength = (h1_analysis.trend_strength + h4_analysis.trend_strength) / 2
                strength_bonus = min(avg_strength * 0.3, 20)  # Up to 20%

                # Add confidence for RSI alignment
                rsi_bonus = 0
                if h1_signal == TimeframeSignal.LONG:
                    if 45 <= h1_analysis.rsi14 <= 55 and 45 <= h4_analysis.rsi14 <= 55:
                        rsi_bonus = 15  # Ideal RSI zone
                    elif 40 <= h1_analysis.rsi14 <= 60 and 40 <= h4_analysis.rsi14 <= 60:
                        rsi_bonus = 10
                else:  # SHORT
                    if 45 <= h1_analysis.rsi14 <= 55 and 45 <= h4_analysis.rsi14 <= 55:
                        rsi_bonus = 15
                    elif 40 <= h1_analysis.rsi14 <= 60 and 40 <= h4_analysis.rsi14 <= 60:
                        rsi_bonus = 10

                result["confidence"] = min(int(base_confidence + strength_bonus + rsi_bonus), 95)
                result["reason"] = f"H1 and H4 aligned: {h1_signal.value}"

                self.logger.info(
                    f"✅ Multi-TF confirmed: {h1_signal.value} "
                    f"(H1 RSI={h1_analysis.rsi14}, H4 RSI={h4_analysis.rsi14}, "
                    f"confidence={result['confidence']}%)"
                )

            # H4 shows direction but H1 not ready
            elif h4_signal != TimeframeSignal.HOLD and h1_signal == TimeframeSignal.HOLD:
                result["signal"] = "HOLD"
                result["reason"] = f"H4 shows {h4_signal.value} but H1 not aligned - waiting"
                result["confidence"] = 30
                self.logger.info(f"⏳ H4 {h4_signal.value} but H1 not ready")

            # Conflicting signals
            elif h1_signal != h4_signal:
                result["signal"] = "HOLD"
                result["reason"] = f"Conflicting signals: H1={h1_signal.value}, H4={h4_signal.value}"
                result["confidence"] = 20
                self.logger.info(f"⚠️ Conflicting: H1={h1_signal.value}, H4={h4_signal.value}")

            else:
                result["reason"] = "No clear signal on either timeframe"

            return result

        except Exception as e:
            self.logger.error(f"Error in multi-timeframe analysis: {e}")
            return {
                "instrument": self.instrument,
                "signal": "HOLD",
                "confidence": 0,
                "error": str(e),
                "reason": "Analysis error"
            }

    def get_trend_context(self) -> Dict:
        """
        Get higher timeframe trend context (D, W).
        Used for overall market direction, not for entries.

        Returns:
            Dict with daily and weekly trend info
        """
        try:
            daily = self.analyze_timeframe("D", 50)

            context = {
                "daily_trend": "NEUTRAL",
                "weekly_bias": "NEUTRAL",
                "higher_tf_aligned": False
            }

            if daily:
                if daily.signal == TimeframeSignal.LONG:
                    context["daily_trend"] = "BULLISH"
                elif daily.signal == TimeframeSignal.SHORT:
                    context["daily_trend"] = "BEARISH"

                context["daily_rsi"] = daily.rsi14
                context["daily_ema20"] = daily.ema20
                context["daily_ema50"] = daily.ema50

            return context

        except Exception as e:
            self.logger.error(f"Error getting trend context: {e}")
            return {"error": str(e)}
