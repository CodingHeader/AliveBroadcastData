import sqlite3

DB = 'data.db'

def migrate():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    # 统计修复前的情况
    c.execute("SELECT COUNT(*) FROM schedule_slots WHERE slot_status = 'on_air_empty'")
    empty_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM schedule_slots WHERE slot_status = 'on_air_anchor'")
    anchor_count = c.fetchone()[0]

    print(f"修复前统计:")
    print(f"  开播无主播 (on_air_empty): {empty_count} 条")
    print(f"  开播有主播 (on_air_anchor): {anchor_count} 条")

    # 将所有 on_air_empty 修复为 on_air_anchor
    # 注意：这会覆盖用户可能手动设置的"开播无主播"，但新建方案默认应该是有主播
    c.execute("UPDATE schedule_slots SET slot_status = 'on_air_anchor' WHERE slot_status = 'on_air_empty'")
    updated = c.rowcount

    conn.commit()
    conn.close()

    print(f"\n修复完成: 已将 {updated} 条记录从 'on_air_empty' 更新为 'on_air_anchor'")

if __name__ == '__main__':
    migrate()
