import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))
from database import SessionLocal
from models import SessionMetric, Lead, Session, Comment
from sqlalchemy import func

def fix():
    db = SessionLocal()
    try:
        # 自动检测所有session，而非硬编码ID
        all_sessions = db.query(Session).order_by(Session.id).all()
        if not all_sessions:
            print("数据库中无任何session，退出")
            return
        for session in all_sessions:
            sid = session.id
            m = db.query(SessionMetric).filter(SessionMetric.session_id == sid).first()
            if not m:
                print(f"Session {sid} metrics 不存在，跳过")
                continue
            log = f"[Session {sid} {session.start_time}]"
            # 1. interaction_users → interaction_count
            if m.interaction_users and m.interaction_count and m.interaction_users != m.interaction_count:
                old = m.interaction_users
                m.interaction_users = m.interaction_count
                print(f"  {log} interaction_users: {old} → {m.interaction_count}")
            # 2. exposure_times → exposure_count
            if m.exposure_times and m.exposure_count and m.exposure_times != m.exposure_count:
                old = m.exposure_times
                m.exposure_times = m.exposure_count
                print(f"  {log} exposure_times: {old} → {m.exposure_count}")
            # 3. total_leads → Lead.count
            real_leads = db.query(Lead).filter(Lead.session_id == sid).count()
            if m.total_leads != real_leads:
                old = m.total_leads
                m.total_leads = real_leads
                print(f"  {log} total_leads: {old} → {real_leads}")
            # 4. lead_cost → ad_spend / total_leads
            if real_leads > 0 and m.ad_spend:
                correct_cost = round(float(m.ad_spend) / real_leads, 1)
                if not m.lead_cost or abs(float(m.lead_cost or 0) - correct_cost) > 0.1:
                    old = m.lead_cost
                    m.lead_cost = correct_cost
                    print(f"  {log} lead_cost: {old} → {correct_cost}")
            # 5. comment_users → COUNT(DISTINCT nickname)
            real_comment_users = db.query(func.count(func.distinct(Comment.nickname))).filter(Comment.session_id == sid).scalar() or 0
            if m.comment_users != real_comment_users:
                old = m.comment_users
                m.comment_users = real_comment_users
                print(f"  {log} comment_users: {old} → {real_comment_users}")
        db.commit()
        print("修复完成")
    except Exception as e:
        db.rollback()
        print(f"修复失败: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    fix()
