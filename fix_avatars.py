
import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, 'users.db')

DEFAULT_AVATAR = "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxMDAgMTAwIj48cmVjdCB3aWR0aD0iMTAwIiBoZWlnaHQ9IjEwMCIgZmlsbD0iIzU4NjVmMiIvPjwvc3ZnPg=="

def fix_avatars():
    print(f"Checking {DB_FILE}...")
    if not os.path.exists(DB_FILE):
        print("users.db not found. Skipping.")
        return

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # 1. Select all users with http/https avatars (likely CDNs)
    c.execute("SELECT id, username, avatar FROM users WHERE avatar LIKE 'http%'")
    rows = c.fetchall()
    
    print(f"Found {len(rows)} users with external avatars.")
    
    count = 0
    for row in rows:
        uid, name, av = row
        print(f"  - Fixing {name} ({uid})...")
        c.execute("UPDATE users SET avatar = ? WHERE id = ?", (DEFAULT_AVATAR, uid))
        count += 1
        
    conn.commit()
    conn.close()
    print(f"Fixed {count} avatars.")

if __name__ == "__main__":
    fix_avatars()
