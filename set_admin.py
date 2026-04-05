import sqlite3
import os

db_path = 'C:/Users/kompd/.gemini/antigravity/scratch/discord_bot/users.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("UPDATE users SET role='admin'")
    conn.commit()
    print("DONE: All users are now admins.")
    conn.close()
else:
    print(f"Error: {db_path} not found")
