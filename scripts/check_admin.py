import sqlite3
conn = sqlite3.connect('E:/Code/AliveBroadcastData/server/data.db')
cur = conn.cursor()
cur.execute("SELECT key, value FROM settings WHERE key LIKE 'admin_%'")
rows = cur.fetchall()
for r in rows:
    print(r)
conn.close()