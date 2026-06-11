from sqlalchemy import Column, Integer, Text, Boolean, Float, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import relationship
from database import Base

class Session(Base):
    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    start_time = Column(Text, nullable=False, unique=True)
    end_time = Column(Text, nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    analyzed = Column(Boolean, default=False)
    analyzed_at = Column(Text, nullable=True)
    room_id = Column(Text, nullable=True)
    comment_summary = Column(Text, nullable=True)
    created_at = Column(Text, server_default="CURRENT_TIMESTAMP")
    
    metrics = relationship("SessionMetric", back_populates="session", uselist=False)
    leads = relationship("Lead", back_populates="session")
    comments = relationship("Comment", back_populates="session")
    high_intent_users = relationship("HighIntentUser", back_populates="session")
    private_messages = relationship("PrivateMessage", back_populates="session")
    anchors = relationship("SessionAnchor", back_populates="session")
    reports = relationship("Report", back_populates="session")
    deals = relationship("Deal", back_populates="session")

class SessionMetric(Base):
    __tablename__ = "session_metrics"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    
    exposure_count = Column(Integer, default=0)
    cumulative_viewers = Column(Integer, default=0)
    exposure_entry_rate = Column(Text)
    gmv = Column(Float, default=0)
    order_count = Column(Integer, default=0)
    marketing_orders = Column(Integer, default=0)
    phone_submits = Column(Integer, default=0)
    ad_spend = Column(Float, default=0)
    total_leads = Column(Integer, default=0)
    order_cost = Column(Float, default=0)
    lead_cost = Column(Float, default=0)
    new_followers = Column(Integer, default=0)
    comment_count = Column(Integer, default=0)
    comment_users = Column(Integer, default=0)
    watch_gt_1min = Column(Integer, default=0)
    avg_watch_duration = Column(Text)
    fan_stay_duration = Column(Text)
    max_online = Column(Integer, default=0)
    interaction_count = Column(Integer, default=0)
    interaction_users = Column(Integer, default=0)
    interaction_rate = Column(Text)
    fan_club_joins = Column(Integer, default=0)
    fan_club_rate = Column(Text)
    component_clicks = Column(Integer, default=0)
    click_rate = Column(Text)
    gift_amount = Column(Float, default=0)
    gift_count = Column(Integer, default=0)
    comment_rate = Column(Text)
    lead_conversion_rate = Column(Text)
    like_rate = Column(Text)
    like_users = Column(Integer, default=0)
    like_count = Column(Integer, default=0)
    product_exposure = Column(Integer, default=0)
    product_clicks = Column(Integer, default=0)
    product_click_rate = Column(Text)
    follow_rate = Column(Text)
    share_count = Column(Integer, default=0)
    share_users = Column(Integer, default=0)
    share_rate = Column(Text)
    gmv_per_mille = Column(Float, default=0)
    fan_ratio = Column(Text)
    exposure_times = Column(Text)
    view_count = Column(Integer, default=0)
    avg_online = Column(Float, default=0)
    realtime_online = Column(Integer, default=0)
    created_at = Column(Text, server_default="CURRENT_TIMESTAMP")
    
    session = relationship("Session", back_populates="metrics")

class Lead(Base):
    __tablename__ = "leads"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=True)
    lead_time = Column(Text, nullable=False)
    nickname = Column(Text, nullable=False)
    lead_id = Column(Text)
    phone_masked = Column(Text)
    product_name = Column(Text)
    city = Column(Text)
    path = Column(Text)
    tags = Column(Text)
    ad_account = Column(Text)
    is_valid = Column(Boolean, default=None)
    is_deal = Column(Boolean, default=False)
    source = Column(Text, nullable=True)  # 线索来源: api, manual, natural
    assigned_employee = Column(Text, nullable=True)
    created_at = Column(Text, server_default="CURRENT_TIMESTAMP")
    
    session = relationship("Session", back_populates="leads")
    deals = relationship("Deal", back_populates="lead")

class Comment(Base):
    __tablename__ = "comments"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    nickname = Column(Text, nullable=False)
    has_lead = Column(Boolean, default=False)
    is_consultation = Column(Boolean, default=True)  # 是否为咨询相关评论，默认True
    content = Column(Text)
    comment_time = Column(Text)
    created_at = Column(Text, server_default="CURRENT_TIMESTAMP")
    __table_args__ = (UniqueConstraint("session_id", "nickname", "comment_time"),)
    
    session = relationship("Session", back_populates="comments")

class HighIntentUser(Base):
    __tablename__ = "high_intent_users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    nickname = Column(Text, nullable=False)
    avatar_url = Column(Text)
    comment_count = Column(Integer, default=0)
    stay_duration = Column(Text)
    status = Column(Text)
    created_at = Column(Text, server_default="CURRENT_TIMESTAMP")
    
    session = relationship("Session", back_populates="high_intent_users")

class PrivateMessage(Base):
    __tablename__ = "private_messages"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    nickname = Column(Text, nullable=False)
    douyin_id = Column(Text)
    has_lead = Column(Boolean, default=False)
    last_message_time = Column(Text)
    last_reply_time = Column(Text)
    pending_reply = Column(Text)
    message_count = Column(Integer, default=0)
    ai_reply_count = Column(Integer, default=0)
    created_at = Column(Text, server_default="CURRENT_TIMESTAMP")
    
    session = relationship("Session", back_populates="private_messages")

class Report(Base):
    __tablename__ = "reports"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=True)
    report_type = Column(Text, nullable=False)
    period = Column(Text, nullable=False)
    content = Column(Text)
    generated_at = Column(Text, server_default="CURRENT_TIMESTAMP")
    
    session = relationship("Session", back_populates="reports")

class Anchor(Base):
    __tablename__ = "anchors"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False, unique=True)
    gender = Column(Text, nullable=True)
    style = Column(Text, nullable=True)
    is_parttime = Column(Integer, default=0)  # 兼职标记：0=全职，1=兼职
    created_at = Column(Text, server_default="CURRENT_TIMESTAMP")

    sessions = relationship("SessionAnchor", back_populates="anchor")

class SessionAnchor(Base):
    __tablename__ = "session_anchors"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    anchor_id = Column(Integer, ForeignKey("anchors.id"), nullable=False)
    on_time = Column(Text, nullable=True)   # 上播时间 "08:00"
    off_time = Column(Text, nullable=True)  # 下播时间 "10:00"
    anchor_order = Column(Integer, nullable=True)  # 主播场次顺序
    __table_args__ = (UniqueConstraint("session_id", "anchor_id", "anchor_order"),)
    
    session = relationship("Session", back_populates="anchors")
    anchor = relationship("Anchor", back_populates="sessions")

class Deal(Base):
    __tablename__ = "deals"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=True)
    customer_name = Column(Text, nullable=False)
    amount = Column(Float, nullable=False)
    deal_time = Column(Text, nullable=False)
    employee = Column(Text)
    team_id = Column(Integer, ForeignKey("recruit_teams.id"), nullable=True)
    employee_id = Column(Integer, ForeignKey("recruit_employees.id"), nullable=True)
    notes = Column(Text)
    created_at = Column(Text, server_default="CURRENT_TIMESTAMP")

    session = relationship("Session", back_populates="deals")
    lead = relationship("Lead", back_populates="deals")
    team = relationship("RecruitTeam")
    deal_employee = relationship("RecruitEmployee")

class Setting(Base):
    __tablename__ = "settings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(Text, nullable=False, unique=True)
    value = Column(Text, nullable=False)
    updated_at = Column(Text, server_default="CURRENT_TIMESTAMP")

class SchedulePlan(Base):
    __tablename__ = "schedule_plans"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)
    start_time = Column(Text, nullable=False)
    end_time = Column(Text, nullable=False)
    time_granularity = Column(Integer, default=60)
    room_count = Column(Integer, default=2)
    anchor_count = Column(Integer, default=5)
    is_active = Column(Boolean, default=True)
    notes = Column(Text, nullable=True)
    created_at = Column(Text, server_default="CURRENT_TIMESTAMP")

    slots = relationship("ScheduleSlot", back_populates="plan", cascade="all, delete-orphan")
    bindings = relationship("ScheduleBinding", back_populates="plan")

class ScheduleSlot(Base):
    __tablename__ = "schedule_slots"
    id = Column(Integer, primary_key=True, autoincrement=True)
    plan_id = Column(Integer, ForeignKey("schedule_plans.id"), nullable=False)
    time_slot = Column(Text, nullable=False)
    room_index = Column(Integer, nullable=False)
    slot_status = Column(Text, nullable=False, default="on_air_anchor")
    anchor_slot = Column(Integer, nullable=True)
    created_at = Column(Text, server_default="CURRENT_TIMESTAMP")

    plan = relationship("SchedulePlan", back_populates="slots")

class ScheduleBinding(Base):
    __tablename__ = "schedule_bindings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Text, nullable=False, unique=True)
    plan_id = Column(Integer, ForeignKey("schedule_plans.id"), nullable=False)
    anchor_mapping = Column(Text, nullable=False, default="{}")
    created_at = Column(Text, server_default="CURRENT_TIMESTAMP")

    plan = relationship("SchedulePlan", back_populates="bindings")

class AdAccount(Base):
    """直播账户"""
    __tablename__ = "ad_accounts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    account_name = Column(Text, nullable=False)
    merchant_id = Column(Text, nullable=True, comment="抖音来客商家ID（API线索用）")
    account_id = Column(Text, nullable=True, unique=True, comment="旧字段，兼容用")
    notes = Column(Text, nullable=True)
    created_at = Column(Text, server_default="CURRENT_TIMESTAMP")

class RoomAccountBinding(Base):
    __tablename__ = "room_account_bindings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Text, nullable=False)
    room_index = Column(Integer, nullable=False)
    ad_account_id = Column(Integer, ForeignKey("ad_accounts.id"), nullable=False)
    created_at = Column(Text, server_default="CURRENT_TIMESTAMP")
    __table_args__ = (UniqueConstraint("date", "room_index"),)

    ad_account = relationship("AdAccount")


class AdPlan(Base):
    """投流计划"""
    __tablename__ = "ad_plans"
    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("ad_accounts.id"), nullable=False)
    plan_name = Column(Text, nullable=False)
    plan_id = Column(Text, nullable=True)
    bid_price = Column(Float, nullable=True)
    status = Column(Text, default="active")
    start_date = Column(Text, nullable=True)
    end_date = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(Text, server_default="CURRENT_TIMESTAMP")

    account = relationship("AdAccount", backref="plans")
    spend_records = relationship("AdPlanSpend", back_populates="plan", cascade="all, delete-orphan")


class AdPlanSpend(Base):
    """投流花费记录"""
    __tablename__ = "ad_plan_spends"
    id = Column(Integer, primary_key=True, autoincrement=True)
    plan_id = Column(Integer, ForeignKey("ad_plans.id"), nullable=False)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=True)
    spend_amount = Column(Float, default=0)
    result_count = Column(Integer, default=0)
    record_date = Column(Text, nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(Text, server_default="CURRENT_TIMESTAMP")

    plan = relationship("AdPlan", back_populates="spend_records")
    session = relationship("Session")


class ApiClue(Base):
    """抖音开放平台API线索表（统一线索主表）"""
    __tablename__ = "api_clues"
    id = Column(Integer, primary_key=True, autoincrement=True)
    clue_id = Column(Text, nullable=False, unique=True)
    account_id = Column(Text, nullable=True)
    enc_telephone = Column(Text, nullable=True)
    phone_decrypted = Column(Text, nullable=True)
    is_decrypted = Column(Boolean, default=False)
    name = Column(Text, nullable=True)
    create_time_detail = Column(Text, nullable=True)
    modify_time = Column(Text, nullable=True)
    author_nickname = Column(Text, nullable=True)
    author_douyin_id = Column(Text, nullable=True)
    author_role = Column(Text, nullable=True)
    advertiser_id = Column(Text, nullable=True)
    advertiser_name = Column(Text, nullable=True)
    ad_type = Column(Text, nullable=True)
    promotion_id = Column(Text, nullable=True)
    promotion_name = Column(Text, nullable=True)
    product_id = Column(Text, nullable=True)
    product_name = Column(Text, nullable=True)
    product_type = Column(Text, nullable=True)
    content_id = Column(Text, nullable=True)
    video_id = Column(Text, nullable=True)
    flow_entrance = Column(Text, nullable=True)
    flow_type = Column(Text, nullable=True)
    leads_page = Column(Text, nullable=True)
    clue_type = Column(Text, nullable=True)
    clue_intention = Column(Text, nullable=True)
    convert_status = Column(Text, nullable=True)
    allocation_status = Column(Text, nullable=True)
    effective_state = Column(Text, nullable=True)
    is_private_clue = Column(Integer, default=0)
    auto_city_name = Column(Text, nullable=True)
    auto_province_name = Column(Text, nullable=True)
    province_name = Column(Text, nullable=True)
    city_name = Column(Text, nullable=True)
    county_name = Column(Text, nullable=True)
    tel_addr = Column(Text, nullable=True)
    ad_id = Column(Text, nullable=True)
    search_bid_word = Column(Text, nullable=True)
    gender = Column(Text, nullable=True)
    age = Column(Text, nullable=True)
    weixin = Column(Text, nullable=True)
    tags = Column(Text, nullable=True)
    system_tags = Column(Text, nullable=True)
    ext_info = Column(Text, nullable=True)
    anchor_id = Column(Integer, nullable=True)
    raw_data = Column(Text, nullable=True)
    # 扩展字段：油猴脚本匹配后关联
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=True)
    # 扩展字段：管理员手动补充的微信
    weixin_manual = Column(Text, nullable=True)
    # 扩展字段：关联主播名(逗号隔开)
    anchor_names = Column(Text, nullable=True)
    # 油猴脚本采集的加密手机号(用于匹配)
    phone_masked = Column(Text, nullable=True)
    # 油猴脚本采集的昵称
    nickname = Column(Text, nullable=True)
    # 油猴脚本采集的留资时间
    lead_time = Column(Text, nullable=True)
    # 线索来源：api=抖音API同步, tm=油猴脚本采集, manual=手动添加, excel=Excel导入
    clue_source = Column(Text, default="api")
    created_at = Column(Text, server_default="CURRENT_TIMESTAMP")

    session = relationship("Session", backref="api_clues")
    assignment = relationship("ClueAssignment", back_populates="clue", uselist=False)


class ClueConfig(Base):
    """抖音API线索账号配置表"""
    __tablename__ = "clue_configs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    account_name = Column(Text, nullable=False)
    ad_account_id = Column(Integer, ForeignKey("ad_accounts.id"), nullable=True, comment="关联直播账户")
    account_id = Column(Text, nullable=True, unique=True, comment="抖音来客商家ID（旧字段）")
    client_key = Column(Text, nullable=False)
    client_secret = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    poll_interval_seconds = Column(Integer, default=30)
    decrypt_enabled = Column(Boolean, default=True)
    push_enabled = Column(Boolean, default=True, comment="线索推送开关：是否自动分配并推送钉钉")
    push_time_range_days = Column(Integer, default=1, comment="推送时间区间（天）：只推送N天内的线索")
    notes = Column(Text, nullable=True)
    created_at = Column(Text, server_default="CURRENT_TIMESTAMP")

    ad_account = relationship("AdAccount")


class PollLog(Base):
    """线索API采集日志"""
    __tablename__ = "poll_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    account_name = Column(Text, nullable=True)
    account_id = Column(Text, nullable=True)
    status = Column(Text, nullable=False)  # success/error
    new_count = Column(Integer, default=0)
    decrypt_count = Column(Integer, default=0)
    total_count = Column(Integer, default=0)
    message = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    triggered_by = Column(Text, default="scheduler")  # scheduler/manual
    created_at = Column(Text, server_default="CURRENT_TIMESTAMP")


class DashboardTab(Base):
    """首页看板报表Tab配置表"""
    __tablename__ = "dashboard_tabs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)
    priority = Column(Integer, default=0)
    is_system = Column(Boolean, default=False)
    chart_type = Column(Text, default="line")
    metrics_config = Column(Text, nullable=False, default="[]")
    system_prompt = Column(Text, nullable=True)
    user_prompt = Column(Text, nullable=True)
    created_at = Column(Text, server_default="CURRENT_TIMESTAMP")


class TabAnalysis(Base):
    """报表Tab AI分析缓存表"""
    __tablename__ = "tab_analyses"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tab_id = Column(Integer, ForeignKey("dashboard_tabs.id"), nullable=False)
    range_type = Column(Text, nullable=False)
    range_value = Column(Text, nullable=False)
    session_id = Column(Integer, nullable=True)
    content = Column(Text, nullable=True)
    created_at = Column(Text, server_default="CURRENT_TIMESTAMP")
    __table_args__ = (UniqueConstraint("tab_id", "range_type", "range_value", "session_id"),)


class RecruitTeam(Base):
    """招生团队"""
    __tablename__ = "recruit_teams"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False, unique=True)
    password = Column(Text, nullable=True)
    require_password = Column(Boolean, default=False)
    dingtalk_webhook = Column(Text, nullable=True)
    dingtalk_secret = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    push_enabled = Column(Boolean, default=True, comment="线索推送开关：该团队是否接收线索分配和钉钉推送")
    assign_mode = Column(Text, default="round_robin", comment="分配模式: single=单人分配 all_to_one, round_robin=轮流分配")
    assignee_id = Column(Integer, ForeignKey("recruit_employees.id"), nullable=True, comment="单人模式下指定接收线索的员工")
    created_at = Column(Text, server_default="CURRENT_TIMESTAMP")

    employees = relationship("RecruitEmployee", back_populates="team", cascade="all, delete-orphan")
    assignments = relationship("ClueAssignment", back_populates="team")


class RecruitEmployee(Base):
    """招生员工"""
    __tablename__ = "recruit_employees"
    id = Column(Integer, primary_key=True, autoincrement=True)
    team_id = Column(Integer, ForeignKey("recruit_teams.id"), nullable=False)
    name = Column(Text, nullable=False)
    phone = Column(Text, nullable=True)
    dingtalk_phone = Column(Text, nullable=True)
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(Text, server_default="CURRENT_TIMESTAMP")

    team = relationship("RecruitTeam", back_populates="employees")


class ClueAssignment(Base):
    """线索分配记录"""
    __tablename__ = "clue_assignments"
    id = Column(Integer, primary_key=True, autoincrement=True)
    clue_id = Column(Integer, ForeignKey("api_clues.id"), nullable=False, unique=True)
    team_id = Column(Integer, ForeignKey("recruit_teams.id"), nullable=False)
    employee_id = Column(Integer, ForeignKey("recruit_employees.id"), nullable=False)
    assigned_at = Column(Text, nullable=False)
    claimed_at = Column(Text, nullable=True)
    status = Column(Text, nullable=False, default="unclaimed")  # unclaimed/following/deal/invalid
    feedback = Column(Text, nullable=True)
    remark = Column(Text, nullable=True)
    created_at = Column(Text, server_default="CURRENT_TIMESTAMP")

    clue = relationship("ApiClue", back_populates="assignment")
    team = relationship("RecruitTeam", back_populates="assignments")
    employee = relationship("RecruitEmployee")
