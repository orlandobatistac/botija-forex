"""
Migration script: Add trading_mode column to bot_status table
Run this on production database
"""
import sqlite3
import sys
from pathlib import Path

def migrate_database(db_path: str = "app.db"):
    """Add trading_mode column to bot_status table"""
    
    print(f"🔧 Migrando base de datos: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if column already exists
        cursor.execute("PRAGMA table_info(bot_status)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'trading_mode' in columns:
            print("✅ Columna 'trading_mode' ya existe")
            return
        
        # Add trading_mode column with default value
        print("📝 Agregando columna 'trading_mode'...")
        cursor.execute("""
            ALTER TABLE bot_status 
            ADD COLUMN trading_mode VARCHAR DEFAULT 'PAPER'
        """)
        
        # Update existing records to PAPER mode
        cursor.execute("""
            UPDATE bot_status 
            SET trading_mode = 'PAPER' 
            WHERE trading_mode IS NULL
        """)
        
        conn.commit()
        print("✅ Migración completada exitosamente")
        
        # Verify
        cursor.execute("PRAGMA table_info(bot_status)")
        columns = [row[1] for row in cursor.fetchall()]
        print(f"📊 Columnas en bot_status: {', '.join(columns)}")
        
    except Exception as e:
        print(f"❌ Error en migración: {e}")
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "app.db"
    migrate_database(db_path)
