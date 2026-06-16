import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))
os.chdir(os.path.join(os.path.dirname(__file__), '..', 'server'))
os.environ['CONFIG_PATH'] = os.path.join(os.path.dirname(__file__), '..', 'server', 'config.py')

from sqlalchemy import create_engine, func, case
from sqlalchemy.orm import Session as SASession
from models import Session, Anchor, SessionAnchor, Lead, Comment, PrivateMessage

engine = create_engine('sqlite:///data.db')
db = SASession(engine)

try:
    query = db.query(
        Session.id.label('session_id'),
        Session.start_time.label('session_start'),
        Session.end_time.label('session_end'),
        Session.duration_minutes,
        Anchor.id.label('anchor_id'),
        Anchor.name.label('anchor_name'),
        SessionAnchor.on_time,
        SessionAnchor.off_time,
        SessionAnchor.anchor_order,
    ).join(
        SessionAnchor, Session.id == SessionAnchor.session_id
    ).join(
        Anchor, SessionAnchor.anchor_id == Anchor.id
    )

    rows = query.order_by(Session.start_time, SessionAnchor.anchor_order).all()
    print(f'Rows: {len(rows)}')

    result = []
    session_counter = {}
    for row in rows:
        date_str = row.session_start[:10] if row.session_start else ''
        if date_str not in session_counter:
            session_counter[date_str] = 0
        session_counter[date_str] += 1

        on_time = row.on_time
        off_time = row.off_time

        if on_time and off_time:
            try:
                on_parts = on_time.split(':')
                off_parts = off_time.split(':')
                on_minutes = int(on_parts[0]) * 60 + int(on_parts[1])
                off_minutes = int(off_parts[0]) * 60 + int(off_parts[1])
                if off_minutes < on_minutes:
                    off_minutes += 24 * 60
                duration_hours = round((off_minutes - on_minutes) / 60.0, 2)
            except Exception as ex:
                print(f'Error parsing time: {ex}')
                duration_hours = 0
        else:
            duration_hours = round((row.duration_minutes or 0) / 60.0, 2)

        income = round(duration_hours * 40, 2)

        try:
            hour = int(on_time.split(':')[0])
            session_period = '上午场' if 6 <= hour < 12 else ('下午场' if 12 <= hour < 18 else '晚间场')
        except:
            session_period = '未知'

        result.append({
            'date': date_str,
            'anchor_name': row.anchor_name,
            'duration_hours': duration_hours,
            'income': income,
            'session_period': session_period
        })

    print(f'Processed: {len(result)} rows')
    for r in result:
        print(f'  date={r["date"]} anchor={r["anchor_name"]} period={r["session_period"]} hours={r["duration_hours"]} income={r["income"]}')

    print(f'\nTotal income: {sum(r["income"] for r in result)}')
    print(f'Total hours: {sum(r["duration_hours"] for r in result)}')

except Exception as e:
    import traceback
    traceback.print_exc()
finally:
    db.close()
