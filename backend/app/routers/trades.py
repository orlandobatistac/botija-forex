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


@router.post("/sync")
async def sync_trades_from_oanda(db: Session = Depends(get_db)):
    """
    Sync closed trades from OANDA to local database.
    This captures trades closed manually on OANDA platform.
    """
    from ..services.oanda_client import OandaClient
    from ..config import settings
    from datetime import datetime

    try:
        oanda = OandaClient(
            api_key=settings.OANDA_API_KEY,
            account_id=settings.OANDA_ACCOUNT_ID,
            environment=settings.OANDA_ENVIRONMENT
        )

        closed_trades = oanda.get_closed_trades(count=50)
        synced = 0

        for trade in closed_trades:
            trade_id = trade.get("id")

            # Check if trade already exists
            existing = db.query(models.Trade).filter(
                models.Trade.trade_id == trade_id
            ).first()

            if existing:
                # Update if closed but not recorded
                if existing.status != "CLOSED":
                    existing.status = "CLOSED"
                    existing.exit_price = float(trade.get("averageClosePrice", 0))
                    existing.profit_loss = float(trade.get("realizedPL", 0))
                    existing.closed_at = datetime.fromisoformat(
                        trade.get("closeTime", "").replace("Z", "+00:00")
                    ) if trade.get("closeTime") else datetime.utcnow()
                    synced += 1
            else:
                # Create new trade record
                units = int(trade.get("initialUnits", 0))
                env = settings.OANDA_ENVIRONMENT.lower()
                trade_mode = "DEMO" if env in ("demo", "practice") else "LIVE"
                new_trade = models.Trade(
                    trade_id=trade_id,
                    order_type="BUY" if units > 0 else "SELL",
                    instrument=trade.get("instrument", "EUR_USD"),
                    entry_price=float(trade.get("price", 0)),
                    exit_price=float(trade.get("averageClosePrice", 0)),
                    units=abs(units),
                    profit_loss=float(trade.get("realizedPL", 0)),
                    status="CLOSED",
                    trading_mode=trade_mode,
                    created_at=datetime.fromisoformat(
                        trade.get("openTime", "").replace("Z", "+00:00")
                    ) if trade.get("openTime") else datetime.utcnow(),
                    closed_at=datetime.fromisoformat(
                        trade.get("closeTime", "").replace("Z", "+00:00")
                    ) if trade.get("closeTime") else datetime.utcnow(),
                    notes="Synced from OANDA"
                )
                db.add(new_trade)
                synced += 1

        db.commit()

        return {
            "success": True,
            "synced": synced,
            "total_checked": len(closed_trades)
        }

    except Exception as e:
        import traceback
        return {"success": False, "error": str(e), "traceback": traceback.format_exc()}
