import sqlite3
import os
import sys

print("Python executable:", sys.executable)
print("Current working directory:", os.getcwd())

db_path = os.path.abspath('users.db')
print("Target DB path:", db_path)

if not os.path.exists(db_path):
    print("ERROR: DB does not exist at path.")
    # Search for it?
    for root, dirs, files in os.walk('.'):
        if 'discord.db' in files:
            print("Found discord.db at:", os.path.join(root, 'discord.db'))
else:
    print("DB file exists. Size:", os.path.getsize(db_path))
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        print("\n--- USERS ---")
        c.execute("SELECT * FROM users")
        for r in c.fetchall():
            print(r)
            
        print("\n--- FRIENDS ---")
        c.execute("SELECT * FROM friends")
        friends = c.fetchall()
        if not friends:
            print("Friends table is EMPTY.")
        else:
            for r in friends:
                print(r)
                
        conn.close()
    except Exception as e:
        print("SQL ERROR:", e)
