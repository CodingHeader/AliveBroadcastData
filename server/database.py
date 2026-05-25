from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()

class Base(DeclarativeBase):
    pass

def init_db():
    """创建所有表 + 初始化默认配置"""
    from models import Session, SessionMetric, Lead, Comment, HighIntentUser, Report, Anchor, SessionAnchor, Deal, Setting
    from auth import hash_password
    from config import DEFAULT_ADMIN_USERNAME, DEFAULT_ADMIN_PASSWORD
    from datetime import datetime
    
    import os
    Base.metadata.create_all(bind=engine)
    
    # 迁移：已有数据库添加share_rate列
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE session_metrics ADD COLUMN share_rate TEXT"))
    except Exception:
        pass

    # 迁移：创建private_messages表
    try:
        with engine.connect() as conn:
            conn.execute(text("""CREATE TABLE IF NOT EXISTS private_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL REFERENCES sessions(id),
                nickname TEXT NOT NULL,
                douyin_id TEXT,
                has_lead BOOLEAN DEFAULT 0,
                last_message_time TEXT,
                last_reply_time TEXT,
                pending_reply TEXT,
                message_count INTEGER DEFAULT 0,
                ai_reply_count INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )"""))
            conn.commit()
    except Exception:
        pass
    
    db = SessionLocal()
    try:
        default_settings = [
            ("admin_username", DEFAULT_ADMIN_USERNAME),
            ("admin_password", hash_password(DEFAULT_ADMIN_PASSWORD)),
            ("ai_api_key", os.getenv("AI_API_KEY", "")),
            ("ai_base_url", os.getenv("AI_BASE_URL", "https://api.openai.com/v1")),
            ("ai_model", os.getenv("AI_MODEL", "gpt-4o")),
            ("ai_system_prompt", "你是一位专业的抖音本地生活直播数据分析师，擅长从数据中挖掘可执行的运营策略。\n\n## 分析方法论\n\n### 五维四率（核心框架）\n- 五维：曝光人数 → 观看人数 → 商品曝光次数 → 商品点击人数 → 留资人数\n- 四率：观看点击率(进房率)、商品点击率、商品留资率、点击成交率\n\n请按此漏斗逐层分析：哪个环节转化率最低？为什么？如何优化？\n\n### 复盘策略\n#### 日复盘\n- 查看数据曲线中曝光量和进房人数最高的时间点\n- 分析该时间点的画面和话术亮点，总结可复用的好经验\n\n#### 周复盘\n- 找流量规律：哪场数据好/为什么/投流计划调整方向\n- 找高互动话术和内容模式\n\n#### 阶段性复盘\n- 主播需理解运营思维：曝光量、进房率、留资数量、投流成本\n- 运用表格进行深度数据对比\n- 团队配合：运营负责最大化曝光，主播负责转化\n- 投流计划优化迭代（圈地域/人群/时间点/出价等）\n- 私域产品升级（已报名学员专场直播、品牌IP塑造等）\n\n### 输出要求\n1. 五维四率漏斗分析（标注每个环节转化率，找出瓶颈环节）\n2. 日复盘亮点和留存策略\n3. 本场表现的量化评价\n4. 3-5条具体可执行的优化建议（区分运营侧和主播侧）"),
            ("ai_user_prompt_template", """请按以下结构分析本场直播数据：

## 基础信息
- 直播时间：{{start_time}} ~ {{end_time}}
- 直播时长：{{duration_minutes}}分钟
- 营销消耗：¥{{ad_spend}}

## 核心指标（44项）
{{metrics_text}}

## 线索列表（共{{leads_count}}条）
{{leads_text}}

## 评论明细（共{{comments_count}}条）
{{comments_text}}

## 高意向用户（共{{high_intent_count}}个）
{{high_intent_text}}

## 分析要求
请遵循五维四率方法论和复盘策略，按以下格式输出：

### 一、整体评价
用1-10分评价本场表现，1-2句话概括

### 二、五维数据概览
按五个维度逐层展示数据：曝光人数→观看人数→商品曝光次数→商品点击人数→留资人数

### 三、四率漏斗分析
逐层计算转化率，标注瓶颈环节：
1. 观看点击率(进房率) = 观看人数/曝光人数
2. 商品点击率 = 商品点击人数/观看人数
3. 商品留资率 = 留资人数/商品点击人数
4. 点击成交率(结合成单数据)

### 四、复盘亮点与问题
- 亮点：曝光和进房峰值时段分析，高互动话术总结
- 问题：数据异常环节识别

### 五、优化建议
区分运营侧和主播侧，给出3-5条具体可执行的建议"""),
            ("email_smtp_host", "smtp.163.com"),
            ("email_smtp_port", "465"),
            ("email_sender", os.getenv("EMAIL_SENDER", "")),
            ("email_password", os.getenv("EMAIL_PASSWORD", "")),
            ("email_receivers", os.getenv("EMAIL_RECEIVERS", '["your_email@example.com"]')),
            ("push_frequency", "daily"),
            ("push_daily_enabled", "true"),
            ("push_daily_receivers", '["your_email@example.com"]'),
            ("push_weekly_enabled", "true"),
            ("push_weekly_receivers", '["your_email@example.com"]'),
            ("push_monthly_enabled", "true"),
            ("push_monthly_receivers", '["your_email@example.com"]'),
        ]
        
        for key, value in default_settings:
            existing = db.query(Setting).filter(Setting.key == key).first()
            if not existing:
                db.add(Setting(key=key, value=str(value)))
        
        # 数据库迁移：已有环境添加assigned_employee列
        try:
            from sqlalchemy import text
            conn = engine.connect()
            conn.execute(text("ALTER TABLE leads ADD COLUMN assigned_employee TEXT"))
            conn.commit()
            conn.close()
        except Exception:
            pass  # 列已存在或其他错误，忽略
        
        db.commit()
    finally:
        db.close()

def get_db():
    """FastAPI依赖注入: 提供数据库Session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
