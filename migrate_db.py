"""
Database Migration Script for Extended Messaging Features
Adds: reply_to_id, is_pinned, edited_at to dm_messages
Creates: message_reactions table
"""
import psycopg2
import os
from urllib.parse import urlparse

def get_db_connection():
    """Get database connection from DATABASE_URL"""
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set")
        return None
    
    # Parse the URL
    result = urlparse(database_url)
    
    # Handle postgres:// vs postgresql:// scheme
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    try:
        conn = psycopg2.connect(database_url, sslmode='require')
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

def migrate():
    """Run database migration"""
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        
        print("Starting database migration...")
        
        # 1. Add new columns to dm_messages if they don't exist
        print("1. Adding new columns to dm_messages table...")
        
        # Check if columns exist first
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='dm_messages' AND column_name IN ('reply_to_id', 'is_pinned', 'edited_at')
        """)
        existing_columns = [row[0] for row in cursor.fetchall()]
        
        if 'reply_to_id' not in existing_columns:
            cursor.execute("ALTER TABLE dm_messages ADD COLUMN reply_to_id INTEGER")
            print("  ✓ Added reply_to_id column")
        else:
            print("  - reply_to_id already exists")
        
        if 'is_pinned' not in existing_columns:
            cursor.execute("ALTER TABLE dm_messages ADD COLUMN is_pinned INTEGER DEFAULT 0")
            print("  ✓ Added is_pinned column")
        else:
            print("  - is_pinned already exists")
        
        if 'edited_at' not in existing_columns:
            cursor.execute("ALTER TABLE dm_messages ADD COLUMN edited_at REAL")
            print("  ✓ Added edited_at column")
        else:
            print("  - edited_at already exists")
        
        # 2. Create message_reactions table if it doesn't exist
        print("2. Creating message_reactions table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS message_reactions (
                id SERIAL PRIMARY KEY,
                message_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                emoji VARCHAR(50) NOT NULL,
                created_at REAL NOT NULL,
                UNIQUE(message_id, user_id, emoji)
            )
        """)
        print("  ✓ message_reactions table created (or already exists)")
        
        # Commit changes
        conn.commit()
        print("\n✅ Migration completed successfully!")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        conn.rollback()
        conn.close()
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("Database Migration for Extended Messaging")
    print("=" * 50)
    migrate()
