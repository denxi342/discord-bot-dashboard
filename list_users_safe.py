import sqlite3
import os

db_path = 'users.db'
if not os.path.exists(db_path):
    print("Database not found!")
    exit(1)

conn = sqlite3.connect(db_path)
cur = conn.cursor()
cur.execute('SELECT id, username, role FROM users')
rows = cur.fetchall()

print("--- USER LIST ---")
for r in rows:
    try:
        # Avoid print errors
        print(f"ID: {r[0]}, User: {r[1].encode('ascii', 'ignore').decode()}, Role: {r[2]}")
    except:
        print(f"ID: {r[0]}, [ENCODE ERROR], Role: {r[2]}")
conn.close()
