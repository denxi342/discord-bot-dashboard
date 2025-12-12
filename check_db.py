import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'users.db')

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
try:
    c.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in c.fetchall()]
    print(f"Columns in users: {columns}")
except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()
