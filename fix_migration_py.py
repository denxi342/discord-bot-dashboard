
import os

file_path = r'C:\Users\kompd\.gemini\antigravity\scratch\discord_bot\web.py'

with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

start_idx = -1
end_idx = -1

for i, line in enumerate(lines):
    if 'def run_db_migration():' in line:
        start_idx = i
    if 'print("[OK] Database migration completed successfully!")' in line:
        end_idx = i + 1 # Include the print
        break

if start_idx != -1 and end_idx != -1:
    # Look for the try/except block end
    # Actually, I'll just replace from def until the end of the try block.
    # Let's find the closing except for the main try block.
    for j in range(end_idx, len(lines)):
        if 'except Exception as e:' in lines[j] and 'Global migration failed' not in lines[j]:
            # This is the inner except
            pass
        if 'print(f"[!] Migration error' in lines[j]:
            end_idx = j + 2
            break

    new_func = """def run_db_migration():
    \"\"\"
    Run database migration to add extended messaging fields to existing databases.
    This is safe to run multiple times - it checks if columns exist before adding.
    \"\"\"
    try:
        conn = get_db_connection()
        is_sqlite = isinstance(conn, sqlite3.Connection)
        cursor = conn.cursor()
        
        pk_type = "INTEGER PRIMARY KEY AUTOINCREMENT" if is_sqlite else "SERIAL PRIMARY KEY"
        
        print("[*] Running database migration...")
        
        # Helper for adding columns safely
        def add_col(table, column, col_type):
            try:
                if is_sqlite:
                    cursor.execute(f"PRAGMA table_info({table})")
                    cols = {row[1] for row in cursor.fetchall()}
                    if column not in cols:
                        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
                        print(f"  [+] Added {column} to {table}")
                else:
                    cursor.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name='{table}' AND column_name='{column}'")
                    if not cursor.fetchone():
                        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
                        print(f"  [+] Added {column} to {table}")
                conn.commit()
            except Exception as e:
                print(f"  [!] Skip {column} on {table}: {e}")
                conn.rollback()

        # Users updates
        add_col("users", "last_seen", "DOUBLE PRECISION" if not is_sqlite else "REAL")
        add_col("users", "admin_pin", "TEXT")
        add_col("users", "custom_status", "TEXT")
        add_col("users", "status_emoji", "TEXT")
        add_col("users", "public_key", "TEXT")
        add_col("users", "private_key_enc", "TEXT")

        # DM messages updates
        add_col("dm_messages", "reply_to_id", "INTEGER")
        add_col("dm_messages", "is_pinned", "INTEGER DEFAULT 0")
        add_col("dm_messages", "edited_at", "REAL")
        add_col("dm_messages", "attachments", "TEXT")
        add_col("dm_messages", "expires_at", "REAL")
        add_col("dm_messages", "voice_duration", "INTEGER")

        # Tables
        cursor.execute(f"CREATE TABLE IF NOT EXISTS admin_logs (id {pk_type}, admin_id INTEGER, ip_address TEXT, action TEXT, timestamp REAL)")
        cursor.execute(f"CREATE TABLE IF NOT EXISTS message_reactions (id {pk_type}, message_id INTEGER, user_id INTEGER, emoji TEXT, created_at REAL, UNIQUE(message_id, user_id, emoji))")
        cursor.execute(f"CREATE TABLE IF NOT EXISTS read_receipts (id {pk_type}, dm_id INTEGER, user_id INTEGER, last_read_message_id INTEGER, updated_at REAL, UNIQUE(dm_id, user_id))")

        conn.commit()
        cursor.close()
        conn.close()
        print("[OK] Database migration completed successfully!")
    except Exception as e:
        print(f"[!] Migration error: {e}")
"""
    
    final_lines = lines[:start_idx] + [new_func + '\n'] + lines[end_idx:]
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(final_lines)
    print(f"Successfully patched run_db_migration in web.py at lines {start_idx}-{end_idx}")
else:
    print(f"Markers not found: start={start_idx}, end={end_idx}")
