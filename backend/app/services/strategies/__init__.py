"""
Strategies Package
==================
Estrategias de trading modulares para botija-forex.

- HybridStrategy: Breakout + MACD con ADX Switch (71% consistencia)
- AdaptiveStrategy: Detección de régimen de mercado
- TripleEMAStrategy: Trend following con EMA 20/50/200
"""

from .triple_ema import TripleEMAStrategy, TripleEMASignal
from .adaptive import AdaptiveStrategy
from .hybrid import HybridStrategy

__all__ = ["TripleEMAStrategy", "TripleEMASignal", "AdaptiveStrategy", "HybridStrategy"]
