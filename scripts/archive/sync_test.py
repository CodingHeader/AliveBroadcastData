from database import SessionLocal
from models import ScheduleBinding, SchedulePlan, SessionAnchor
from routers.admin import _sync_session_anchors
import json

db = SessionLocal()
plan = db.query(SchedulePlan).first()

for d in ['2026-05-20', '2026-05-21']:
    binding = db.query(ScheduleBinding).filter(ScheduleBinding.date == d).first()
    if binding:
        am = json.loads(binding.anchor_mapping) if binding.anchor_mapping else {}
        _sync_session_anchors(db, d, plan, am)
        print(f'synced {d}')

print('SA count:', db.query(SessionAnchor).count())
