import sqlite3
import os

db_path = 'discord.db'
if not os.path.exists(db_path):
    print("DB not found")
else:
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        print("--- USERS ---")
        c.execute('SELECT id, username FROM users')
        for r in c.fetchall():
            print(r)
            
        print("\n--- FRIENDS TABLE ---")
        c.execute('SELECT * FROM friends')
        friends = c.fetchall()
        if not friends:
            print("No friend records found.")
        for r in friends:
            print(r)
        conn.close()
    except Exception as e:
        print("Error:", e)
