"""
Pydantic schemas for Kraken AI Trading Bot API
"""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class TradeBase(BaseModel):
    order_type: str
    symbol: str = "BTCUSD"
    entry_price: float
    quantity: float
    status: str
    trading_mode: str = "REAL"

class TradeCreate(TradeBase):
    pass

class Trade(TradeBase):
    id: int
    trade_id: Optional[str] = None
    exit_price: Optional[float] = None
    profit_loss: Optional[float] = None
    trailing_stop: Optional[float] = None
    created_at: datetime
    closed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.strftime('%Y-%m-%dT%H:%M:%SZ') if v else None
        }

class BotStatusBase(BaseModel):
    is_running: bool
    trading_mode: str = "PAPER"
    btc_balance: float
    usd_balance: float

class BotStatusCreate(BotStatusBase):
    pass

class BotStatus(BotStatusBase):
    id: int
    last_buy_price: Optional[float] = None
    trailing_stop_price: Optional[float] = None
    last_check: datetime
    last_trade_id: Optional[str] = None
    error_count: int
    updated_at: datetime
    
    class Config:
        from_attributes = True

class SignalBase(BaseModel):
    ema20: float
    ema50: float
    rsi14: float
    ai_signal: str
    confidence: float

class SignalCreate(SignalBase):
    pass

class Signal(SignalBase):
    id: int
    timestamp: datetime
    action_taken: Optional[str] = None
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.strftime('%Y-%m-%dT%H:%M:%SZ') if v else None
        }

class TradingCycleBase(BaseModel):
    btc_price: float
    ema20: float
    ema50: float
    rsi14: float
    btc_balance: float
    usd_balance: float
    ai_signal: str
    ai_confidence: float
    action: str
    trading_mode: str

class TradingCycleCreate(TradingCycleBase):
    ai_reason: Optional[str] = None
    trade_id: Optional[str] = None
    execution_time_ms: Optional[int] = None
    trigger: Optional[str] = None
    error_message: Optional[str] = None

class TradingCycle(TradingCycleBase):
    id: int
    timestamp: datetime
    ai_reason: Optional[str] = None
    trade_id: Optional[str] = None
    execution_time_ms: Optional[int] = None
    trigger: Optional[str] = None
    error_message: Optional[str] = None
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.strftime('%Y-%m-%dT%H:%M:%SZ') if v else None
        }
