"""
Indicators router for technical analysis endpoints
"""

from fastapi import APIRouter, Query
from typing import List
from ..services import TechnicalIndicators

router = APIRouter(
    prefix="/api/v1/indicators",
    tags=["indicators"]
)

@router.post("/ema")
async def calculate_ema(data: List[float], period: int = 20):
    """Calculate Exponential Moving Average"""
    try:
        ema = TechnicalIndicators.calculate_ema(data, period)
        return {
            "indicator": "EMA",
            "period": period,
            "values": ema,
            "current": ema[-1] if ema else None
        }
    except Exception as e:
        return {"error": str(e)}

@router.post("/rsi")
async def calculate_rsi(data: List[float], period: int = 14):
    """Calculate Relative Strength Index"""
    try:
        rsi = TechnicalIndicators.calculate_rsi(data, period)
        return {
            "indicator": "RSI",
            "period": period,
            "values": rsi,
            "current": rsi[-1] if rsi else None,
            "oversold": rsi[-1] < 30 if rsi else None,
            "overbought": rsi[-1] > 70 if rsi else None
        }
    except Exception as e:
        return {"error": str(e)}

@router.post("/macd")
async def calculate_macd(
    data: List[float], 
    fast: int = 12, 
    slow: int = 26, 
    signal: int = 9
):
    """Calculate MACD indicator"""
    try:
        macd_line, signal_line, histogram = TechnicalIndicators.calculate_macd(
            data, fast, slow, signal
        )
        return {
            "indicator": "MACD",
            "fast_ema": fast,
            "slow_ema": slow,
            "signal_period": signal,
            "macd_line": macd_line,
            "signal_line": signal_line,
            "histogram": histogram,
            "current_macd": macd_line[-1] if macd_line else None,
            "current_signal": signal_line[-1] if signal_line else None,
            "current_histogram": histogram[-1] if histogram else None
        }
    except Exception as e:
        return {"error": str(e)}

@router.post("/bollinger")
async def calculate_bollinger(
    data: List[float], 
    period: int = 20, 
    std_dev: float = 2.0
):
    """Calculate Bollinger Bands"""
    try:
        upper, middle, lower = TechnicalIndicators.calculate_bollinger_bands(
            data, period, std_dev
        )
        return {
            "indicator": "Bollinger Bands",
            "period": period,
            "std_dev": std_dev,
            "upper_band": upper,
            "middle_band": middle,
            "lower_band": lower,
            "current_upper": upper[-1] if upper else None,
            "current_middle": middle[-1] if middle else None,
            "current_lower": lower[-1] if lower else None
        }
    except Exception as e:
        return {"error": str(e)}

@router.post("/analyze")
async def analyze_signals(data: List[float]):
    """Comprehensive signal analysis"""
    try:
        analysis = TechnicalIndicators.analyze_signals(data)
        return analysis
    except Exception as e:
        return {"error": str(e)}

@router.get("/current")
async def get_current_indicators():
    """Get current market indicators for BTC/USD"""
    try:
        from ..services import KrakenClient
        import os
        
        # Initialize Kraken client
        kraken = KrakenClient(
            api_key=os.getenv('KRAKEN_API_KEY', ''),
            secret_key=os.getenv('KRAKEN_SECRET_KEY', '')
        )
        
        # Get current price
        price = kraken.get_current_price('XBTUSDT')
        
        # Get historical data for indicators
        ohlc_data = kraken.get_ohlc('XBTUSDT', interval=240, count=100)
        
        if ohlc_data and len(ohlc_data) > 0:
            close_prices = [float(candle[4]) for candle in ohlc_data]
            
            # Calculate indicators
            ema_20 = TechnicalIndicators.calculate_ema(close_prices, 20)
            ema_50 = TechnicalIndicators.calculate_ema(close_prices, 50)
            rsi_14 = TechnicalIndicators.calculate_rsi(close_prices, 14)
            
            return {
                "price": price,
                "ema_20": ema_20[-1] if ema_20 and len(ema_20) > 0 else None,
                "ema_50": ema_50[-1] if ema_50 and len(ema_50) > 0 else None,
                "rsi_14": rsi_14[-1] if rsi_14 and len(rsi_14) > 0 else None,
                "timestamp": ohlc_data[-1][0] if ohlc_data else None
            }
        else:
            return {
                "price": price,
                "ema_20": None,
                "ema_50": None,
                "rsi_14": None,
                "error": "No historical data available"
            }
    except Exception as e:
        return {
            "price": 0.0,
            "ema_20": None,
            "ema_50": None,
            "rsi_14": None,
            "error": str(e)
        }
