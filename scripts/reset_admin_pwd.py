import sqlite3
import bcrypt

password = 'admin123'
hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
print(f"Hash: {hashed}")

conn = sqlite3.connect('E:/Code/AliveBroadcastData/server/data.db')
cur = conn.cursor()
cur.execute("UPDATE settings SET value = ? WHERE key = 'admin_password'", (hashed,))
conn.commit()
print(f"Updated {cur.rowcount} rows")
conn.close()