import sqlite3
import os

db_path = 'C:/Users/kompd/.gemini/antigravity/scratch/discord_bot/users.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()

# Get SQL for creating the table
c.execute("SELECT sql FROM sqlite_master WHERE name='verification_codes'")
sql = c.fetchone()
print(f"Schema: {sql[0] if sql else 'NOT FOUND'}")

# Check for is_verified in users
c.execute("PRAGMA table_info(users)")
cols = c.fetchall()
print(f"Users columns: {cols}")

conn.close()
