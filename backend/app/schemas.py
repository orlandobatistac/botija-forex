"""
Pydantic schemas for Botija Forex API
"""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional


# ═══════════════════════════════════════════════════════════════
# TRADE SCHEMAS
# ═══════════════════════════════════════════════════════════════

class TradeBase(BaseModel):
    order_type: str
    instrument: str = "EUR_USD"
    entry_price: float
    units: int
    status: str
    trading_mode: str = "DEMO"


class TradeCreate(TradeBase):
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


class TradeResponse(TradeBase):
    id: int
    trade_id: Optional[str] = None
    exit_price: Optional[float] = None
    profit_loss: Optional[float] = None
    profit_loss_pips: Optional[float] = None
    created_at: datetime
    closed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════
# BOT STATUS SCHEMAS
# ═══════════════════════════════════════════════════════════════

class BotStatusBase(BaseModel):
    is_running: bool
    trading_mode: str = "DEMO"
    instrument: str = "EUR_USD"
    balance: float
    position_units: int = 0


class BotStatusCreate(BotStatusBase):
    pass


class BotStatusResponse(BotStatusBase):
    id: int
    nav: float = 0.0
    unrealized_pl: float = 0.0
    last_check: datetime
    last_trade_id: Optional[str] = None
    error_count: int = 0
    updated_at: datetime

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════
# TRADING CYCLE SCHEMAS
# ═══════════════════════════════════════════════════════════════

class TradingCycleBase(BaseModel):
    instrument: str
    price: float
    ema_fast: float
    ema_slow: float
    ema_trend: Optional[float] = None
    balance: float
    position_units: int
    ai_signal: str
    ai_confidence: float
    action: str
    trading_mode: str


class TradingCycleCreate(TradingCycleBase):
    spread_pips: Optional[float] = None
    ai_reason: Optional[str] = None
    trade_id: Optional[str] = None
    profit_loss: Optional[float] = None
    execution_time_ms: Optional[int] = None
    trigger: Optional[str] = None
    strategy: Optional[str] = None
    error_message: Optional[str] = None


class TradingCycleResponse(TradingCycleBase):
    id: int
    timestamp: datetime
    spread_pips: Optional[float] = None
    ai_reason: Optional[str] = None
    trade_id: Optional[str] = None
    profit_loss: Optional[float] = None
    execution_time_ms: Optional[int] = None
    trigger: Optional[str] = None
    strategy: Optional[str] = None

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════
# SIGNAL SCHEMAS
# ═══════════════════════════════════════════════════════════════

class SignalBase(BaseModel):
    instrument: str
    ema_fast: float
    ema_slow: float
    rsi: float
    ai_signal: str
    confidence: float


class SignalCreate(SignalBase):
    pass


class SignalResponse(SignalBase):
    id: int
    timestamp: datetime
    action_taken: Optional[str] = None

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════
# DASHBOARD SCHEMAS
# ═══════════════════════════════════════════════════════════════

class DashboardResponse(BaseModel):
    mode: str
    instrument: str
    balance: float
    nav: float
    position_units: int
    unrealized_pl: float
    is_running: bool
    last_price: Optional[float] = None
    spread_pips: Optional[float] = None
    status: str = "ready"
    active_strategy: str = "hybrid"
    timeframe: str = "H4"


class MarketAnalysis(BaseModel):
    instrument: str
    current_price: float
    bid: float
    ask: float
    spread_pips: float
    ema_fast: float
    ema_slow: float
    rsi: float
    ai_signal: str
    ai_confidence: float
    ai_reason: Optional[str] = None
    should_buy: bool
    should_sell: bool
    balance: float
    position_units: int
