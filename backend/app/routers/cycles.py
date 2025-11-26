"""
Trading Cycles router - track execution cycles
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from .. import models, schemas
from ..database import get_db

router = APIRouter(
    prefix="/api/v1/cycles",
    tags=["cycles"]
)

@router.get("/", response_model=List[schemas.TradingCycle])
async def get_trading_cycles(
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """Get recent trading cycles"""
    try:
        cycles = db.query(models.TradingCycle)\
            .order_by(models.TradingCycle.executed_at.desc())\
            .limit(limit)\
            .all()
        return cycles
    except Exception as e:
        # Return empty list if table doesn't exist or error
        return []

@router.post("/", response_model=schemas.TradingCycle)
async def create_trading_cycle(
    cycle: schemas.TradingCycleCreate,
    db: Session = Depends(get_db)
):
    """Create a new trading cycle record"""
    db_cycle = models.TradingCycle(**cycle.dict())
    db.add(db_cycle)
    db.commit()
    db.refresh(db_cycle)
    return db_cycle
