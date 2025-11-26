"""
Trading Cycles router - Cycle history and analysis
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from ..database import get_db
from .. import models, schemas

router = APIRouter(
    prefix="/api/v1/cycles",
    tags=["cycles"]
)


@router.get("/", response_model=List[schemas.TradingCycleResponse])
async def get_trading_cycles(
    limit: int = 20,
    instrument: str = None,
    db: Session = Depends(get_db)
):
    """Get recent trading cycles"""
    try:
        query = db.query(models.TradingCycle).order_by(models.TradingCycle.timestamp.desc())

        if instrument:
            query = query.filter(models.TradingCycle.instrument == instrument)

        cycles = query.limit(limit).all()
        return cycles
    except Exception:
        return []


@router.get("/last")
async def get_last_cycle(db: Session = Depends(get_db)):
    """Get the most recent trading cycle"""
    try:
        cycle = db.query(models.TradingCycle).order_by(
            models.TradingCycle.timestamp.desc()
        ).first()

        if not cycle:
            return {"message": "No cycles recorded yet"}

        return cycle
    except Exception as e:
        return {"error": str(e)}


@router.get("/stats")
async def get_cycle_stats(
    instrument: str = None,
    db: Session = Depends(get_db)
):
    """Get cycle statistics"""
    try:
        query = db.query(models.TradingCycle)

        if instrument:
            query = query.filter(models.TradingCycle.instrument == instrument)

        cycles = query.all()

        if not cycles:
            return {
                "total_cycles": 0,
                "buy_signals": 0,
                "sell_signals": 0,
                "hold_signals": 0,
                "actions_taken": 0,
                "errors": 0
            }

        return {
            "total_cycles": len(cycles),
            "buy_signals": len([c for c in cycles if c.ai_signal == "BUY"]),
            "sell_signals": len([c for c in cycles if c.ai_signal == "SELL"]),
            "hold_signals": len([c for c in cycles if c.ai_signal == "HOLD"]),
            "actions_taken": len([c for c in cycles if c.action in ["BOUGHT", "SOLD"]]),
            "errors": len([c for c in cycles if c.action == "ERROR"])
        }
    except Exception as e:
        return {"error": str(e)}
