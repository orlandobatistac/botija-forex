"""
Technical indicators for trading signals
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Tuple
import logging

logger = logging.getLogger(__name__)

class TechnicalIndicators:
    """Technical analysis indicators"""
    
    @staticmethod
    def calculate_ema(data: List[float], period: int) -> List[float]:
        """Calculate Exponential Moving Average"""
        if len(data) < period:
            return []
        
        series = pd.Series(data)
        ema = series.ewm(span=period, adjust=False).mean()
        return ema.tolist()
    
    @staticmethod
    def calculate_rsi(data: List[float], period: int = 14) -> List[float]:
        """Calculate Relative Strength Index"""
        if len(data) < period + 1:
            return []
        
        series = pd.Series(data)
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.tolist()
    
    @staticmethod
    def calculate_macd(
        data: List[float], 
        fast: int = 12, 
        slow: int = 26, 
        signal: int = 9
    ) -> Tuple[List[float], List[float], List[float]]:
        """Calculate MACD indicator"""
        series = pd.Series(data)
        ema_fast = series.ewm(span=fast, adjust=False).mean()
        ema_slow = series.ewm(span=slow, adjust=False).mean()
        
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        
        return (
            macd_line.tolist(),
            signal_line.tolist(),
            histogram.tolist()
        )
    
    @staticmethod
    def calculate_bollinger_bands(
        data: List[float], 
        period: int = 20, 
        std_dev: float = 2.0
    ) -> Tuple[List[float], List[float], List[float]]:
        """Calculate Bollinger Bands"""
        series = pd.Series(data)
        middle = series.rolling(window=period).mean()
        std = series.rolling(window=period).std()
        
        upper = middle + (std_dev * std)
        lower = middle - (std_dev * std)
        
        return (upper.tolist(), middle.tolist(), lower.tolist())
    
    @staticmethod
    def analyze_signals(
        prices: List[float],
        ema20_period: int = 20,
        ema50_period: int = 50,
        rsi_period: int = 14
    ) -> Dict:
        """Analyze current signals from price data"""
        if len(prices) < max(ema50_period, rsi_period) + 1:
            return {}
        
        try:
            # Calculate indicators
            ema20 = TechnicalIndicators.calculate_ema(prices, ema20_period)
            ema50 = TechnicalIndicators.calculate_ema(prices, ema50_period)
            rsi = TechnicalIndicators.calculate_rsi(prices, rsi_period)
            
            current_price = prices[-1]
            current_ema20 = ema20[-1] if ema20 else 0
            current_ema50 = ema50[-1] if ema50 else 0
            current_rsi = rsi[-1] if rsi else 0
            
            # Determine signal
            signal = 'HOLD'
            if current_ema20 > current_ema50 and 45 <= current_rsi <= 60:
                signal = 'BUY'
            elif current_ema20 < current_ema50 or current_rsi < 40:
                signal = 'SELL'
            
            return {
                'current_price': current_price,
                'ema20': round(current_ema20, 2),
                'ema50': round(current_ema50, 2),
                'rsi14': round(current_rsi, 2),
                'signal': signal,
                'ema20_gt_ema50': current_ema20 > current_ema50,
                'rsi_in_buy_zone': 45 <= current_rsi <= 60
            }
        except Exception as e:
            logger.error(f"Error analyzing signals: {e}")
            return {}
