"""
Trades router - Trade management endpoints
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from ..database import get_db
from .. import models, schemas

router = APIRouter(
    prefix="/api/v1/trades",
    tags=["trades"]
)


@router.get("/", response_model=List[schemas.TradeResponse])
async def get_trades(
    skip: int = 0,
    limit: int = 100,
    mode: str = None,
    instrument: str = None,
    db: Session = Depends(get_db)
):
    """Get all trades with optional filters"""
    query = db.query(models.Trade).order_by(models.Trade.created_at.desc())

    if mode:
        query = query.filter(models.Trade.trading_mode == mode.upper())
    if instrument:
        query = query.filter(models.Trade.instrument == instrument)

    trades = query.offset(skip).limit(limit).all()
    return trades


@router.get("/{trade_id}", response_model=schemas.TradeResponse)
async def get_trade(trade_id: int, db: Session = Depends(get_db)):
    """Get a specific trade by ID"""
    trade = db.query(models.Trade).filter(models.Trade.id == trade_id).first()
    if not trade:
        return {"error": "Trade not found"}
    return trade


@router.get("/stats/summary")
async def get_trade_stats(
    mode: str = None,
    instrument: str = None,
    db: Session = Depends(get_db)
):
    """Get trading statistics summary"""
    query = db.query(models.Trade).filter(models.Trade.status == "CLOSED")

    if mode:
        query = query.filter(models.Trade.trading_mode == mode.upper())
    if instrument:
        query = query.filter(models.Trade.instrument == instrument)

    trades = query.all()

    if not trades:
        return {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate": 0.0,
            "total_profit_loss": 0.0,
            "average_profit": 0.0,
            "average_loss": 0.0
        }

    winning = [t for t in trades if t.profit_loss and t.profit_loss > 0]
    losing = [t for t in trades if t.profit_loss and t.profit_loss < 0]

    total_pl = sum(t.profit_loss or 0 for t in trades)
    avg_profit = sum(t.profit_loss for t in winning) / len(winning) if winning else 0
    avg_loss = sum(t.profit_loss for t in losing) / len(losing) if losing else 0

    return {
        "total_trades": len(trades),
        "winning_trades": len(winning),
        "losing_trades": len(losing),
        "win_rate": len(winning) / len(trades) * 100 if trades else 0,
        "total_profit_loss": total_pl,
        "average_profit": avg_profit,
        "average_loss": avg_loss
    }
