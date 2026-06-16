import sqlite3, json, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))
os.chdir(os.path.join(os.path.dirname(__file__), '..', 'server'))

conn = sqlite3.connect('data.db')
cur = conn.cursor()

mapping = json.dumps({"1": 1, "2": 2, "3": 3})
for date_str in ['2026-06-09', '2026-06-08', '2026-06-10']:
    cur.execute("UPDATE schedule_bindings SET anchor_mapping = ? WHERE date = ? AND plan_id = ?",
                (mapping, date_str, 2))
    print(f'Updated {cur.rowcount} binding for {date_str}')

conn.commit()

cur.execute('SELECT id, date, plan_id, anchor_mapping FROM schedule_bindings')
for r in cur.fetchall():
    print(f'  id={r[0]} date={r[1]} plan={r[2]} mapping={r[3]}')

conn.close()

# Now trigger _sync_session_anchors from the admin module
print("\nTriggering _sync_session_anchors...")
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as SASession
from models import SchedulePlan, ScheduleBinding, SessionAnchor, Session
from routers.admin import _sync_session_anchors

engine = create_engine('sqlite:///data.db')
sa_session = SASession(engine)

plan = sa_session.query(SchedulePlan).filter(SchedulePlan.id == 2).first()
binding = sa_session.query(ScheduleBinding).filter(
    ScheduleBinding.date == '2026-06-09',
    ScheduleBinding.plan_id == 2
).first()

if binding:
    anchor_mapping = json.loads(binding.anchor_mapping) if binding.anchor_mapping else {}
    print(f"Binding: date={binding.date}, mapping={anchor_mapping}")
    _sync_session_anchors(sa_session, '2026-06-09', plan, anchor_mapping)
    sa_session.commit()

    # Also sync 2026-06-08 and 2026-06-10
    for date_str in ['2026-06-08', '2026-06-10']:
        b = sa_session.query(ScheduleBinding).filter(
            ScheduleBinding.date == date_str,
            ScheduleBinding.plan_id == 2
        ).first()
        if b:
            m = json.loads(b.anchor_mapping) if b.anchor_mapping else {}
            print(f"Syncing {date_str}: mapping={m}")
            _sync_session_anchors(sa_session, date_str, plan, m)
            sa_session.commit()

sa_session.close()

print("\n=== SessionAnchors after sync ===")
cur.execute('''
    SELECT sa.id, sa.session_id, s.start_time, a.name, sa.anchor_order, sa.on_time, sa.off_time
    FROM session_anchors sa
    LEFT JOIN sessions s ON sa.session_id = s.id
    LEFT JOIN anchors a ON sa.anchor_id = a.id
    ORDER BY sa.session_id, sa.anchor_order
''')
for r in cur.fetchall():
    print(f'  id={r[0]} session={r[1]} start={r[2]} anchor={r[3]} order={r[4]} on={r[5]} off={r[6]}')
conn.close()
