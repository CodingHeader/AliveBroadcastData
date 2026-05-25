"""
迁移脚本：为deals表的lead_id列添加UNIQUE约束
防止同一线索被重复标记成单
"""
import sys
from pathlib import Path

# 动态计算 server 目录路径（脚本位于 scripts/，server 是其父目录）
SERVER_DIR = str(Path(__file__).resolve().parent.parent / "server")
sys.path.insert(0, SERVER_DIR)

from database import engine
from sqlalchemy import text

def migrate():
    with engine.connect() as conn:
        # 检查是否已有同名约束
        result = conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='deals' AND sql LIKE '%UNIQUE%lead_id%'"
        )).fetchone()
        if result:
            print(f"已存在UNIQUE约束: {result[0]}，跳过")
            return
        
        # 检查重复数据
        dups = conn.execute(text(
            "SELECT lead_id, COUNT(*) as cnt FROM deals WHERE lead_id IS NOT NULL GROUP BY lead_id HAVING cnt > 1"
        )).fetchall()
        if dups:
            print(f"警告: 发现 {len(dups)} 个重复lead_id，需清理后才能添加约束")
            for lead_id, cnt in dups:
                print(f"  lead_id={lead_id}: {cnt}条记录")
            print("请先手动处理重复数据，再重新运行此脚本")
            return
        
        # 添加UNIQUE索引（SQLite中用UNIQUE INDEX实现约束）
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS idx_deals_lead_id_unique ON deals(lead_id)"))
        conn.commit()
        print("成功: deals.lead_id UNIQUE约束已添加")

if __name__ == "__main__":
    migrate()
