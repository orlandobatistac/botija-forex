"""
Paper trading routes
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from .. import schemas, models
from ..database import get_db
from ..services.modes.paper import PaperTradingEngine

router = APIRouter(
    prefix="/api/v1/paper",
    tags=["paper trading"]
)

# Initialize paper engine
paper_engine = PaperTradingEngine()

@router.get("/wallet")
async def get_wallet():
    """Get current paper wallet status"""
    return paper_engine.get_wallet_summary()

@router.get("/trades")
async def get_paper_trades(limit: int = 20, db: Session = Depends(get_db)):
    """Get recent simulated trades from database"""
    try:
        trades = db.query(models.Trade)\
            .filter(models.Trade.trading_mode == "PAPER")\
            .order_by(models.Trade.created_at.desc())\
            .limit(limit)\
            .all()
        
        return {
            "trades": [schemas.TradeResponse.from_orm(t).dict() for t in trades],
            "total": len(trades)
        }
    except Exception as e:
        return {"error": str(e)}

@router.post("/reset")
async def reset_wallet(initial_usd: float = 1000.0):
    """Reset paper wallet to initial state"""
    try:
        paper_engine.reset_wallet(initial_usd)
        return {
            "message": f"Paper wallet reset to ${initial_usd:.2f}",
            "wallet": paper_engine.get_wallet_summary()
        }
    except Exception as e:
        return {"error": str(e)}

@router.post("/simulate-buy")
async def simulate_buy(price: float, usd_amount: float):
    """Manually simulate a buy order"""
    try:
        success, message = paper_engine.buy(price, usd_amount)
        return {
            "success": success,
            "message": message,
            "wallet": paper_engine.get_wallet_summary() if success else None
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.post("/simulate-sell")
async def simulate_sell(price: float, btc_amount: float):
    """Manually simulate a sell order"""
    try:
        success, message = paper_engine.sell(price, btc_amount)
        return {
            "success": success,
            "message": message,
            "wallet": paper_engine.get_wallet_summary() if success else None
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.get("/stats")
async def get_paper_stats(db: Session = Depends(get_db)):
    """Get paper trading statistics"""
    try:
        wallet = paper_engine.get_wallet_summary()
        
        # Calculate stats from database
        buy_trades = db.query(models.Trade)\
            .filter(models.Trade.trading_mode == "PAPER", models.Trade.order_type == "BUY")\
            .count()
        
        sell_trades = db.query(models.Trade)\
            .filter(models.Trade.trading_mode == "PAPER", models.Trade.order_type == "SELL")\
            .count()
        
        total_trades = buy_trades + sell_trades
        
        return {
            "wallet": wallet,
            "stats": {
                "total_trades": total_trades,
                "buy_trades": buy_trades,
                "sell_trades": sell_trades,
                "position_open": wallet['btc_balance'] > 0
            }
        }
    except Exception as e:
        return {"error": str(e)}

