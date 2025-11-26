"""
Migration script to add trigger column to trading_cycles table
"""

import sqlite3
import sys
import os

def migrate_add_trigger():
    """Add trigger column to trading_cycles table"""
    
    # Database path
    db_path = os.path.join(os.path.dirname(__file__), '..', 'backend', 'kraken-ai-trading-bot.db')
    
    if not os.path.exists(db_path):
        print(f"❌ Database not found at {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if column already exists
        cursor.execute("PRAGMA table_info(trading_cycles)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'trigger' in columns:
            print("✅ Column 'trigger' already exists in trading_cycles table")
            conn.close()
            return True
        
        # Add trigger column
        print("📝 Adding 'trigger' column to trading_cycles table...")
        cursor.execute("""
            ALTER TABLE trading_cycles 
            ADD COLUMN trigger VARCHAR
        """)
        
        conn.commit()
        print("✅ Migration completed successfully")
        
        # Verify
        cursor.execute("PRAGMA table_info(trading_cycles)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'trigger' in columns:
            print("✅ Verification passed - trigger column added")
        else:
            print("❌ Verification failed - trigger column not found")
            return False
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False

if __name__ == "__main__":
    print("🔄 Starting migration: Add trigger column")
    success = migrate_add_trigger()
    sys.exit(0 if success else 1)
