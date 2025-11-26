"""
Initialize database with all tables
Run this to create fresh database schema
"""
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.database import engine, Base
from app.models import Trade, BotStatus, Signal, TradingCycle

def init_database():
    """Create all tables in the database"""
    
    print("🔧 Inicializando base de datos...")
    
    try:
        # Create all tables
        Base.metadata.create_all(bind=engine)
        
        print("✅ Tablas creadas exitosamente:")
        print("   - trades")
        print("   - bot_status")
        print("   - signals")
        print("   - trading_cycles")
        
        # Verify tables were created
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        print(f"\n📊 Tablas en base de datos: {', '.join(tables)}")
        
        # Create initial bot_status record for PAPER mode
        from app.database import SessionLocal
        db = SessionLocal()
        
        # Check if any record exists
        existing_count = db.query(BotStatus).count()
        if existing_count == 0:
            print("\n📝 Creando registro inicial de bot_status...")
            initial_status = BotStatus(
                is_running=False,
                trading_mode="PAPER",
                btc_balance=0.0,
                usd_balance=1000.0,
                error_count=0
            )
            db.add(initial_status)
            db.commit()
            print("✅ Bot status inicial creado")
        else:
            print(f"\n✅ Bot status ya existe ({existing_count} registro(s))")
        
        db.close()
        
    except Exception as e:
        print(f"❌ Error inicializando base de datos: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    init_database()
