import sqlite3

db_path = 'C:/Users/kompd/.gemini/antigravity/scratch/discord_bot/users.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()

email = 'dedmaged@gmail.com'
c.execute("UPDATE users SET is_verified = 1 WHERE email = ?", (email,))
conn.commit()

if c.rowcount > 0:
    print(f"[SUCCESS] {email} is now verified!")
else:
    print(f"[ERROR] Could not find user with email {email}")

conn.close()
