"""
Multi-pair trading manager
Manages trading across multiple currency pairs
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
import asyncio

from .oanda_client import OandaClient
from .multi_timeframe import MultiTimeframeAnalyzer
from ..config import Config

logger = logging.getLogger(__name__)


@dataclass
class PairAnalysis:
    """Analysis result for a single pair"""
    instrument: str
    signal: str  # LONG, SHORT, HOLD
    confidence: int
    mtf_confirmed: bool
    current_price: float
    spread_pips: float
    position_units: int
    reason: str


class MultiPairManager:
    """
    Manages trading signals across multiple currency pairs.
    Analyzes all pairs and prioritizes by signal strength.
    """

    # Pip values for different pairs (approximate)
    PIP_MULTIPLIERS = {
        "EUR_USD": 0.0001,
        "GBP_USD": 0.0001,
        "AUD_USD": 0.0001,
        "NZD_USD": 0.0001,
        "USD_JPY": 0.01,
        "EUR_JPY": 0.01,
        "GBP_JPY": 0.01,
        "USD_CHF": 0.0001,
        "USD_CAD": 0.0001,
    }

    def __init__(
        self,
        oanda_client: OandaClient,
        instruments: List[str] = None
    ):
        """
        Initialize multi-pair manager.

        Args:
            oanda_client: OANDA API client
            instruments: List of currency pairs to monitor
        """
        self.oanda = oanda_client
        self.instruments = instruments or Config.TRADING_INSTRUMENTS
        self.logger = logger

        # Create MTF analyzer for each pair
        self.analyzers: Dict[str, MultiTimeframeAnalyzer] = {}
        for instrument in self.instruments:
            self.analyzers[instrument] = MultiTimeframeAnalyzer(oanda_client, instrument)

        self.logger.info(f"📊 Multi-pair manager initialized: {', '.join(self.instruments)}")

    def analyze_pair(self, instrument: str) -> Optional[PairAnalysis]:
        """
        Analyze a single currency pair.

        Args:
            instrument: Currency pair (e.g., 'EUR_USD')

        Returns:
            PairAnalysis or None on error
        """
        try:
            analyzer = self.analyzers.get(instrument)
            if not analyzer:
                self.logger.warning(f"No analyzer for {instrument}")
                return None

            # Get multi-timeframe signal
            mtf_result = analyzer.get_confirmed_signal()

            # Get current price and spread
            spread_info = self.oanda.get_spread(instrument)
            if not spread_info:
                return None

            # Get current position
            position_units = self.oanda.get_position_units(instrument)

            return PairAnalysis(
                instrument=instrument,
                signal=mtf_result.get('signal', 'HOLD'),
                confidence=mtf_result.get('confidence', 0),
                mtf_confirmed=mtf_result.get('confirmation', False),
                current_price=spread_info['mid'],
                spread_pips=spread_info['spread_pips'],
                position_units=position_units,
                reason=mtf_result.get('reason', '')
            )

        except Exception as e:
            self.logger.error(f"Error analyzing {instrument}: {e}")
            return None

    def analyze_all_pairs(self) -> List[PairAnalysis]:
        """
        Analyze all configured pairs.

        Returns:
            List of PairAnalysis sorted by confidence (highest first)
        """
        results = []

        for instrument in self.instruments:
            analysis = self.analyze_pair(instrument)
            if analysis:
                results.append(analysis)

        # Sort by confidence (highest first)
        results.sort(key=lambda x: x.confidence, reverse=True)

        return results

    def get_best_opportunity(self) -> Optional[PairAnalysis]:
        """
        Get the best trading opportunity across all pairs.

        Returns:
            Best PairAnalysis with confirmed signal and no existing position
        """
        analyses = self.analyze_all_pairs()

        for analysis in analyses:
            # Skip if already has position
            if analysis.position_units != 0:
                self.logger.info(f"⏭️ {analysis.instrument}: Already has position ({analysis.position_units} units)")
                continue

            # Skip if not confirmed
            if not analysis.mtf_confirmed:
                continue

            # Skip HOLD signals
            if analysis.signal == 'HOLD':
                continue

            # Found a good opportunity
            self.logger.info(
                f"🎯 Best opportunity: {analysis.instrument} - {analysis.signal} "
                f"(confidence: {analysis.confidence}%)"
            )
            return analysis

        self.logger.info("⏳ No trading opportunities found")
        return None

    def get_all_positions(self) -> Dict[str, int]:
        """
        Get all open positions across monitored pairs.

        Returns:
            Dict mapping instrument to position units
        """
        positions = {}
        for instrument in self.instruments:
            units = self.oanda.get_position_units(instrument)
            if units != 0:
                positions[instrument] = units
        return positions

    def get_summary(self) -> Dict:
        """
        Get summary of all pairs analysis.

        Returns:
            Dict with analysis summary
        """
        analyses = self.analyze_all_pairs()
        positions = self.get_all_positions()

        long_signals = [a for a in analyses if a.signal == 'LONG' and a.mtf_confirmed]
        short_signals = [a for a in analyses if a.signal == 'SHORT' and a.mtf_confirmed]

        return {
            'timestamp': datetime.now().isoformat(),
            'instruments': self.instruments,
            'total_pairs': len(self.instruments),
            'active_positions': len(positions),
            'positions': positions,
            'long_signals': len(long_signals),
            'short_signals': len(short_signals),
            'analyses': [
                {
                    'instrument': a.instrument,
                    'signal': a.signal,
                    'confidence': a.confidence,
                    'confirmed': a.mtf_confirmed,
                    'has_position': a.position_units != 0,
                    'spread_pips': round(a.spread_pips, 2)
                }
                for a in analyses
            ],
            'best_opportunity': None if not analyses else {
                'instrument': analyses[0].instrument,
                'signal': analyses[0].signal,
                'confidence': analyses[0].confidence
            } if analyses[0].mtf_confirmed and analyses[0].signal != 'HOLD' else None
        }
