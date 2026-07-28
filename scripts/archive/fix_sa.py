"""清理6月9日重复的SessionAnchor数据"""
from database import SessionLocal
from models import SessionAnchor, Session

db = SessionLocal()

# 检查6月9日的session
sessions = db.query(Session).filter(Session.start_time.like('2026-06-09%')).order_by(Session.start_time).all()
print(f"6月9日共有 {len(sessions)} 个session:")
for s in sessions:
    sa_count = db.query(SessionAnchor).filter(SessionAnchor.session_id == s.id).count()
    print(f"  session_id={s.id}, start={s.start_time}, end={s.end_time}, SessionAnchors={sa_count}")

# 两个session的SessionAnchor完全相同，说明是同一天的直播被拆成了两个session
# session_id=2: 08:00-15:32 (白天场)
# session_id=1: 16:02-次日01:02 (晚间场)
# 但_sync_session_anchors为每个session都创建了7条记录，这是错误的
# 应该是：每个session只包含该时段内的主播

# 查看每个session的SessionAnchor详情
for s in sessions:
    sas = db.query(SessionAnchor).filter(SessionAnchor.session_id == s.id).order_by(SessionAnchor.anchor_order).all()
    print(f"\nsession_id={s.id} ({s.start_time} - {s.end_time}):")
    for sa in sas:
        from models import Anchor
        anchor = db.query(Anchor).get(sa.anchor_id)
        print(f"  anchor={anchor.name}, on={sa.on_time}, off={sa.off_time}, order={sa.anchor_order}")

# 实际上两个session的时段应该不同：
# session_id=2 (08:00-15:32): 只有白天的时段
# session_id=1 (16:02-01:02): 只有晚间的时段
# 但当前两个session都有全部7个时段，这是错误的

# 修复方案：删除session_id=2中晚间时段(17:00以后)的记录，删除session_id=1中白天时段(14:00以前)的记录
print("\n=== 修复方案 ===")
print("session_id=2 (08:00-15:32): 保留 01:00-02:00, 08:00-10:00, 11:00-14:00")
print("session_id=1 (16:02-01:02): 保留 17:00-19:00, 19:00-21:00, 21:00-23:00, 23:00-25:00")

# 执行修复
# session_id=2: 删除晚间时段
del_count = db.query(SessionAnchor).filter(
    SessionAnchor.session_id == 2,
    SessionAnchor.on_time.in_(['17:00', '19:00', '21:00', '23:00'])
).delete()
print(f"删除session_id=2的晚间时段: {del_count}条")

# session_id=1: 删除白天时段
del_count2 = db.query(SessionAnchor).filter(
    SessionAnchor.session_id == 1,
    SessionAnchor.on_time.in_(['01:00', '08:00', '11:00'])
).delete()
print(f"删除session_id=1的白天时段: {del_count2}条")

db.commit()

# 验证
print("\n=== 修复后 ===")
for s in sessions:
    sas = db.query(SessionAnchor).filter(SessionAnchor.session_id == s.id).order_by(SessionAnchor.anchor_order).all()
    print(f"session_id={s.id} ({s.start_time} - {s.end_time}):")
    for sa in sas:
        anchor = db.query(Anchor).get(sa.anchor_id)
        print(f"  anchor={anchor.name}, on={sa.on_time}, off={sa.off_time}, order={sa.anchor_order}")

db.close()
