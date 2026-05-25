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
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
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
    content = Column(Text)
    comment_time = Column(Text)
    created_at = Column(Text, server_default="CURRENT_TIMESTAMP")
    
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
    created_at = Column(Text, server_default="CURRENT_TIMESTAMP")
    
    sessions = relationship("SessionAnchor", back_populates="anchor")

class SessionAnchor(Base):
    __tablename__ = "session_anchors"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    anchor_id = Column(Integer, ForeignKey("anchors.id"), nullable=False)
    __table_args__ = (UniqueConstraint("session_id", "anchor_id"),)
    
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
    notes = Column(Text)
    created_at = Column(Text, server_default="CURRENT_TIMESTAMP")
    
    session = relationship("Session", back_populates="deals")
    lead = relationship("Lead", back_populates="deals")

class Setting(Base):
    __tablename__ = "settings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(Text, nullable=False, unique=True)
    value = Column(Text, nullable=False)
    updated_at = Column(Text, server_default="CURRENT_TIMESTAMP")
