import sqlite3
conn = sqlite3.connect('campus.db')
c = conn.cursor()
c.execute("SELECT email, role FROM users LIMIT 30")
rows = c.fetchall()
for r in rows:
    print(r)
conn.close()
