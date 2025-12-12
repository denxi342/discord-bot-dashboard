import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'users.db')

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

cols = ['display_name', 'banner', 'bio', 'email', 'phone']
for col in cols:
    try:
        c.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT")
        print(f"Added {col}")
    except Exception as e:
        print(f"Skipped {col}: {e}")

conn.commit()
conn.close()
print("DB fix complete.")
