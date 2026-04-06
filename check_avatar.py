import sqlite3

conn = sqlite3.connect('users.db')
c = conn.cursor()

# Find all users and their avatar info
c.execute("SELECT id, username, display_name, LENGTH(avatar) as avlen, SUBSTR(avatar,1,100) as avpreview FROM users ORDER BY id LIMIT 20")
rows = c.fetchall()
for r in rows:
    uid, uname, dname, avlen, avprev = r
    print(f"ID={uid} name={uname} display={dname} avatar_len={avlen} preview={avprev[:80] if avprev else 'NULL'!r}")

conn.close()
