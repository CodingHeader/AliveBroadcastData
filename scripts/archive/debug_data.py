from database import engine
from sqlalchemy import text
conn = engine.connect()

# 检查6月9日的SessionAnchor详细数据
print("=== SessionAnchor (6月9日) ===")
r = conn.execute(text("""
    SELECT sa.id, sa.session_id, sa.anchor_id, a.name, sa.on_time, sa.off_time, sa.anchor_order
    FROM session_anchors sa
    JOIN anchors a ON a.id = sa.anchor_id
    JOIN sessions s ON s.id = sa.session_id
    WHERE s.start_time LIKE '2026-06-09%'
    ORDER BY sa.session_id, sa.anchor_order
"""))
for row in r.fetchall():
    # 计算时长
    on_parts = row[4].split(":")
    off_parts = row[5].split(":")
    on_min = int(on_parts[0]) * 60 + int(on_parts[1])
    off_min = int(off_parts[0]) * 60 + int(off_parts[1])
    if off_min < on_min: off_min += 24 * 60
    dur = off_min - on_min
    print(f"  session_id={row[1]}, anchor={row[3]}, {row[4]}-{row[5]}, order={row[6]}, duration={dur}min")

# 检查6月9日的Lead数据
print("\n=== Lead (6月9日session) ===")
r2 = conn.execute(text("""
    SELECT l.id, l.session_id, l.source, l.is_valid, l.ad_account
    FROM leads l
    JOIN sessions s ON s.id = l.session_id
    WHERE s.start_time LIKE '2026-06-09%'
"""))
for row in r2.fetchall():
    print(f"  id={row[0]}, session_id={row[1]}, source={row[2]}, is_valid={row[3]}, ad_account={row[4]}")

# 检查6月9日的Comment数据
print("\n=== Comment (6月9日session) ===")
r3 = conn.execute(text("""
    SELECT c.id, c.session_id, c.has_lead, c.nickname
    FROM comments c
    JOIN sessions s ON s.id = c.session_id
    WHERE s.start_time LIKE '2026-06-09%'
    LIMIT 10
"""))
for row in r3.fetchall():
    print(f"  id={row[0]}, session_id={row[1]}, has_lead={row[2]}, nickname={row[3]}")

# 检查6月9日的PrivateMessage数据
print("\n=== PrivateMessage (6月9日session) ===")
r4 = conn.execute(text("""
    SELECT pm.id, pm.session_id, pm.has_lead
    FROM private_messages pm
    JOIN sessions s ON s.id = pm.session_id
    WHERE s.start_time LIKE '2026-06-09%'
    LIMIT 10
"""))
for row in r4.fetchall():
    print(f"  id={row[0]}, session_id={row[1]}, has_lead={row[2]}")

# 按主播统计时长
print("\n=== 按主播统计时长 ===")
r5 = conn.execute(text("""
    SELECT a.name,
           SUM(CASE WHEN CAST(sa.off_time AS INTEGER) < CAST(sa.on_time AS INTEGER)
                THEN (CAST(SUBSTR(sa.off_time,1,2) AS INTEGER)*60 + CAST(SUBSTR(sa.off_time,4,2) AS INTEGER) + 1440)
                    - (CAST(SUBSTR(sa.on_time,1,2) AS INTEGER)*60 + CAST(SUBSTR(sa.on_time,4,2) AS INTEGER))
                ELSE (CAST(SUBSTR(sa.off_time,1,2) AS INTEGER)*60 + CAST(SUBSTR(sa.off_time,4,2) AS INTEGER))
                    - (CAST(SUBSTR(sa.on_time,1,2) AS INTEGER)*60 + CAST(SUBSTR(sa.on_time,4,2) AS INTEGER))
           END) as total_minutes
    FROM session_anchors sa
    JOIN anchors a ON a.id = sa.anchor_id
    JOIN sessions s ON s.id = sa.session_id
    WHERE s.start_time LIKE '2026-06-09%'
    GROUP BY a.name
"""))
for row in r5.fetchall():
    print(f"  {row[0]}: {row[1]}分钟 = {row[1]/60:.1f}小时")

# 按session统计线索
print("\n=== 按session统计线索 ===")
r6 = conn.execute(text("""
    SELECT s.id, s.start_time, COUNT(l.id) as lead_count
    FROM sessions s
    LEFT JOIN leads l ON l.session_id = s.id
    WHERE s.start_time LIKE '2026-06-09%'
    GROUP BY s.id
"""))
for row in r6.fetchall():
    print(f"  session_id={row[0]}, start={row[1]}, leads={row[2]}")
