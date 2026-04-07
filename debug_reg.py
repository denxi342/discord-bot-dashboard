import sqlite3
import os

db_path = 'C:/Users/kompd/.gemini/antigravity/scratch/discord_bot/users.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()

email = 'dedmaged@gmail.com'

# Check users
c.execute("SELECT username, email, is_verified FROM users WHERE email = ?", (email,))
user = c.fetchone()
print(f"User info: {user}")

# Check verification_codes
c.execute("SELECT * FROM verification_codes WHERE email = ?", (email,))
codes = c.fetchall()
print(f"Verification codes for {email}: {codes}")

# Check ALL verification codes to be sure
c.execute("SELECT * FROM verification_codes")
all_codes = c.fetchall()
print(f"All verification codes: {all_codes}")

conn.close()
