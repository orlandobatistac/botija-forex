"""
Trading engine factory
"""

import logging
from typing import Union
from .base import TradingEngine
from .real import RealTradingEngine
from .paper import PaperTradingEngine
from ..kraken_client import KrakenClient
from ..trading_mode import MODE

logger = logging.getLogger(__name__)

def get_trading_engine(kraken_client: KrakenClient = None) -> TradingEngine:
    """Get appropriate trading engine based on MODE
    
    Args:
        kraken_client: KrakenClient instance for real mode
        
    Returns:
        TradingEngine: Real or Paper engine based on configuration
    """
    if MODE == "REAL":
        if not kraken_client:
            raise ValueError("KrakenClient required for REAL mode")
        logger.info("Using REAL trading engine")
        return RealTradingEngine(kraken_client)
    elif MODE == "PAPER":
        logger.info("Using PAPER trading engine")
        return PaperTradingEngine()
    else:
        raise ValueError(f"Unknown trading mode: {MODE}")
