import sqlite3

for db_name in ['data.db', 'alive_broadcast.db']:
    print(f"\n=== {db_name} ===")
    try:
        conn = sqlite3.connect(f'E:/Code/AliveBroadcastData/server/{db_name}')
        cur = conn.cursor()
        cur.execute("SELECT key, value FROM settings WHERE key LIKE 'admin_%'")
        rows = cur.fetchall()
        if rows:
            for r in rows:
                print(r)
        else:
            print("No admin settings found")
        conn.close()
    except Exception as e:
        print(f"Error: {e}")