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
    from models import Session, SessionMetric, Lead, Comment, HighIntentUser, Report, Anchor, SessionAnchor, Deal, Setting, SchedulePlan, ScheduleSlot, ScheduleBinding, AdAccount, RoomAccountBinding, ApiClue, ClueConfig, DashboardTab, TabAnalysis, RecruitTeam, RecruitEmployee, ClueAssignment, AdPlan, AdPlanSpend, MultiDimRecord, MultiDimImportBatch, MultiDimImportSkip, ScheduleDay, ScheduleDayAnchor, WeekdayDefault, ScheduleDayOperator, Operator, CollectionLog
    from auth import hash_password
    from config import DEFAULT_ADMIN_USERNAME, DEFAULT_ADMIN_PASSWORD
    from datetime import datetime
    
    import os
    Base.metadata.create_all(bind=engine)
    
    # 迁移：已有数据库添加share_rate列
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE session_metrics ADD COLUMN share_rate TEXT"))
            conn.commit()
    except Exception:
        pass

    # 迁移：anchors表添加gender和style列
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE anchors ADD COLUMN gender TEXT"))
            conn.commit()
    except Exception:
        pass
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE anchors ADD COLUMN style TEXT"))
            conn.commit()
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
            ("email_receivers", os.getenv("EMAIL_RECEIVERS", '["164093410@qq.com"]')),
            ("push_frequency", "daily"),
            ("push_daily_enabled", "true"),
            ("push_daily_receivers", '["164093410@qq.com"]'),
            ("push_weekly_enabled", "true"),
            ("push_weekly_receivers", '["164093410@qq.com"]'),
            ("push_monthly_enabled", "true"),
            ("push_monthly_receivers", '["164093410@qq.com"]'),
            ("dashboard_default_system_prompt", "你是一位专业的抖音直播数据分析师，请根据以下数据指标进行分析，给出简洁的洞察和优化建议。"),
            ("dashboard_default_user_prompt", "请分析以下时间范围内的数据指标趋势，重点关注变化幅度较大的指标，并给出可执行的优化建议。"),
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

        try:
            from sqlalchemy import text
            conn = engine.connect()
            conn.execute(text("ALTER TABLE leads ADD COLUMN weixin TEXT"))
            conn.commit()
            conn.close()
        except Exception:
            pass  # 列已存在或其他错误，忽略
        
        # 初始化默认总览Tab
        default_tab = db.query(DashboardTab).filter(DashboardTab.is_system == True, DashboardTab.priority == 0).first()
        if not default_tab:
            import json
            db.add(DashboardTab(
                name="总览",
                priority=0,
                is_system=True,
                chart_type="line",
                metrics_config=json.dumps([
                    {"key": "exposure_entry_rate", "label": "曝光进入率", "type": "computed", "formula": "cumulative_viewers/exposure_count"},
                    {"key": "lead_conversion_rate", "label": "留资率", "type": "computed", "formula": "total_leads/cumulative_viewers"},
                    {"key": "avg_watch_duration", "label": "人均观看时长", "type": "field"}
                ], ensure_ascii=False)
            ))

        # 迁移：api_clues表添加扩展字段
        for col_name, col_type in [
            ("session_id", "INTEGER REFERENCES sessions(id)"),
            ("weixin_manual", "TEXT"),
            ("anchor_names", "TEXT"),
            ("phone_masked", "TEXT"),
            ("nickname", "TEXT"),
            ("lead_time", "TEXT"),
            ("clue_source", "TEXT DEFAULT 'api'"),
        ]:
            try:
                with engine.connect() as conn:
                    conn.execute(text(f"ALTER TABLE api_clues ADD COLUMN {col_name} {col_type}"))
                    conn.commit()
            except Exception:
                pass

        # 迁移：recruit_teams表添加push_enabled、assign_mode、assignee_id列
        try:
            with engine.connect() as conn:
                result = conn.execute(text("PRAGMA table_info(recruit_teams)"))
                columns = [row[1] for row in result]
                if 'push_enabled' not in columns:
                    conn.execute(text("ALTER TABLE recruit_teams ADD COLUMN push_enabled BOOLEAN DEFAULT 1"))
                    conn.commit()
                if 'assign_mode' not in columns:
                    conn.execute(text("ALTER TABLE recruit_teams ADD COLUMN assign_mode TEXT DEFAULT 'round_robin'"))
                    conn.commit()
                if 'assignee_id' not in columns:
                    conn.execute(text("ALTER TABLE recruit_teams ADD COLUMN assignee_id INTEGER REFERENCES recruit_employees(id)"))
                    conn.commit()
        except Exception:
            pass

        # 初始化默认招生团队（社招部，密码hd1994）
        default_team = db.query(RecruitTeam).filter(RecruitTeam.name == "社招部").first()
        if not default_team:
            db.add(RecruitTeam(
                name="社招部",
                password="hd1994",
                require_password=False,
                is_active=True,
            ))

        # 迁移：anchors表添加is_parttime列
        try:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE anchors ADD COLUMN is_parttime INTEGER DEFAULT 0"))
                conn.commit()
        except Exception:
            pass

        # 迁移：session_anchors表添加on_time、off_time、anchor_order列
        for col_name, col_type in [
            ("on_time", "TEXT"),
            ("off_time", "TEXT"),
            ("anchor_order", "INTEGER"),
        ]:
            try:
                with engine.connect() as conn:
                    conn.execute(text(f"ALTER TABLE session_anchors ADD COLUMN {col_name} {col_type}"))
                    conn.commit()
            except Exception:
                pass

        # 迁移：sessions表添加room_id和comment_summary列
        for col_name, col_type in [
            ("room_id", "TEXT"),
            ("comment_summary", "TEXT"),
        ]:
            try:
                with engine.connect() as conn:
                    conn.execute(text(f"ALTER TABLE sessions ADD COLUMN {col_name} {col_type}"))
                    conn.commit()
            except Exception:
                pass

        # 迁移：comments表添加唯一约束索引
        try:
            with engine.connect() as conn:
                conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS idx_comments_unique ON comments(session_id, nickname, comment_time)"))
                conn.commit()
        except Exception:
            pass

        # 迁移：clue_configs表poll_interval_minutes重命名为poll_interval_seconds
        try:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE clue_configs RENAME COLUMN poll_interval_minutes TO poll_interval_seconds"))
                conn.commit()
        except Exception:
            pass

        # 迁移：session_anchors唯一约束从(session_id,anchor_id)改为(session_id,anchor_id,anchor_order)
        try:
            with engine.connect() as conn:
                # 检查当前约束是否包含anchor_order
                result = conn.execute(text("SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='session_anchors'"))
                indexes = [row[0] for row in result.fetchall() if row[0]]
                needs_migration = True
                for idx_sql in indexes:
                    if 'anchor_order' in idx_sql:
                        needs_migration = False
                        break
                if needs_migration:
                    conn.execute(text("ALTER TABLE session_anchors RENAME TO session_anchors_old"))
                    conn.execute(text("""CREATE TABLE session_anchors (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id INTEGER NOT NULL REFERENCES sessions(id),
                        anchor_id INTEGER NOT NULL REFERENCES anchors(id),
                        on_time TEXT,
                        off_time TEXT,
                        anchor_order INTEGER,
                        UNIQUE(session_id, anchor_id, anchor_order)
                    )"""))
                    conn.execute(text("INSERT INTO session_anchors (id, session_id, anchor_id, on_time, off_time, anchor_order) SELECT id, session_id, anchor_id, on_time, off_time, anchor_order FROM session_anchors_old"))
                    conn.execute(text("DROP TABLE session_anchors_old"))
                    conn.commit()
        except Exception:
            pass

        # 迁移：comments表添加is_consultation列
        try:
            with engine.connect() as conn:
                result = conn.execute(text("PRAGMA table_info(comments)"))
                columns = [row[1] for row in result]
                if 'is_consultation' not in columns:
                    conn.execute(text("ALTER TABLE comments ADD COLUMN is_consultation BOOLEAN DEFAULT 1"))
                    conn.commit()
        except Exception:
            pass

        # 迁移：clue_configs表添加缺失列
        try:
            with engine.connect() as conn:
                result = conn.execute(text("PRAGMA table_info(clue_configs)"))
                columns = [row[1] for row in result]
                if 'ad_account_id' not in columns:
                    conn.execute(text("ALTER TABLE clue_configs ADD COLUMN ad_account_id INTEGER REFERENCES ad_accounts(id)"))
                    conn.commit()
                if 'push_enabled' not in columns:
                    conn.execute(text("ALTER TABLE clue_configs ADD COLUMN push_enabled BOOLEAN DEFAULT 1"))
                    conn.commit()
                if 'push_time_range_days' not in columns:
                    conn.execute(text("ALTER TABLE clue_configs ADD COLUMN push_time_range_days INTEGER DEFAULT 1"))
                    conn.commit()
        except Exception:
            pass

        # 迁移：ad_accounts表添加merchant_id列
        try:
            with engine.connect() as conn:
                result = conn.execute(text("PRAGMA table_info(ad_accounts)"))
                columns = [row[1] for row in result]
                if 'merchant_id' not in columns:
                    conn.execute(text("ALTER TABLE ad_accounts ADD COLUMN merchant_id TEXT"))
                    conn.commit()
        except Exception:
            pass

        # 迁移：deals表添加team_id和employee_id列
        try:
            with engine.connect() as conn:
                result = conn.execute(text("PRAGMA table_info(deals)"))
                columns = [row[1] for row in result]
                if 'team_id' not in columns:
                    conn.execute(text("ALTER TABLE deals ADD COLUMN team_id INTEGER REFERENCES recruit_teams(id)"))
                    conn.commit()
                if 'employee_id' not in columns:
                    conn.execute(text("ALTER TABLE deals ADD COLUMN employee_id INTEGER REFERENCES recruit_employees(id)"))
                    conn.commit()
        except Exception:
            pass

        # 迁移：leads表添加anchor_id列
        try:
            with engine.connect() as conn:
                result = conn.execute(text("PRAGMA table_info(leads)"))
                columns = [row[1] for row in result]
                if 'anchor_id' not in columns:
                    conn.execute(text("ALTER TABLE leads ADD COLUMN anchor_id INTEGER REFERENCES anchors(id)"))
                    conn.commit()
        except Exception:
            pass

        # 迁移：schedule_bindings 表添加 recruit_team_id 列
        try:
            with engine.connect() as conn:
                result = conn.execute(text("PRAGMA table_info(schedule_bindings)"))
                columns = [row[1] for row in result]
                if 'recruit_team_id' not in columns:
                    conn.execute(text("ALTER TABLE schedule_bindings ADD COLUMN recruit_team_id INTEGER REFERENCES recruit_teams(id)"))
                    conn.commit()
        except Exception:
            pass

        # 迁移：创建多维数据导入相关表
        try:
            from models import MultiDimRecord, MultiDimImportBatch, MultiDimImportSkip
            # SQLAlchemy create_all 会自动创建不存在的表
            Base.metadata.create_all(bind=engine)
            # 创建缺失的列（ALTER TABLE 安全迁移）
            for table_name, col_name, col_type in [
                ("multidim_records", "dedup_key", "TEXT"),
                ("multidim_records", "contact_norm", "TEXT"),
                ("multidim_records", "wechat", "TEXT"),
                ("multidim_records", "synced_to_lead", "INTEGER DEFAULT 0"),
            ]:
                try:
                    with engine.connect() as conn:
                        result = conn.execute(text(f"PRAGMA table_info({table_name})"))
                        columns = [row[1] for row in result]
                        if col_name not in columns:
                            conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}"))
                            conn.commit()
                except Exception:
                    pass
        except Exception:
            pass

        # 迁移：排班方案增加运营人数
        try:
            with engine.connect() as conn:
                result = conn.execute(text("PRAGMA table_info(schedule_plans)"))
                columns = [row[1] for row in result]
                if "operator_count" not in columns:
                    conn.execute(text("ALTER TABLE schedule_plans ADD COLUMN operator_count INTEGER DEFAULT 1"))
                    conn.commit()
        except Exception:
            pass

        # 迁移：排班绑定增加运营人员映射
        try:
            with engine.connect() as conn:
                result = conn.execute(text("PRAGMA table_info(schedule_bindings)"))
                columns = [row[1] for row in result]
                if "staff_mapping" not in columns:
                    conn.execute(text("ALTER TABLE schedule_bindings ADD COLUMN staff_mapping TEXT DEFAULT '{}'"))
                    conn.commit()
        except Exception:
            pass

        # 迁移：schedule_days 增加直播计划字段
        for col_name, col_type in [
            ("plan_id", "INTEGER"),
            ("status", "TEXT DEFAULT 'draft'"),
            ("source", "TEXT DEFAULT 'manual'"),
            ("updated_at", "TEXT"),
            ("updated_by", "TEXT"),
        ]:
            try:
                with engine.connect() as conn:
                    result = conn.execute(text("PRAGMA table_info(schedule_days)"))
                    columns = [row[1] for row in result]
                    if col_name not in columns:
                        conn.execute(text(f"ALTER TABLE schedule_days ADD COLUMN {col_name} {col_type}"))
                        conn.commit()
            except Exception:
                pass

        # 迁移：sessions 表增加新字段（第二直播间支持）
        for col_name, col_type in [
            ("ad_account_id", "INTEGER"),
            ("room_index", "INTEGER"),
            ("external_session_id", "TEXT"),
            ("schedule_day_id", "INTEGER"),
            ("ingest_updated_at", "TEXT"),
        ]:
            try:
                with engine.connect() as conn:
                    result = conn.execute(text("PRAGMA table_info(sessions)"))
                    columns = [row[1] for row in result]
                    if col_name not in columns:
                        conn.execute(text(f"ALTER TABLE sessions ADD COLUMN {col_name} {col_type}"))
                        conn.commit()
            except Exception:
                pass

        # 迁移：schedule_days 增加 recruit_team_id
        try:
            with engine.connect() as conn:
                result = conn.execute(text("PRAGMA table_info(schedule_days)"))
                columns = [row[1] for row in result]
                if "recruit_team_id" not in columns:
                    conn.execute(text("ALTER TABLE schedule_days ADD COLUMN recruit_team_id INTEGER"))
                    conn.commit()
        except Exception:
            pass

        # 迁移：删除 sessions 旧 start_time 唯一约束，增加 (ad_account_id, start_time) 复合索引
        try:
            with engine.connect() as conn:
                # 检查是否仍有旧的 start_time 唯一索引
                result = conn.execute(text("PRAGMA index_list(sessions)"))
                has_old_unique = any(row[2] == 1 for row in result)  # unique=1
                if has_old_unique:
                    # SQLite 不能直接删除约束，需要重建表
                    conn.execute(text("""
                        CREATE TABLE sessions_new (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            start_time TEXT NOT NULL,
                            end_time TEXT NOT NULL,
                            duration_minutes INTEGER NOT NULL,
                            analyzed BOOLEAN,
                            analyzed_at TEXT,
                            room_id TEXT,
                            ad_account_id INTEGER,
                            room_index INTEGER,
                            external_session_id TEXT,
                            schedule_day_id INTEGER,
                            ingest_updated_at TEXT,
                            comment_summary TEXT,
                            created_at TEXT DEFAULT CURRENT_TIMESTAMP
                        )
                    """))
                    conn.execute(text("""
                        INSERT INTO sessions_new (id, start_time, end_time, duration_minutes, analyzed, analyzed_at, room_id, ad_account_id, room_index, external_session_id, schedule_day_id, ingest_updated_at, comment_summary, created_at)
                        SELECT id, start_time, end_time, duration_minutes, analyzed, analyzed_at, room_id, ad_account_id, room_index, external_session_id, schedule_day_id, ingest_updated_at, comment_summary, created_at FROM sessions
                    """))
                    conn.execute(text("DROP TABLE sessions"))
                    conn.execute(text("ALTER TABLE sessions_new RENAME TO sessions"))
                    conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS idx_sessions_account_time ON sessions(ad_account_id, start_time)"))
                    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_sessions_external_id ON sessions(external_session_id)"))
                    conn.commit()
        except Exception:
            pass

        # 迁移：schedule_slots 增加 operator_slot 字段
        try:
            with engine.connect() as conn:
                result = conn.execute(text("PRAGMA table_info(schedule_slots)"))
                columns = [row[1] for row in result]
                if "operator_slot" not in columns:
                    conn.execute(text("ALTER TABLE schedule_slots ADD COLUMN operator_slot INTEGER"))
                    conn.commit()
        except Exception:
            pass

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


def db_health_check():
    """数据库结构自检，启动时调用"""
    import logging
    logger = logging.getLogger(__name__)
    checks = []
    try:
        with engine.connect() as conn:
            # 检查 sessions 表字段
            result = conn.execute(text("PRAGMA table_info(sessions)"))
            session_cols = {row[1] for row in result}
            required_session_cols = ['ad_account_id', 'room_index', 'external_session_id', 'schedule_day_id', 'ingest_updated_at']
            for col in required_session_cols:
                checks.append(('sessions.' + col, col in session_cols))

            # 检查索引
            result = conn.execute(text("PRAGMA index_list(sessions)"))
            session_idx = {row[1] for row in result}
            checks.append(('idx_sessions_account_time', 'idx_sessions_account_time' in session_idx))
            checks.append(('idx_sessions_external_id', 'idx_sessions_external_id' in session_idx))

            # 检查 schedule_days 字段
            result = conn.execute(text("PRAGMA table_info(schedule_days)"))
            sd_cols = {row[1] for row in result}
            required_sd_cols = ['plan_id', 'recruit_team_id', 'status', 'source', 'updated_at']
            for col in required_sd_cols:
                checks.append(('schedule_days.' + col, col in sd_cols))

            # 检查 schedule_plans 字段
            result = conn.execute(text("PRAGMA table_info(schedule_plans)"))
            sp_cols = {row[1] for row in result}
            checks.append(('schedule_plans.operator_count', 'operator_count' in sp_cols))

            # 检查 schedule_bindings 字段
            result = conn.execute(text("PRAGMA table_info(schedule_bindings)"))
            sb_cols = {row[1] for row in result}
            checks.append(('schedule_bindings.staff_mapping', 'staff_mapping' in sb_cols))

            # 检查 collection_logs 字段
            result = conn.execute(text("PRAGMA table_info(collection_logs)"))
            cl_cols = {row[1] for row in result}
            checks.append(('collection_logs.request_id', 'request_id' in cl_cols))

    except Exception as e:
        logger.error(f"数据库自检失败: {e}")
        return

    # 输出结果
    all_ok = True
    for name, ok in checks:
        status = "OK" if ok else "MISSING"
        if not ok:
            all_ok = False
            logger.warning(f"   [{status}] {name}")
        else:
            logger.info(f"   [{status}] {name}")

    if all_ok:
        logger.info("数据库结构自检全部通过")
    else:
        logger.warning("数据库结构自检存在缺失项，请检查迁移是否完整")
