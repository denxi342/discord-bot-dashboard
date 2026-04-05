import sqlite3
import os

db_path = 'C:/Users/kompd/.gemini/antigravity/scratch/discord_bot/users.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT id, username FROM users")
    users = c.fetchall()
    
    found = False
    for u_id, u_name in users:
        # Check for 'OmG' or characters from the image
        if 'omg' in u_name.lower():
            print(f"Found match: ID={u_id}, Name={u_name!r}")
            c.execute("UPDATE users SET role='admin' WHERE id=?", (u_id,))
            found = True
            
    if found:
        conn.commit()
        print("SUCCESS: Admin role granted to matches.")
    else:
        # If no OmG found, maybe it's the very last registered user?
        c.execute("SELECT id, username FROM users ORDER BY id DESC LIMIT 1")
        last = c.fetchone()
        if last:
            print(f"Last user found: ID={last[0]}, Name={last[1]!r}. Promoting to admin.")
            c.execute("UPDATE users SET role='admin' WHERE id=?", (last[0],))
            conn.commit()
            
    conn.close()
else:
    print("Error: DB not found.")
