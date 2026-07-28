#!/usr/bin/env python3
import sqlite3

DB = 'data.db'

def migrate():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("PRAGMA table_info(leads)")
    cols = [r[1] for r in c.fetchall()]
    if 'source' in cols:
        print("[OK] source字段已存在")
    else:
        c.execute("ALTER TABLE leads ADD COLUMN source TEXT")
        c.execute("UPDATE leads SET source='api' WHERE source IS NULL")
        conn.commit()
        print("[OK] source字段添加成功")
    conn.close()

migrate()
