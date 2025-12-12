import sqlite3
import os

db_path = 'discord.db'
if not os.path.exists(db_path):
    print("DB not found at", db_path)
else:
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute('SELECT id, username FROM users')
        users = c.fetchall()
        print("Users found:", users)
        conn.close()
    except Exception as e:
        print("Error:", e)
