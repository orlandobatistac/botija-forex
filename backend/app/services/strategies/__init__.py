"""
Strategies Package
==================
Estrategias de trading modulares para botija-forex.

Fase 0: Estrategias simples
- TripleEMAStrategy: Trend following con EMA 20/50/200
"""

from .triple_ema import TripleEMAStrategy, TripleEMASignal

__all__ = ["TripleEMAStrategy", "TripleEMASignal"]
