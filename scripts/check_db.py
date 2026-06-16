import sqlite3
conn = sqlite3.connect('E:\\Code\\AliveBroadcastData\\server\\data.db')
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [r[0] for r in cur.fetchall()]
print('Tables:', tables)
print('Has private_messages:', 'private_messages' in tables)
print()

# Check private_messages columns
if 'private_messages' in tables:
    cur.execute('PRAGMA table_info(private_messages)')
    print('private_messages columns:')
    for r in cur.fetchall():
        print(f'  {r}')

# Check leads columns
cur.execute('PRAGMA table_info(leads)')
print('\nleads columns:')
for r in cur.fetchall():
    print(f'  {r}')
conn.close()
