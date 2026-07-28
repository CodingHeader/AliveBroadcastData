import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'data.db')
print(f'DB path: {db_path}')
print(f'DB exists: {os.path.exists(db_path)}')

conn = sqlite3.connect(db_path)
c = conn.cursor()

print('\n=== All Tables ===')
c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
for r in c.fetchall():
    print(f'  {r[0]}')

print('\n=== Sessions (June 9) ===')
c.execute("SELECT id, start_time, end_time, duration_minutes FROM sessions WHERE start_time LIKE '2026-06-09%' ORDER BY start_time")
rows = c.fetchall()
for r in rows:
    print(f'  id={r[0]} | start={r[1]} | end={r[2]} | duration={r[3]}min')
print(f'  Total: {len(rows)} sessions')

print('\n=== Anchors ===')
c.execute('SELECT id, name FROM anchors ORDER BY id')
for r in c.fetchall():
    print(f'  id={r[0]} | name={r[1]}')

print('\n=== Session Anchors (June 9) ===')
c.execute("""
    SELECT sa.id, sa.session_id, sa.anchor_id, a.name, sa.on_time, sa.off_time, sa.anchor_order, s.start_time 
    FROM session_anchors sa 
    JOIN anchors a ON sa.anchor_id=a.id 
    JOIN sessions s ON sa.session_id=s.id 
    WHERE s.start_time LIKE '2026-06-09%' 
    ORDER BY s.start_time, sa.anchor_order
""")
for r in c.fetchall():
    print(f'  sa={r[0]} | sid={r[1]} | aid={r[2]} | name={r[3]} | on={r[4]} | off={r[5]} | order={r[6]} | sess_start={r[7]}')

print('\n=== Session Metrics (June 9) ===')
c.execute("""
    SELECT sm.session_id, sm.total_leads, sm.ad_spend, sm.comment_count, s.start_time 
    FROM session_metrics sm 
    JOIN sessions s ON sm.session_id=s.id 
    WHERE s.start_time LIKE '2026-06-09%'
""")
for r in c.fetchall():
    print(f'  sid={r[0]} | leads={r[1]} | spend={r[2]} | comments={r[3]} | start={r[4]}')

print('\n=== Leads per session (June 9) ===')
c.execute("""
    SELECT s.id, s.start_time, COUNT(l.id) as lead_count 
    FROM sessions s 
    LEFT JOIN leads l ON s.id=l.session_id 
    WHERE s.start_time LIKE '2026-06-09%' 
    GROUP BY s.id
""")
for r in c.fetchall():
    print(f'  sid={r[0]} | start={r[1]} | leads={r[2]}')

print('\n=== Comments per session (June 9) ===')
c.execute("""
    SELECT s.id, s.start_time, COUNT(c.id) as comment_count 
    FROM sessions s 
    LEFT JOIN comments c ON s.id=c.session_id 
    WHERE s.start_time LIKE '2026-06-09%' 
    GROUP BY s.id
""")
for r in c.fetchall():
    print(f'  sid={r[0]} | start={r[1]} | comments={r[2]}')

conn.close()
print('\nDone.')