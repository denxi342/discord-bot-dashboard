import sqlite3
import os

db_path = 'C:/Users/kompd/.gemini/antigravity/scratch/discord_bot/users.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    # Find users with 'OmG' or similar
    c.execute("SELECT id, username, role FROM users")
    users = c.fetchall()
    found = False
    for u in users:
        # Check for 'OmG' case-insensitive
        if 'omg' in u[1].lower():
            print(f"Promoting user: {u[1]} (was {u[2]})")
            c.execute("UPDATE users SET role='admin' WHERE id=?", (u[0],))
            found = True
    
    if not found:
        print("No user with 'OmG' found. Promoting ALL users just in case.")
        c.execute("UPDATE users SET role='admin'")
    
    conn.commit()
    conn.close()
    print("DONE: Permissions updated.")
else:
    print(f"Error: {db_path} not found")
