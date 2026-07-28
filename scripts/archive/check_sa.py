from database import engine
from sqlalchemy import text

with engine.connect() as conn:
    r = conn.execute(text("SELECT sql FROM sqlite_master WHERE type='table' AND name='session_anchors'"))
    row = r.fetchone()
    print("Table schema:", row)

    r2 = conn.execute(text("SELECT * FROM session_anchors LIMIT 5"))
    for row in r2.fetchall():
        print("SA:", row)
