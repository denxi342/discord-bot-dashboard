import sqlite3
import os

db_path = 'C:/Users/kompd/.gemini/antigravity/scratch/discord_bot/users.db'
if not os.path.exists(db_path):
    print(f"Error: {db_path} not found")
    exit(1)

conn = sqlite3.connect(db_path)
c = conn.cursor()

# Check tables
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in c.fetchall()]
print(f"Tables: {tables}")

# Check users columns
c.execute("PRAGMA table_info(users)")
cols = [row[1] for row in c.fetchall()]
print(f"Users columns: {cols}")

# Check verification_codes
if 'verification_codes' in tables:
    c.execute("PRAGMA table_info(verification_codes)")
    v_cols = [row[1] for row in c.fetchall()]
    print(f"Verification_codes columns: {v_cols}")
else:
    print("Verification_codes table MISSING")

conn.close()
