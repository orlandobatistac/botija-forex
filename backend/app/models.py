"""
SQLAlchemy models for Botija Forex
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text
from sqlalchemy.sql import func

from .database import Base


class Trade(Base):
    """Trade record model"""
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    trade_id = Column(String, unique=True, index=True)
    order_type = Column(String)  # BUY, SELL
    instrument = Column(String)  # EUR_USD, GBP_USD, etc.
    entry_price = Column(Float)
    exit_price = Column(Float, nullable=True)
    units = Column(Integer)  # Position size in units
    profit_loss = Column(Float, nullable=True)
    profit_loss_pips = Column(Float, nullable=True)
    status = Column(String)  # OPEN, CLOSED, CANCELLED
    trading_mode = Column(String, default="PAPER")  # PAPER, REAL
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    closed_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)


class BotStatus(Base):
    """Bot status model"""
    __tablename__ = "bot_status"

    id = Column(Integer, primary_key=True, index=True)
    is_running = Column(Boolean, default=False)
    trading_mode = Column(String, default="DEMO")  # DEMO, LIVE
    instrument = Column(String, default="EUR_USD")
    balance = Column(Float, default=0.0)
    nav = Column(Float, default=0.0)  # Net Asset Value
    position_units = Column(Integer, default=0)  # Current position (+ long, - short, 0 flat)
    unrealized_pl = Column(Float, default=0.0)
    last_check = Column(DateTime(timezone=True), server_default=func.now())
    last_trade_id = Column(String, nullable=True)
    error_count = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class TradingCycle(Base):
    """Trading cycle record"""
    __tablename__ = "trading_cycles"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    # Market data
    instrument = Column(String)
    price = Column(Float)
    spread_pips = Column(Float, nullable=True)

    # Technical indicators
    ema_fast = Column(Float)   # EMA 20
    ema_slow = Column(Float)   # EMA 50
    ema_trend = Column(Float)  # EMA 200

    # Hybrid strategy indicators
    adx = Column(Float, nullable=True)
    macd = Column(Float, nullable=True)
    macd_signal = Column(Float, nullable=True)
    ema200 = Column(Float, nullable=True)
    donchian_high = Column(Float, nullable=True)
    donchian_low = Column(Float, nullable=True)

    # Account state
    balance = Column(Float)
    position_units = Column(Integer)

    # AI Signal
    ai_signal = Column(String)  # BUY, SELL, HOLD
    ai_confidence = Column(Float)
    ai_reason = Column(Text, nullable=True)

    # Action taken
    action = Column(String)  # BOUGHT, SOLD, HOLD, ERROR
    trade_id = Column(String, nullable=True)
    profit_loss = Column(Float, nullable=True)

    # Execution details
    execution_time_ms = Column(Integer, nullable=True)
    trading_mode = Column(String)  # DEMO, LIVE
    trigger = Column(String, nullable=True)  # manual, scheduled
    strategy = Column(String, nullable=True)  # Triple EMA, etc.
    error_message = Column(Text, nullable=True)


class Signal(Base):
    """Trading signal record"""
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    instrument = Column(String)
    ema_fast = Column(Float)
    ema_slow = Column(Float)
    rsi = Column(Float)
    ai_signal = Column(String)  # BUY, SELL, HOLD
    confidence = Column(Float)
    action_taken = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
