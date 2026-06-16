import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))
os.chdir(os.path.join(os.path.dirname(__file__), '..', 'server'))
os.environ['CONFIG_PATH'] = os.path.join(os.path.dirname(__file__), '..', 'server', 'config.py')

from sqlalchemy import create_engine
from sqlalchemy.orm import Session as SASession
from models import Session, Anchor, SessionAnchor
from services.anchor_stats_service import get_comprehensive_stats

engine = create_engine('sqlite:///data.db')
db = SASession(engine)

# Check data first
print('=== SessionAnchors ===')
rows = db.query(SessionAnchor).all()
for r in rows:
    print(f'  id={r.id} session={r.session_id} anchor={r.anchor_id} order={r.anchor_order} on={r.on_time} off={r.off_time}')

print('\n=== get_comprehensive_stats ===')
try:
    stats = get_comprehensive_stats(db, '2026-06-09', '2026-06-09')
    print(f'daily_detail: {len(stats["daily_detail"])} rows')
    for item in stats['daily_detail'][:3]:
        print(f'  {json.dumps({k: str(v) if not isinstance(v, (int, float)) else v for k, v in item.items()}, ensure_ascii=False)[:200]}')
    print(f'\nanchor_summary: {len(stats["anchor_summary"])} rows')
    for item in stats['anchor_summary']:
        print(f'  {json.dumps({k: str(v) if not isinstance(v, (int, float)) else v for k, v in item.items()}, ensure_ascii=False)[:200]}')
    print(f'\noverall_summary: {json.dumps({k: str(v) if not isinstance(v, (int, float)) else v for k, v in stats["overall_summary"].items()}, ensure_ascii=False)}')
except Exception as e:
    import traceback
    traceback.print_exc()
finally:
    db.close()
