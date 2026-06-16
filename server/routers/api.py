from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session as DBSession
from sqlalchemy import Integer as SAInt, Float as SAFloat, func, or_
from database import get_db
from models import Session, SessionMetric, Lead, Comment, HighIntentUser, PrivateMessage, Report, Anchor, SessionAnchor, Deal, Setting, SchedulePlan, ScheduleSlot, ScheduleBinding, AdAccount, RoomAccountBinding, DashboardTab, TabAnalysis, ApiClue
from utils import parse_number, parse_time, format_duration, format_duration_hms, extract_hhmm
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
import io, json, re, logging
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)
from openpyxl import Workbook

router = APIRouter()

# ===== 告警频率限制（内存级别，进程重启重置） =====
_alert_last_sent = {}
ALERT_COOLDOWN_SECONDS = 600

# ===== Pydantic Models =====
class LeadItem(BaseModel):
    lead_time: str; nickname: str; lead_id: Optional[str] = None; phone_masked: Optional[str] = None
    product_name: Optional[str] = None; city: Optional[str] = None; path: Optional[str] = None
    tags: Optional[str] = None; ad_account: Optional[str] = None

class CommentItem(BaseModel):
    nickname: str; has_lead: bool = False; content: Optional[str] = None; comment_time: Optional[str] = None

class CommentInsightItem(BaseModel):
    nickname: str
    has_lead: bool = False
    content: Optional[str] = None
    comment_time: Optional[str] = None

class CommentInsightData(BaseModel):
    room_id: Optional[str] = None
    session_start: str
    session_end: str
    summary: Optional[str] = None
    comments: List[CommentInsightItem] = []
    anchor_stats: Optional[list] = None

class HighIntentItem(BaseModel):
    nickname: str; avatar_url: Optional[str] = None; comment_count: int = 0; stay_duration: Optional[str] = None; status: Optional[str] = None

class SessionData(BaseModel):
    version: str = "1.0"
    account_id: Optional[str] = None
    start_time: str; end_time: str; metrics: dict; leads: List[LeadItem] = []
    comments: List[CommentItem] = []; high_intent_users: List[HighIntentItem] = []
    review: Optional[dict] = None
    private_messages: Optional[list] = None

SUPPORTED_VERSIONS = ["1.0"]


def _match_lead_to_api_clue(session_id: int, lead_data: dict, session_start: str, db):
    """油猴脚本提交线索时，通过手机号后4位+日期匹配ApiClue表，匹配到则补充session_id等字段"""
    try:
        from models import ApiClue, SessionAnchor, Anchor
        phone_masked = lead_data.get("phone_masked", "")
        if not phone_masked or len(phone_masked) < 4:
            return
        suffix = phone_masked[-4:]
        session_date = session_start[:10] if session_start else None
        if not session_date:
            return
        # BUG-D：优先通过 phone_masked 完整匹配（非仅后4位），避免假阳性
        candidates = db.query(ApiClue).filter(
            ApiClue.phone_masked == phone_masked,
            ApiClue.create_time_detail.like(f"{session_date}%"),
        ).all()
        if not candidates:
            # 降级：通过 phone_decrypted 后4位 + 日期匹配
            candidates = db.query(ApiClue).filter(
                ApiClue.phone_decrypted.like(f"%{suffix}"),
                ApiClue.session_id == None,
                ApiClue.create_time_detail.like(f"{session_date}%"),
            ).all()
        for clue in candidates:
            clue_date = clue.create_time_detail[:10] if clue.create_time_detail else None
            if clue_date == session_date:
                clue.session_id = session_id
                clue.phone_masked = phone_masked
                clue.nickname = lead_data.get("nickname")
                clue.lead_time = lead_data.get("lead_time")
                if not clue.anchor_names and clue.anchor_id:
                    anchor = db.query(Anchor).get(clue.anchor_id)
                    if anchor:
                        clue.anchor_names = anchor.name
                db.flush()
                return
        # BUG-C：创建 tm_ 桥接记录前，检查是否已有真实API线索（clue_source='api'）对应同手机号
        existing_real = db.query(ApiClue).filter(
            ApiClue.clue_source == 'api',
            ApiClue.session_id == None,
            ApiClue.phone_masked == phone_masked,
            ApiClue.create_time_detail.like(f"{session_date}%"),
        ).first()
        if existing_real:
            # 已有真实API线索，直接关联（不自创建tm_副本）
            existing_real.session_id = session_id
            existing_real.phone_masked = phone_masked
            existing_real.nickname = lead_data.get("nickname")
            existing_real.lead_time = lead_data.get("lead_time")
            db.flush()
            return
        clue_id = f"tm_{session_date}_{suffix}_{lead_data.get('nickname', 'unknown')}"
        existing = db.query(ApiClue).filter(ApiClue.clue_id == clue_id).first()
        if not existing:
            # 尝试匹配主播
            anchor_id = None
            anchor_names = None
            create_time_detail = None
            lead_time_str = lead_data.get("lead_time")
            if lead_time_str:
                try:
                    create_time_detail = f"2026-{lead_time_str}:00"
                    from services.clue_service import match_anchor
                    anchor_ids = match_anchor(create_time_detail, db)
                    if anchor_ids:
                        anchor_id = anchor_ids[0]
                        anchor_objs = db.query(Anchor).filter(Anchor.id.in_(anchor_ids)).all()
                        anchor_names = ",".join([a.name for a in anchor_objs])
                except Exception:
                    pass
            new_clue = ApiClue(
                clue_id=clue_id, session_id=session_id, phone_masked=phone_masked,
                nickname=lead_data.get("nickname"), lead_time=lead_time_str,
                city_name=lead_data.get("city"), product_name=lead_data.get("product_name"),
                tags=lead_data.get("tags"),
                is_decrypted=False, clue_source="tm",
                create_time_detail=create_time_detail,
                anchor_id=anchor_id, anchor_names=anchor_names,
            )
            db.add(new_clue)
    except Exception as e:
        logger.warning(f"线索匹配ApiClue失败(不影响主流程): {e}")

# ===== 数据接收API =====
@router.get("/session/check")
def check_session(start_time: str, db: DBSession = Depends(get_db)):
    parsed_time = parse_time(start_time)
    existing = db.query(Session).filter(Session.start_time == parsed_time).first()
    if existing: return {"code": 0, "exists": True, "session_id": existing.id}
    return {"code": 0, "exists": False}

@router.get("/sessions/by-date")
def get_sessions_by_date(date: str = Query(..., description="日期，格式：2026-05-21"), db: DBSession = Depends(get_db)):
    from datetime import datetime as dt, timedelta
    try:
        dt.strptime(date, "%Y-%m-%d")
    except ValueError:
        return {"code": 400, "message": "date参数格式错误，应为YYYY-MM-DD"}
    next_date = (dt.strptime(date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    sessions = db.query(Session.start_time).filter(
        Session.start_time >= f"{date} 00:00:00",
        Session.start_time < f"{next_date} 00:00:00"
    ).order_by(Session.start_time).all()
    starts = [s[0] for s in sessions]
    return {"code": 0, "starts": starts}

@router.post("/session")
def receive_session(data: SessionData, db: DBSession = Depends(get_db)):
    if data.version not in SUPPORTED_VERSIONS:
        return {"code": 400, "message": f"不支持的数据版本: {data.version}，请更新油猴脚本"}
    start = parse_time(data.start_time); end = parse_time(data.end_time)
    existing = db.query(Session).filter(Session.start_time == start).first()
    if existing: return {"code": 400, "message": "场次已存在", "session_id": existing.id}
    try:
        start_dt = datetime.strptime(start, "%Y-%m-%d %H:%M:%S"); end_dt = datetime.strptime(end, "%Y-%m-%d %H:%M:%S")
        duration_minutes = int((end_dt - start_dt).total_seconds() / 60)
    except: raise HTTPException(status_code=400, detail="时间解析失败")
    try:
        session = Session(start_time=start, end_time=end, duration_minutes=duration_minutes); db.add(session); db.flush()
        # 处理油猴脚本传递的account_id，关联到直播间账户绑定
        account_id = getattr(data, 'account_id', None)
        if account_id:
            try:
                account_id = int(account_id)
                binding = db.query(RoomAccountBinding).filter(RoomAccountBinding.account_id == account_id).first()
                if binding:
                    # 更新绑定的session关联（可选：记录该场次属于哪个账户）
                    pass
                # 确保AdAccount存在
                account = db.query(AdAccount).filter(AdAccount.id == account_id).first()
                if account:
                    # 如果没有绑定关系，自动创建
                    if not binding:
                        db.add(RoomAccountBinding(account_id=account_id, room_name=account.account_name or ''))
            except (ValueError, TypeError):
                pass
        valid_columns = {c.name for c in SessionMetric.__table__.columns} - {'id', 'session_id', 'created_at'}
        metrics_data = {}
        for key, value in data.metrics.items():
            if key not in valid_columns: continue
            col_type = SessionMetric.__table__.columns[key].type
            parsed = parse_number(value) if isinstance(value, str) else value
            # 数值异常检测：处理油猴脚本拼接值
            if isinstance(parsed, str) and "%" in parsed and parsed.count("%") > 1:
                for pct in re.findall(r"[\d.]+%", parsed):
                    parsed = pct; break
            elif isinstance(parsed, str) and "%" in parsed and parsed.count(".") > 1:
                # 限位小数提取：取首个1-2位小数百分比（如"0.7280.8782%"→"0.72%"）
                m = re.match(r"(\d+\.\d{1,2})%", parsed)
                if m:
                    parsed = m.group(1) + "%"
                else:
                    parts = parsed.replace("%","").split(".")
                    if len(parts) >= 2 and parts[0] and parts[1]:
                        parsed = parts[0] + "." + parts[1][:2] + "%"
            if isinstance(col_type, SAInt):
                int_val = int(parsed) if isinstance(parsed, (int, float)) else 0
                # 纯整数拼接检测：值异常大时，尝试用对应count字段fallback
                if int_val > 99999:
                    count_fallback_map = {'interaction_users': 'interaction_count', 'exposure_times': 'exposure_count', 'comment_users': 'comment_count', 'like_users': 'like_count', 'share_users': 'share_count'}
                    fallback_key = count_fallback_map.get(key)
                    if fallback_key and fallback_key in metrics_data and metrics_data[fallback_key] > 0:
                        int_val = metrics_data[fallback_key]
                metrics_data[key] = int_val
            elif isinstance(col_type, SAFloat): metrics_data[key] = float(parsed) if isinstance(parsed, (int, float)) else 0.0
            else: metrics_data[key] = str(parsed) if parsed is not None else None
        db.add(SessionMetric(session_id=session.id, **metrics_data))
        # 线索处理：油猴脚本提交时匹配ApiClue表（手机号后4位+日期）
        for ld in data.leads:
            lead_data = ld.model_dump()
            lead_data['source'] = 'tm'
            # 优先从已有 ApiClue 获取 anchor_id（API实时采集已匹配）
            phone_masked = lead_data.get('phone_masked', '')
            if phone_masked and len(phone_masked) >= 4:
                existing_ac = db.query(ApiClue).filter(
                    ApiClue.anchor_id != None,
                    ApiClue.phone_masked == phone_masked,
                    ApiClue.create_time_detail.like(f"{start[:10]}%"),
                ).first()
                if existing_ac:
                    lead_data['anchor_id'] = existing_ac.anchor_id
            # 如果还没 anchor_id，直接按时间匹配主播时段
            if not lead_data.get('anchor_id'):
                lead_time_str = lead_data.get('lead_time')
                if lead_time_str:
                    from services.clue_service import match_anchor
                    create_time_detail = f"2026-{lead_time_str}:00"
                    anchor_ids = match_anchor(create_time_detail, db)
                    if anchor_ids:
                        lead_data['anchor_id'] = anchor_ids[0]
            # 写入Lead表（含anchor_id）
            db.add(Lead(session_id=session.id, **lead_data))
            # 尝试匹配ApiClue表（建立桥梁）
            _match_lead_to_api_clue(session.id, lead_data, start, db)
        for c in data.comments:
            existing = db.query(Comment).filter(
                Comment.session_id == session.id,
                Comment.nickname == c.nickname,
                Comment.comment_time == c.comment_time
            ).first()
            if not existing:
                db.add(Comment(session_id=session.id, **c.model_dump()))
        for h in data.high_intent_users: db.add(HighIntentUser(session_id=session.id, **h.model_dump()))
        if data.private_messages:
            for pm in data.private_messages:
                db.add(PrivateMessage(session_id=session.id, nickname=pm.get('nickname',''), douyin_id=pm.get('douyin_id',''), has_lead=pm.get('has_lead',False), last_message_time=pm.get('last_message_time',''), last_reply_time=pm.get('last_reply_time',''), pending_reply=pm.get('pending_reply',''), message_count=pm.get('message_count',0), ai_reply_count=pm.get('ai_reply_count',0)))
        db.commit()
        # 同步SessionAnchor：新Session入库后自动触发对应日期的排班主播同步
        try:
            date_str = start[:10]
            binding = db.query(ScheduleBinding).filter(ScheduleBinding.date == date_str).first()
            if binding and binding.plan_id:
                plan = db.query(SchedulePlan).filter(SchedulePlan.id == binding.plan_id).first()
                if plan:
                    from services.anchor_stats_service import sync_session_anchors
                    sync_session_anchors(db, date_str, plan, binding.anchor_mapping, binding_id=binding.id)
                    db.commit()
        except Exception as e:
            logger.warning(f"SessionAnchor自动同步失败(date={date_str}): {e}")
        # 数据入库后立即自动AI分析（异步，不阻塞返回）
        try:
            from services.ai_service import analyze_session
            import threading
            def _auto_analyze():
                from database import SessionLocal
                try:
                    db2 = SessionLocal()
                    analyze_session(db2, session.id)
                    date_str = start[:10]
                    _auto_analyze_dashboard(date_str, db2)
                    db2.close()
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).error(f"自动AI分析失败(session_id={session.id}): {e}")
            threading.Thread(target=_auto_analyze, daemon=True).start()
        except Exception:
            pass
        return {"code": 0, "message": "success", "session_id": session.id}
    except HTTPException: raise
    except Exception as e: db.rollback(); raise HTTPException(status_code=500, detail=f"数据库写入失败: {str(e)}")

@router.post("/alert")
def receive_alert(data: dict, db: DBSession = Depends(get_db)):
    alert_type = data.get("type", "未知")
    # 白名单过滤：仅关键类型发送邮件
    CRITICAL_ALERT_TYPES = {'脚本崩溃', '脚本异常'}
    if alert_type not in CRITICAL_ALERT_TYPES:
        logger.info(f"告警已记录（非关键类型，不发送邮件）: {alert_type} - {data.get('message', '')[:80]}")
        return {"code": 0, "message": "告警已记录（非关键类型，不发送邮件）"}
    now = datetime.now()
    # 频率限制：同类型10分钟内只发一次
    last_sent = _alert_last_sent.get(alert_type)
    if last_sent and (now - last_sent).total_seconds() < ALERT_COOLDOWN_SECONDS:
        return {"code": 0, "message": "告警已忽略（10分钟内重复）"}
    _alert_last_sent[alert_type] = now
    # 读取邮箱配置
    settings = db.query(Setting).filter(Setting.key.in_([
        "email_smtp_host", "email_smtp_port", "email_sender",
        "email_password", "email_receivers"
    ])).all()
    config = {s.key: s.value for s in settings}
    if not config.get("email_sender"):
        return {"code": 0, "message": "告警已记录（邮箱未配置）"}
    # 构造HTML邮件
    html = f"""
    <h2>【直播数据告警】{alert_type}</h2>
    <p><strong>告警内容：</strong>{data.get('message', '')}</p>
    <p><strong>场次：</strong>{data.get('session_time', '无')}</p>
    <p><strong>时间：</strong>{data.get('timestamp', '')}</p>
    <hr/>
    <p style="color:#999;font-size:12px">此邮件由系统自动发送</p>
    """
    try:
        from services.email_service import send_email
        receivers = json.loads(config.get("email_receivers", "[]"))
        send_email(
            subject=f"【直播数据告警】{alert_type}",
            html=html,
            config=config,
            receivers=receivers
        )
        return {"code": 0, "message": "告警已发送"}
    except Exception as e:
        return {"code": 0, "message": f"告警记录成功，邮件发送失败: {e}"}

# ===== 前台查询API =====
@router.get("/dashboard")
def dashboard_api(time_range: str = Query("week", alias="range"), date: str = Query(None),
                  session_id: Optional[int] = Query(None), db: DBSession = Depends(get_db)):
    import calendar
    # 单场模式：直接返回该场次数据
    if session_id and time_range == "day":
        s = db.query(Session).get(session_id)
        if not s:
            return {"code": 1, "message": "场次不存在"}
        m = db.query(SessionMetric).filter(SessionMetric.session_id == session_id).first()
        leads = db.query(func.count(Lead.id)).filter(Lead.session_id == session_id).scalar() or 0
        spend = float(m.ad_spend or 0) if m else 0
        # 场均历史对比
        all_leads_count = db.query(func.count(Lead.id)).scalar() or 0
        all_spend_sum = db.query(func.sum(SessionMetric.ad_spend)).scalar() or 0
        all_sessions_count = db.query(Session).count()
        historical_avg = {
            "avg_leads_per_day": round(all_leads_count / max(db.query(func.count(func.distinct(func.substr(Session.start_time, 1, 10)))).scalar() or 1, 1), 1),
            "avg_spend_per_day": round(float(all_spend_sum or 0) / max(db.query(func.count(func.distinct(func.substr(Session.start_time, 1, 10)))).scalar() or 1, 1), 0),
            "avg_lead_cost": round(float(all_spend_sum or 0) / max(all_leads_count, 1), 1),
        }
        return {"code": 0, "data": {
            "current": {"leads": leads, "spend": spend, "lead_cost": round(spend/leads,1) if leads>0 else 0, "sessions": 1},
            "previous": {"leads": 0, "spend": 0, "lead_cost": 0, "sessions": 0},
            "change": {"leads": "——", "spend": "——", "lead_cost": "——", "sessions": "——"},
            "trend": [], "recent_sessions": [], "alerts": [], "funnel": {},
            "historical_avg": historical_avg,
            "period": {"start": s.start_time[:10] if s.start_time else "", "end": s.start_time[:10] if s.start_time else "", "label": s.start_time[:16] if s.start_time else ""}
        }}
    # 解析基准日期（默认今天）
    try:
        base_date = datetime.strptime(date, "%Y-%m-%d").date() if date else datetime.now().date()
    except ValueError:
        base_date = datetime.now().date()

    # 根据模式计算时间窗口
    if time_range == "day":
        period_start = base_date
        period_end = base_date
        period_label = base_date.strftime("%Y-%m-%d")
    elif time_range == "week":
        # 自然周（周一~周日）
        period_start = base_date - timedelta(days=base_date.weekday())
        period_end = period_start + timedelta(days=6)
        period_label = f"{period_start.strftime('%m-%d')} ~ {period_end.strftime('%m-%d')}"
    else:  # month
        period_start = base_date.replace(day=1)
        last_day = calendar.monthrange(base_date.year, base_date.month)[1]
        period_end = base_date.replace(day=last_day)
        period_label = base_date.strftime("%Y-%m")

    cutoff = f"{period_start.strftime('%Y-%m-%d')} 00:00:00"
    cutoff_end = f"{period_end.strftime('%Y-%m-%d')} 23:59:59"
    days = (period_end - period_start).days + 1

    # 上一周期（用于环比计算）
    prev_period_end = period_start - timedelta(days=1)
    prev_period_start = prev_period_end - timedelta(days=days - 1)
    prev_cutoff = f"{prev_period_start.strftime('%Y-%m-%d')} 00:00:00"
    prev_cutoff_end = f"{prev_period_end.strftime('%Y-%m-%d')} 23:59:59"
    
    cur_sessions = db.query(Session).filter(Session.start_time >= cutoff, Session.start_time <= cutoff_end).all()
    prev_sessions = db.query(Session).filter(Session.start_time >= prev_cutoff, Session.start_time <= prev_cutoff_end).all()
    cur_ids = [s.id for s in cur_sessions]; prev_ids = [s.id for s in prev_sessions]
    
    cur_leads = db.query(func.count(Lead.id)).filter(Lead.session_id.in_(cur_ids)).scalar() or 0 if cur_ids else 0
    prev_leads = db.query(func.count(Lead.id)).filter(Lead.session_id.in_(prev_ids)).scalar() or 0 if prev_ids else 0
    cur_spend = db.query(func.sum(SessionMetric.ad_spend)).filter(SessionMetric.session_id.in_(cur_ids)).scalar() or 0
    prev_spend = db.query(func.sum(SessionMetric.ad_spend)).filter(SessionMetric.session_id.in_(prev_ids)).scalar() or 0
    
    def change(cur, prev):
        if prev == 0: return "——" if cur > 0 else "0%"
        pct = (cur-prev)/prev*100; return f"+{pct:.1f}%" if pct >= 0 else f"{pct:.1f}%"
    
    recent = db.query(Session).order_by(Session.start_time.desc()).limit(10).all()
    recent_ids = [s.id for s in recent]
    recent_metrics = db.query(SessionMetric).filter(SessionMetric.session_id.in_(recent_ids)).all()
    recent_metric_dict = {m.session_id: m for m in recent_metrics}
    recent_lead_counts = db.query(Lead.session_id, func.count(Lead.id)).filter(Lead.session_id.in_(recent_ids)).group_by(Lead.session_id).all()
    recent_lead_dict = {sid: cnt for sid, cnt in recent_lead_counts}
    
    recent_data = []
    for s in recent:
        m = recent_metric_dict.get(s.id)
        lc = recent_lead_dict.get(s.id, 0)
        recent_data.append({"id":s.id,"start_time":s.start_time,"end_time":s.end_time,"duration_minutes":s.duration_minutes,"duration_text":format_duration_hms(s.start_time, s.end_time),"leads":lc,"spend":float(m.ad_spend or 0) if m else 0})
    
    # 趋势数据: 按日聚合 (批量查询优化)
    all_trend_sessions = db.query(Session.id, Session.start_time).filter(
        Session.start_time >= cutoff,
        Session.start_time <= cutoff_end
    ).all()
    
    from collections import defaultdict
    day_session_ids = defaultdict(list)
    for sid, st in all_trend_sessions:
        day_session_ids[st[:10]].append(sid)
    
    all_trend_ids = [sid for sid, _ in all_trend_sessions]
    if all_trend_ids:
        all_lead_counts = db.query(Lead.session_id, func.count(Lead.id)).filter(Lead.session_id.in_(all_trend_ids)).group_by(Lead.session_id).all()
        all_lead_dict = {sid: cnt for sid, cnt in all_lead_counts}
        all_spends = db.query(SessionMetric.session_id, SessionMetric.ad_spend).filter(SessionMetric.session_id.in_(all_trend_ids)).all()
        all_spend_dict = {sid: float(spend or 0) for sid, spend in all_spends}
    else:
        all_lead_dict = {}
        all_spend_dict = {}
    
    trend_data = []
    for i in range(days):
        d = (period_start + timedelta(days=i)).strftime("%Y-%m-%d")
        ids = day_session_ids.get(d, [])
        day_leads = sum(all_lead_dict.get(sid, 0) for sid in ids)
        day_spend = sum(all_spend_dict.get(sid, 0) for sid in ids)
        trend_data.append({"date": d, "leads": day_leads, "spend": day_spend})
    
    # 漏斗数据
    all_m = db.query(SessionMetric).filter(SessionMetric.session_id.in_(cur_ids)).all() if cur_ids else []
    funnel = {
        "exposure": sum(m.exposure_count or 0 for m in all_m),
        "view": sum(m.view_count or 0 for m in all_m),
        "watch_gt_1min": sum(m.watch_gt_1min or 0 for m in all_m),
        "interaction": sum(m.interaction_count or 0 for m in all_m),
        "leads": cur_leads
    }
    
    # 异常检测
    alerts = []
    if cur_ids:
        avg_cost = cur_spend / cur_leads if cur_leads > 0 else 0
        # 按时间取最新场次，避免id插入顺序≠时间顺序
        latest_session = db.query(Session).filter(Session.id.in_(cur_ids)).order_by(Session.start_time.desc()).first()
        if latest_session:
            latest_m = db.query(SessionMetric).filter(SessionMetric.session_id == latest_session.id).first()
            latest_leads = db.query(func.count(Lead.id)).filter(Lead.session_id == latest_session.id).scalar() or 0
            if latest_leads > 0 and latest_m:
                latest_cost = float(latest_m.ad_spend or 0) / latest_leads
                if latest_cost > avg_cost * 1.5:
                    alerts.append({"type": "warning", "message": f"最新场次线索成本¥{latest_cost:.0f}，高于近{days}天均值¥{avg_cost:.0f}的50%"})
            # 零留资告警（排除结束时间不足2小时的场次，避免数据同步延迟误报）
            if latest_leads == 0 and latest_session:
                from datetime import datetime as dt
                try:
                    end_dt = dt.strptime(latest_session.end_time, "%Y-%m-%d %H:%M:%S")
                    hours_since_end = (dt.now() - end_dt).total_seconds() / 3600
                    if hours_since_end >= 2:
                        alert_key = "zero_leads"
                        now = dt.now()
                        last_alert = _alert_last_sent.get(alert_key)
                        if not last_alert or (now - last_alert).total_seconds() >= ALERT_COOLDOWN_SECONDS:
                            _alert_last_sent[alert_key] = now
                            alerts.append({"type": "warning", "message": f"最新场次({latest_session.start_time[:16]})零留资，已结束{hours_since_end:.0f}小时"})
                except ValueError:
                    pass
    
    # 全历史平均值计算（纯SQL聚合，不加载全量ORM对象）
    all_leads_count = db.query(func.count(Lead.id)).scalar() or 0
    all_spend_sum = db.query(func.sum(SessionMetric.ad_spend)).scalar() or 0
    all_days_with_sessions = db.query(func.count(func.distinct(func.substr(Session.start_time, 1, 10)))).scalar() or 0
    all_weeks_with_sessions = db.query(func.count(func.distinct(func.strftime('%Y-%W', Session.start_time)))).scalar() or 0
    all_months_with_sessions = db.query(func.count(func.distinct(func.substr(Session.start_time, 1, 7)))).scalar() or 0

    historical_avg = {
        "avg_leads_per_day": round(all_leads_count / all_days_with_sessions, 1) if all_days_with_sessions > 0 else 0,
        "avg_spend_per_day": round(float(all_spend_sum or 0) / all_days_with_sessions, 0) if all_days_with_sessions > 0 else 0,
        "avg_lead_cost": round(float(all_spend_sum or 0) / all_leads_count, 1) if all_leads_count > 0 else 0,
        "avg_leads_per_week": round(all_leads_count / all_weeks_with_sessions, 1) if all_weeks_with_sessions > 0 else 0,
        "avg_spend_per_week": round(float(all_spend_sum or 0) / all_weeks_with_sessions, 0) if all_weeks_with_sessions > 0 else 0,
        "avg_leads_per_month": round(all_leads_count / all_months_with_sessions, 1) if all_months_with_sessions > 0 else 0,
        "avg_spend_per_month": round(float(all_spend_sum or 0) / all_months_with_sessions, 0) if all_months_with_sessions > 0 else 0
    }
    
    return {"code":0,"data":{"current":{"leads":cur_leads,"spend":cur_spend,"lead_cost":round(cur_spend/cur_leads,1) if cur_leads>0 else 0,"sessions":len(cur_sessions)},
        "previous":{"leads":prev_leads,"spend":prev_spend,"lead_cost":round(prev_spend/prev_leads,1) if prev_leads>0 else 0,"sessions":len(prev_sessions)},
        "change":{"leads":change(cur_leads,prev_leads),"spend":change(cur_spend,prev_spend),"lead_cost":change(cur_spend/cur_leads if cur_leads>0 else 0,prev_spend/prev_leads if prev_leads>0 else 0),"sessions":change(len(cur_sessions),len(prev_sessions))},
        "trend":trend_data,"recent_sessions":recent_data,"alerts":alerts,"funnel":funnel,
        "historical_avg":historical_avg,
        "period":{"start":period_start.strftime("%Y-%m-%d"),"end":period_end.strftime("%Y-%m-%d"),"label":period_label}}}

@router.get("/sessions")
def list_sessions(page: int = 1, size: int = 20, db: DBSession = Depends(get_db)):
    total = db.query(Session).count()
    items = db.query(Session).order_by(Session.start_time.desc()).offset((page-1)*size).limit(size).all()
    return {"code":0,"data":{"items":[{"id":s.id,"start_time":s.start_time,"end_time":s.end_time,"duration_minutes":s.duration_minutes,"analyzed":s.analyzed} for s in items],"total":total,"page":page,"size":size}}

@router.get("/sessions/for-reports")
def list_sessions_for_reports(page: int = 1, size: int = 20, db: DBSession = Depends(get_db)):
    """列出所有场次（分页），带是否有报告标记。N+1→批量IN查询重构。"""
    total = db.query(Session).count()
    sessions = db.query(Session).order_by(Session.start_time.desc()).offset((page - 1) * size).limit(size).all()
    if not sessions:
        return {"code": 0, "data": {"items": [], "total": 0, "page": page, "size": size}}

    session_ids = [s.id for s in sessions]

    # 批量查询SessionMetric
    metrics = db.query(SessionMetric).filter(SessionMetric.session_id.in_(session_ids)).all()
    metric_dict = {m.session_id: m for m in metrics}

    # 批量查询Lead count (GROUP BY)
    lead_counts = db.query(Lead.session_id, func.count(Lead.id)).filter(Lead.session_id.in_(session_ids)).group_by(Lead.session_id).all()
    lead_dict = {sid: cnt for sid, cnt in lead_counts}

    # 批量查询Report (session类型)
    reports = db.query(Report).filter(Report.session_id.in_(session_ids), Report.report_type == "session").all()
    report_dict = {r.session_id: r for r in reports}

    result = []
    for s in sessions:
        m = metric_dict.get(s.id)
        lc = lead_dict.get(s.id, 0)
        report = report_dict.get(s.id)
        result.append({
            "id": s.id,
            "start_time": s.start_time,
            "end_time": s.end_time,
            "duration_minutes": s.duration_minutes,
            "duration_text": format_duration_hms(s.start_time, s.end_time),
            "leads": lc,
            "spend": float(m.ad_spend or 0) if m else 0,
            "has_report": report is not None,
            "report_id": report.id if report else None
        })
    return {"code": 0, "data": {"items": result, "total": total, "page": page, "size": size}}

@router.get("/sessions/by-room")
def get_sessions_by_room(date: str = Query(...), room_index: int = Query(None), db: DBSession = Depends(get_db)):
    """获取某日（可选某直播间）的场次列表，用于场选择器"""
    next_date = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    sessions = db.query(Session).filter(
        or_(
            Session.start_time.between(f"{date} 00:00:00", f"{next_date} 00:00:00"),
            Session.end_time.between(f"{date} 00:00:00", f"{next_date} 00:00:00")
        )
    ).order_by(Session.start_time).all()

    result = []
    for s in sessions:
        m = db.query(SessionMetric).filter(SessionMetric.session_id == s.id).first()
        lead_count = db.query(func.count(Lead.id)).filter(Lead.session_id == s.id).scalar() or 0
        result.append({
            "id": s.id, "start_time": s.start_time, "end_time": s.end_time,
            "duration_minutes": s.duration_minutes,
            "leads": lead_count,
            "spend": float(m.ad_spend or 0) if m else 0,
        })
    return {"code": 0, "data": result}

@router.get("/sessions/{session_id}")
def session_detail(session_id: int, db: DBSession = Depends(get_db)):
    s = db.query(Session).get(session_id)
    if not s: raise HTTPException(404, detail="场次不存在")
    m = db.query(SessionMetric).filter(SessionMetric.session_id==session_id).first()
    leads = db.query(Lead).filter(Lead.session_id==session_id).all()
    comments = db.query(Comment).filter(Comment.session_id==session_id).all()
    hiu = db.query(HighIntentUser).filter(HighIntentUser.session_id==session_id).all()
    report = db.query(Report).filter(Report.session_id==session_id, Report.report_type=="session").first()
    anchors = db.query(Anchor).join(SessionAnchor).filter(SessionAnchor.session_id==session_id).all()
    return {"code":0,"data":{"session":{"id":s.id,"start_time":s.start_time,"end_time":s.end_time,"duration_minutes":s.duration_minutes},
        "metrics":{c.name:getattr(m,c.name) for c in m.__table__.columns} if m else {},
        "leads":[{"id":l.id,"lead_time":l.lead_time,"nickname":l.nickname,"city":l.city,"path":l.path,"ad_account":l.ad_account} for l in leads],
        "comments":[{"nickname":c.nickname,"has_lead":c.has_lead,"content":c.content,"comment_time":c.comment_time} for c in comments],
        "high_intent_users":[{"nickname":h.nickname,"avatar_url":h.avatar_url,"comment_count":h.comment_count,"stay_duration":h.stay_duration,"status":h.status} for h in hiu],
        "report":{"content":report.content,"generated_at":report.generated_at} if report else None,
        "anchors":[{"id":a.id,"name":a.name} for a in anchors],
        "funnel":{"exposure":m.exposure_count if m else 0,"view":m.view_count if m else 0,"watch_gt_1min":m.watch_gt_1min if m else 0,"interaction":m.interaction_count if m else 0,"leads":len(leads)}}}

@router.get("/reports")
def list_reports(type: Optional[str] = None, page: int = 1, size: int = 20, db: DBSession = Depends(get_db)):
    query = db.query(Report)
    if type: query = query.filter(Report.report_type == type)
    total = query.count(); items = query.order_by(Report.generated_at.desc()).offset((page-1)*size).limit(size).all()
    return {"code":0,"data":{"items":[{"id":r.id,"report_type":r.report_type,"period":r.period,"generated_at":r.generated_at} for r in items],"total":total,"page":page,"size":size}}

@router.get("/reports/{report_id}/download")
def download_report(report_id: int, db: DBSession = Depends(get_db)):
    report = db.query(Report).get(report_id)
    if not report: raise HTTPException(404)
    return StreamingResponse(io.BytesIO(report.content.encode('utf-8')), media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename={report.report_type}_{report.period}.md"})

@router.get("/reports/dates-status")
def list_dates_with_report_status(db: DBSession = Depends(get_db)):
    """列出所有有场次数据的日期及日报生成状态"""
    from sqlalchemy import func as sa_func
    rows = db.query(sa_func.substr(Session.start_time, 1, 10).label('date'), sa_func.count(Session.id).label('session_count')).group_by('date').order_by(sa_func.substr(Session.start_time, 1, 10).desc()).all()
    result = []
    for row in rows:
        report = db.query(Report).filter(Report.report_type == "daily", Report.period == row[0]).first()
        result.append({"date": row[0], "session_count": row[1], "has_report": report is not None, "report_id": report.id if report else None, "generated_at": report.generated_at if report else None})
    return {"code": 0, "data": {"items": result, "total": len(result)}}

@router.get("/reports/session/{session_id}")
def get_session_report(session_id: int, db: DBSession = Depends(get_db)):
    """获取场次AI分析报告缓存"""
    report = db.query(Report).filter(Report.session_id == session_id, Report.report_type == "session").first()
    if report:
        return {"code": 0, "content": report.content, "generated_at": report.generated_at}
    return {"code": 1, "content": None, "message": "暂无分析报告，数据入库后自动触发AI分析"}

@router.post("/reports/session/{session_id}/generate")
def generate_session_report(session_id: int, db: DBSession = Depends(get_db)):
    """生成单场AI分析报告"""
    session = db.query(Session).get(session_id)
    if not session: raise HTTPException(404, detail="场次不存在")
    existing = db.query(Report).filter(Report.session_id == session_id, Report.report_type == "session").first()
    if existing:
        # 重新生成
        from services.ai_service import analyze_session
        analyze_session(db, session_id)
        return {"code": 0, "message": "报告已重新生成", "report_id": existing.id}
    from services.ai_service import analyze_session
    report_id = analyze_session(db, session_id)
    return {"code": 0, "message": "报告生成成功", "report_id": report_id}

@router.post("/reports/daily/{date}/generate")
def generate_daily_report_api(date: str, db: DBSession = Depends(get_db)):
    """生成日报"""
    from services.report_service import generate_daily_report
    report_id = generate_daily_report(db, date)
    if not report_id: raise HTTPException(404, detail="该日期无场次数据")
    return {"code": 0, "message": "日报生成成功", "report_id": report_id}

@router.post("/reports/weekly/{week}/generate")
def generate_weekly_report_api(week: str, db: DBSession = Depends(get_db)):
    """生成周报"""
    from services.report_service import generate_weekly_report
    report_id = generate_weekly_report(db, week)
    if not report_id: raise HTTPException(404, detail="该周期无场次数据")
    return {"code": 0, "message": "周报生成成功", "report_id": report_id}

@router.post("/reports/monthly/{month}/generate")
def generate_monthly_report_api(month: str, db: DBSession = Depends(get_db)):
    """生成月报"""
    from services.report_service import generate_monthly_report
    report_id = generate_monthly_report(db, month)
    if not report_id: raise HTTPException(404, detail="该月份无场次数据")
    return {"code": 0, "message": "月报生成成功", "report_id": report_id}

@router.delete("/reports/{report_id}")
def delete_report(report_id: int, db: DBSession = Depends(get_db)):
    """删除报告"""
    report = db.query(Report).get(report_id)
    if not report: raise HTTPException(404, detail="报告不存在")
    db.delete(report); db.commit()
    return {"code": 0, "message": "报告已删除"}

@router.post("/reports/{report_id}/regenerate")
def regenerate_report(report_id: int, db: DBSession = Depends(get_db)):
    """重新生成报告"""
    report = db.query(Report).get(report_id)
    if not report: raise HTTPException(404, detail="报告不存在")
    if report.report_type == "session":
        from services.ai_service import analyze_session
        analyze_session(db, report.session_id)
        return {"code": 0, "message": "场次报告已重新生成"}
    elif report.report_type == "daily":
        from services.report_service import generate_daily_report
        generate_daily_report(db, report.period)
        return {"code": 0, "message": "日报已重新生成"}
    elif report.report_type == "weekly":
        from services.report_service import generate_weekly_report
        generate_weekly_report(db, report.period)
        return {"code": 0, "message": "周报已重新生成"}
    elif report.report_type == "monthly":
        from services.report_service import generate_monthly_report
        generate_monthly_report(db, report.period)
        return {"code": 0, "message": "月报已重新生成"}
    return {"code": 400, "message": "未知报告类型"}

@router.get("/trends")
def trends_api(date_from: Optional[str] = None, date_to: Optional[str] = None, metric: str = "leads", group_by: str = "date", anchor_id: Optional[int] = None, db: DBSession = Depends(get_db)):
    # 使用Lead子查询替代SessionMetric.total_leads，与首页/漏斗数据源一致
    lead_count_sq = db.query(Lead.session_id, func.count(Lead.id).label('lead_cnt')).group_by(Lead.session_id).subquery()
    query = db.query(Session.start_time, SessionMetric.ad_spend, func.coalesce(lead_count_sq.c.lead_cnt, 0)).join(SessionMetric).outerjoin(lead_count_sq, lead_count_sq.c.session_id == Session.id)
    if anchor_id:
        anchor_session_ids = [sa.session_id for sa in db.query(SessionAnchor).filter(SessionAnchor.anchor_id == anchor_id).all()]
        query = query.filter(Session.id.in_(anchor_session_ids))
    if date_from: query = query.filter(Session.start_time >= date_from)
    if date_to: query = query.filter(Session.start_time <= date_to + " 23:59:59")
    results = query.order_by(Session.start_time).all()
    
    if group_by == "date":
        data = [{"date":r[0][:10],"leads":r[2],"spend":float(r[1] or 0),"lead_cost":round(float(r[1] or 0)/r[2],1) if r[2]>0 else 0} for r in results]
    elif group_by == "hour":
        from collections import defaultdict
        hour_data = defaultdict(lambda: {"leads":0,"spend":0.0,"count":0})
        for r in results:
            hour = int(r[0][11:13])
            hour_data[hour]["leads"] += r[2] or 0
            hour_data[hour]["spend"] += float(r[1] or 0)
            hour_data[hour]["count"] += 1
        data = [{"hour":h,"avg_leads":round(v["leads"]/v["count"],1) if v["count"]>0 else 0,"avg_spend":round(v["spend"]/v["count"],1),"session_count":v["count"]} for h,v in sorted(hour_data.items())]
    elif group_by == "weekday":
        weekday_names = ["周日","周一","周二","周三","周四","周五","周六"]
        from collections import defaultdict
        wd_data = defaultdict(lambda: {"leads":0,"spend":0.0,"count":0})
        for r in results:
            from datetime import datetime as dt
            wd = dt.strptime(r[0][:10],"%Y-%m-%d").weekday()
            wd = (wd + 1) % 7
            wd_data[wd]["leads"] += r[2] or 0
            wd_data[wd]["spend"] += float(r[1] or 0)
            wd_data[wd]["count"] += 1
        data = [{"weekday":str(w),"weekday_name":weekday_names[w],"avg_leads":round(v["leads"]/v["count"],1) if v["count"]>0 else 0,"session_count":v["count"]} for w,v in sorted(wd_data.items())]
    else:
        data = [{"date":r[0][:10],"leads":r[2],"spend":float(r[1] or 0),"lead_cost":round(float(r[1] or 0)/r[2],1) if r[2]>0 else 0} for r in results]
    
    return {"code":0,"data":data}

@router.get("/leads")
def list_leads(keyword: Optional[str] = None, city: Optional[str] = None, date_from: Optional[str] = None, date_to: Optional[str] = None, is_deal: Optional[bool] = None, is_valid: Optional[str] = None, page: int = 1, size: int = 20, db: DBSession = Depends(get_db)):
    query = db.query(Lead).join(Session)
    if keyword: query = query.filter(Lead.nickname.contains(keyword))
    if city: query = query.filter(Lead.city == city)
    if date_from: query = query.filter(Session.start_time >= date_from)
    if date_to: query = query.filter(Session.start_time <= date_to + " 23:59:59")
    if is_deal is not None: query = query.filter(Lead.is_deal == is_deal)
    if is_valid == "true": query = query.filter(Lead.is_valid == True)
    elif is_valid == "false": query = query.filter(Lead.is_valid == False)
    elif is_valid == "null": query = query.filter(Lead.is_valid == None)
    total = query.count(); items = query.order_by(Lead.lead_time.desc(), Lead.created_at.desc()).offset((page-1)*size).limit(size).all()
    all_q = db.query(Lead).join(Session)
    if keyword: all_q = all_q.filter(Lead.nickname.contains(keyword))
    if city: all_q = all_q.filter(Lead.city == city)
    paid = all_q.filter(Lead.ad_account != None, Lead.ad_account != '--').count()
    city_stats = db.query(Lead.city, func.count()).group_by(Lead.city).order_by(func.count().desc()).limit(10).all()
    return {"code":0,"data":{"items":[{"id":l.id,"lead_time":l.lead_time,"nickname":l.nickname,"city":l.city,"path":l.path,"ad_account":l.ad_account,"is_deal":l.is_deal,"is_valid":l.is_valid} for l in items],
        "total":total,"page":page,"size":size,"charts":{"source":{"paid":paid,"organic":total-paid},"city_top10":[{"city":c[0],"count":c[1]} for c in city_stats]}}}

@router.get("/anchors/stats")
def anchor_stats(date_from: Optional[str] = None, date_to: Optional[str] = None, db: DBSession = Depends(get_db)):
    from utils import time_in_range
    from collections import defaultdict
    anchors = db.query(Anchor).all()
    result = []
    for a in anchors:
        sa_list = db.query(SessionAnchor).filter(SessionAnchor.anchor_id==a.id).all()
        if not sa_list: continue
        sa_groups = defaultdict(list)
        for sa in sa_list:
            sa_groups[sa.session_id].append(sa)
        ids = list(sa_groups.keys())
        sessions = db.query(Session).filter(Session.id.in_(ids))
        if date_from: sessions = sessions.filter(Session.start_time >= date_from)
        if date_to: sessions = sessions.filter(Session.start_time <= date_to + " 23:59:59")
        s_list = sessions.all()
        leads = effective_leads = 0
        for s in s_list:
            session_leads = db.query(Lead).filter(Lead.session_id == s.id).all()
            if not session_leads:
                continue
            sa_records = sa_groups.get(s.id, [])
            if sa_records:
                for l in session_leads:
                    hhmm = extract_hhmm(l.lead_time)
                    if not hhmm:
                        continue
                    for sa in sa_records:
                        on_t = sa.on_time or (s.start_time[11:16] if s.start_time else "")
                        off_t = sa.off_time or (s.end_time[11:16] if s.end_time else "")
                        if on_t and off_t and time_in_range(on_t, off_t, hhmm):
                            leads += 1
                            if l.is_valid:
                                effective_leads += 1
                            break
            else:
                leads += len(session_leads)
                for l in session_leads:
                    if l.is_valid:
                        effective_leads += 1
        s_ids = [s.id for s in s_list]
        spend = db.query(func.sum(SessionMetric.ad_spend)).filter(SessionMetric.session_id.in_(s_ids)).scalar() or 0
        deals_count = db.query(func.count(Deal.id)).filter(Deal.session_id.in_(s_ids)).scalar() or 0
        deals_amount = db.query(func.sum(Deal.amount)).filter(Deal.session_id.in_(s_ids)).scalar() or 0
        deal_rate = round(deals_count/leads*100,1) if leads>0 else 0
        total_hours = round(sum(s.duration_minutes for s in s_list) / 60, 1)
        result.append({"anchor_id":a.id,"anchor_name":a.name,"gender":a.gender,"style":a.style,"session_count":len(s_list),"total_hours":total_hours,"avg_hours_per_session":round(total_hours/len(s_list),1) if s_list else 0,"avg_leads":round(leads/len(s_list),1) if s_list else 0,"avg_spend":round(float(spend)/len(s_list),1) if s_list else 0,"total_leads":leads,"effective_leads":effective_leads,"total_spend":float(spend or 0),"deal_count":deals_count,"deal_amount":float(deals_amount or 0),"deal_rate":deal_rate})
    return {"code":0,"data":result}

@router.get("/export/sessions")
def export_sessions(date_from: Optional[str] = None, date_to: Optional[str] = None, db: DBSession = Depends(get_db)):
    query = db.query(Session, SessionMetric).join(SessionMetric, isouter=True)
    if date_from: query = query.filter(Session.start_time >= date_from)
    if date_to: query = query.filter(Session.start_time <= date_to + " 23:59:59")
    sessions = query.order_by(Session.start_time).all()
    
    # 批量查询Lead count
    session_ids = [s.id for s, _ in sessions]
    if session_ids:
        lead_counts = db.query(Lead.session_id, func.count(Lead.id)).filter(Lead.session_id.in_(session_ids)).group_by(Lead.session_id).all()
        lead_dict = {sid: cnt for sid, cnt in lead_counts}
    else:
        lead_dict = {}
    
    wb = Workbook(); ws = wb.active; ws.title = "场次数据"
    ws.append(["开播时间","结束时间","时长(分)","线索数","消耗","线索成本"])
    for s, m in sessions:
        lc = lead_dict.get(s.id, 0)
        spend = float(m.ad_spend or 0) if m else 0
        ws.append([s.start_time, s.end_time, s.duration_minutes, lc, spend, round(spend/lc,1) if lc>0 else 0])
    output = io.BytesIO(); wb.save(output); output.seek(0)
    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition":"attachment; filename=sessions.xlsx"})

@router.get("/export/leads")
def export_leads(date_from: Optional[str] = None, date_to: Optional[str] = None, db: DBSession = Depends(get_db)):
    query = db.query(Lead).join(Session)
    if date_from: query = query.filter(Session.start_time >= date_from)
    if date_to: query = query.filter(Session.start_time <= date_to + " 23:59:59")
    leads = query.order_by(Lead.created_at.desc()).all()
    wb = Workbook(); ws = wb.active; ws.title = "线索数据"
    ws.append(["留资时间","昵称","线索ID","电话","商品","城市","路径","标签","账户","成单"])
    for l in leads: ws.append([l.lead_time, l.nickname, l.lead_id, l.phone_masked, l.product_name, l.city, l.path, l.tags, l.ad_account, "是" if l.is_deal else "否"])
    output = io.BytesIO(); wb.save(output); output.seek(0)
    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition":"attachment; filename=leads.xlsx"})

# ===== 前台排班查询 =====

@router.get("/schedule")
def get_schedule(date: str, db: DBSession = Depends(get_db)):
    """查询某日排班信息（含主播详情）"""
    binding = db.query(ScheduleBinding).filter(ScheduleBinding.date == date).first()
    if not binding:
        return {"code": 0, "data": None}
    plan = db.query(SchedulePlan).get(binding.plan_id)
    if not plan:
        return {"code": 0, "data": None}
    slots = db.query(ScheduleSlot).filter(ScheduleSlot.plan_id == plan.id).order_by(ScheduleSlot.time_slot, ScheduleSlot.room_index).all()
    anchor_mapping = json.loads(binding.anchor_mapping) if binding.anchor_mapping else {}
    anchor_ids = [int(v) for v in anchor_mapping.values() if v]
    anchors = db.query(Anchor).filter(Anchor.id.in_(anchor_ids)).all() if anchor_ids else []
    anchor_dict = {a.id: {"id": a.id, "name": a.name, "gender": a.gender, "style": a.style} for a in anchors}
    resolved_mapping = {}
    for slot_key, anchor_id in anchor_mapping.items():
        if anchor_id and int(anchor_id) in anchor_dict:
            resolved_mapping[slot_key] = anchor_dict[int(anchor_id)]
    return {"code": 0, "data": {
        "plan": {"id": plan.id, "name": plan.name, "start_time": plan.start_time, "end_time": plan.end_time,
            "time_granularity": plan.time_granularity, "room_count": plan.room_count, "anchor_count": plan.anchor_count},
        "slots": [{"time_slot": s.time_slot, "room_index": s.room_index, "slot_status": s.slot_status, "anchor_slot": s.anchor_slot} for s in slots],
        "anchor_mapping": resolved_mapping}}

@router.get("/room-accounts")
def get_room_accounts(date: str, db: DBSession = Depends(get_db)):
    """查询某日直播间账户绑定"""
    bindings = db.query(RoomAccountBinding).filter(RoomAccountBinding.date == date).order_by(RoomAccountBinding.room_index).all()
    if not bindings:
        return {"code": 0, "data": []}
    return {"code": 0, "data": [{"room_index": b.room_index, "ad_account_id": b.ad_account_id,
        "account_name": b.ad_account.account_name if b.ad_account else None,
        "account_id": b.ad_account.account_id if b.ad_account else None} for b in bindings]}

# ===== 报表Tab数据 API =====

METRIC_FIELD_MAP = {
    "exposure_count": "exposure_count",
    "cumulative_viewers": "cumulative_viewers",
    "view_count": "view_count",
    "watch_gt_1min": "watch_gt_1min",
    "interaction_count": "interaction_count",
    "total_leads": None,  # 需要关联Lead表
    "ad_spend": "ad_spend",
    "avg_watch_duration": "avg_watch_duration",
    "share_count": "share_count",
    "follow_count": "follow_count",
    "new_fans": "new_fans",
    "product_click_count": "product_click_count",
    "product_exposure_count": "product_exposure_count",
    "comment_count": "comment_count",
    "peak_viewers": "peak_viewers",
    "gift_count": "gift_count",
    "gift_amount": "gift_amount",
}


def _compute_metric(formula: str, values: dict) -> Optional[float]:
    """根据公式计算复合指标，如 cumulative_viewers/exposure_count"""
    try:
        parts = formula.split("/")
        if len(parts) == 2:
            a = float(values.get(parts[0].strip(), 0) or 0)
            b = float(values.get(parts[1].strip(), 0) or 0)
            return round(a / b * 100, 2) if b > 0 else 0
        return None
    except Exception:
        return None


@router.get("/dashboard-tabs")
def get_dashboard_tabs(range: str = Query("week"), date: str = Query(None), db: DBSession = Depends(get_db)):
    """获取所有Tab配置（前台用，无需鉴权）"""
    tabs = db.query(DashboardTab).order_by(DashboardTab.priority, DashboardTab.id).all()
    return {"code": 0, "data": [{"id": t.id, "name": t.name, "priority": t.priority,
        "is_system": t.is_system, "chart_type": t.chart_type,
        "metrics_config": json.loads(t.metrics_config) if t.metrics_config else []} for t in tabs]}


@router.get("/dashboard-tabs/{tab_id}/data")
def get_tab_data(tab_id: int, range_type: str = Query("week", alias="range"), date: str = Query(None),
                 session_id: int = Query(None), db: DBSession = Depends(get_db)):
    """获取指定Tab的图表数据"""
    import calendar
    tab = db.query(DashboardTab).get(tab_id)
    if not tab:
        raise HTTPException(404)

    metrics_config = json.loads(tab.metrics_config) if tab.metrics_config else []

    # 确定时间范围
    try:
        base_date = datetime.strptime(date, "%Y-%m-%d").date() if date else datetime.now().date()
    except ValueError:
        base_date = datetime.now().date()

    if range_type == "day":
        period_start = base_date
        period_end = base_date
    elif range_type == "week":
        period_start = base_date - timedelta(days=base_date.weekday())
        period_end = period_start + timedelta(days=6)
    else:
        period_start = base_date.replace(day=1)
        last_day = calendar.monthrange(base_date.year, base_date.month)[1]
        period_end = base_date.replace(day=last_day)

    # 如果指定了session_id（场选择器），则只查该场次
    if session_id:
        session = db.query(Session).get(session_id)
        if not session:
            raise HTTPException(404, "场次不存在")
        sessions = [session]
    else:
        cutoff = f"{period_start.strftime('%Y-%m-%d')} 00:00:00"
        cutoff_end = f"{period_end.strftime('%Y-%m-%d')} 23:59:59"
        sessions = db.query(Session).filter(
            Session.start_time >= cutoff, Session.start_time <= cutoff_end
        ).order_by(Session.start_time).all()

    if not sessions:
        return {"code": 0, "data": {"labels": [], "series": []}}

    session_ids = [s.id for s in sessions]

    # 批量查询指标
    metrics_list = db.query(SessionMetric).filter(SessionMetric.session_id.in_(session_ids)).all()
    metric_dict = {m.session_id: m for m in metrics_list}

    # 批量查询线索数
    lead_counts = db.query(Lead.session_id, func.count(Lead.id)).filter(
        Lead.session_id.in_(session_ids)
    ).group_by(Lead.session_id).all()
    lead_dict = {sid: cnt for sid, cnt in lead_counts}

    # 按日聚合
    from collections import defaultdict
    day_data = defaultdict(lambda: defaultdict(float))
    day_session_count = defaultdict(int)

    for s in sessions:
        day_key = s.start_time[:10]
        m = metric_dict.get(s.id)
        if not m:
            continue
        day_session_count[day_key] += 1

        # 构建该场次的值字典
        values = {}
        for field_name, col_name in METRIC_FIELD_MAP.items():
            if col_name:
                values[field_name] = float(getattr(m, col_name, 0) or 0)
        values["total_leads"] = float(lead_dict.get(s.id, 0))

        # 计算每个指标
        for mc in metrics_config:
            key = mc.get("key", "")
            mtype = mc.get("type", "field")
            if mtype == "computed":
                formula = mc.get("formula", "")
                val = _compute_metric(formula, values)
                day_data[day_key][key] = day_data[day_key].get(key, 0) + (val or 0)
            else:
                val = values.get(key, 0)
                day_data[day_key][key] = day_data[day_key].get(key, 0) + val

    # 生成标签和序列
    days = (period_end - period_start).days + 1
    labels = []
    series_map = {mc["key"]: [] for mc in metrics_config}
    for i in range(days):
        d = (period_start + timedelta(days=i)).strftime("%Y-%m-%d")
        labels.append(d)
        for mc in metrics_config:
            key = mc["key"]
            series_map[key].append(day_data[d].get(key, 0))

    series = [{"name": mc.get("label", mc["key"]), "key": mc["key"], "data": series_map[mc["key"]]} for mc in metrics_config]

    return {"code": 0, "data": {"labels": labels, "series": series}}


@router.get("/dashboard-tabs/{tab_id}/analysis")
def get_tab_analysis(tab_id: int, range: str = Query("day", alias="range"),
                     date: str = Query(None), session_id: int = Query(None),
                     db: DBSession = Depends(get_db)):
    """获取缓存的Tab分析结果（不触发AI）"""
    if not date: date = datetime.now().strftime("%Y-%m-%d")
    cache = db.query(TabAnalysis).filter(
        TabAnalysis.tab_id == tab_id,
        TabAnalysis.range_type == range,
        TabAnalysis.range_value == date,
        TabAnalysis.session_id == session_id
    ).first()
    if cache and cache.content:
        return {"code": 0, "data": {"content": cache.content}}
    return {"code": 1, "data": None}


def _auto_analyze_dashboard(date_str: str, db: DBSession):
    """油猴数据同步后，自动生成并缓存当日所有Tab的AI分析"""
    from models import DashboardTab as DBTab, TabAnalysis as TA, Setting as ST
    try:
        tabs = db.query(DBTab).order_by(DBTab.priority, DBTab.id).all()
        if not tabs:
            return
        from services.ai_service import get_ai_config
        config = get_ai_config(db)
        client = __import__('openai').OpenAI(
            api_key=config["ai_api_key"],
            base_url=config.get("ai_base_url", "https://api.openai.com/v1")
        )
        for tab in tabs:
            cache = db.query(TA).filter(
                TA.tab_id == tab.id, TA.range_type == 'day',
                TA.range_value == date_str, TA.session_id == None,
            ).first()
            if cache and cache.content:
                continue
            tab_data = get_tab_data(tab.id, range_type='day', date=date_str, db=db)
            chart_data = tab_data.get("data", {})
            metrics_config = json.loads(tab.metrics_config) if tab.metrics_config else []
            analysis_input = f"## 时间范围: day - {date_str}\n## 指标数据\n"
            for mc in metrics_config:
                label = mc.get("label", mc["key"])
                values = next((s["data"] for s in chart_data.get("series", []) if s["key"] == mc["key"]), [])
                analysis_input += f"- {label}: {values}\n"
            sp = tab.system_prompt
            if not sp:
                sp_row = db.query(ST).filter(ST.key == "dashboard_default_system_prompt").first()
                sp = sp_row.value if sp_row else "你是一位专业的抖音直播数据分析师。"
            up = tab.user_prompt
            if not up:
                up_row = db.query(ST).filter(ST.key == "dashboard_default_user_prompt").first()
                up = up_row.value if up_row else "请分析以下数据指标趋势。"
            up = up + "\n\n" + analysis_input
            resp = client.chat.completions.create(
                model=config.get("ai_model", "gpt-4o"),
                messages=[{"role":"system","content":sp},{"role":"user","content":up}],
                timeout=60,
            )
            content = resp.choices[0].message.content
            if cache:
                cache.content = content
            else:
                db.add(TA(tab_id=tab.id, range_type='day', range_value=date_str, session_id=None, content=content))
            db.commit()
    except Exception as e:
        logger.warning(f"自动分析Dashboard Tab失败: {e}")


@router.post("/dashboard-tabs/{tab_id}/analyze")
def analyze_tab(tab_id: int, data: dict, db: DBSession = Depends(get_db)):
    """手动触发AI分析（流式输出）"""
    tab = db.query(DashboardTab).get(tab_id)
    if not tab:
        raise HTTPException(404)

    range_type = data.get("range", "week")
    range_value = data.get("date", datetime.now().strftime("%Y-%m-%d"))
    session_id = data.get("session_id")

    cache = db.query(TabAnalysis).filter(
        TabAnalysis.tab_id == tab_id,
        TabAnalysis.range_type == range_type,
        TabAnalysis.range_value == range_value,
        TabAnalysis.session_id == session_id
    ).first()

    if cache and cache.content:
        return {"code": 0, "data": {"content": cache.content, "cached": True}}

    tab_data_resp = get_tab_data(tab_id, range_type=range_type, date=range_value, session_id=session_id, db=db)
    chart_data = tab_data_resp.get("data", {})

    metrics_config = json.loads(tab.metrics_config) if tab.metrics_config else []
    analysis_input = f"## 时间范围: {range_type} - {range_value}\n"
    if session_id:
        analysis_input += f"## 场次ID: {session_id}\n"
    analysis_input += "## 指标数据\n"
    for mc in metrics_config:
        label = mc.get("label", mc["key"])
        values = next((s["data"] for s in chart_data.get("series", []) if s["key"] == mc["key"]), [])
        analysis_input += f"- {label}: {values}\n"

    system_prompt = tab.system_prompt
    if not system_prompt:
        sp = db.query(Setting).filter(Setting.key == "dashboard_default_system_prompt").first()
        system_prompt = sp.value if sp else "你是一位专业的抖音直播数据分析师。"

    user_prompt = tab.user_prompt
    if not user_prompt:
        up = db.query(Setting).filter(Setting.key == "dashboard_default_user_prompt").first()
        user_prompt = up.value if up else "请分析以下数据指标趋势。"

    user_prompt = user_prompt + "\n\n" + analysis_input

    try:
        from services.ai_service import get_ai_config
        config = get_ai_config(db)

        client = __import__('openai').OpenAI(
            api_key=config["ai_api_key"],
            base_url=config.get("ai_base_url", "https://api.openai.com/v1")
        )

        stream = client.chat.completions.create(
            model=config.get("ai_model", "gpt-4o"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            stream=True,
        )

        def generate():
            full_content = ""
            try:
                for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        text = chunk.choices[0].delta.content
                        full_content += text
                        yield f"data: {json.dumps({'text': text}, ensure_ascii=False)}\n\n"
            except Exception as e:
                logger.error(f"AI分析流式输出中断: {e}")
                yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
                return
            if cache:
                cache.content = full_content
            else:
                db.add(TabAnalysis(
                    tab_id=tab_id, range_type=range_type, range_value=range_value,
                    session_id=session_id, content=full_content
                ))
            db.commit()
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")
    except Exception as e:
        logger.error(f"AI分析失败: {e}")
        return {"code": 500, "message": f"AI分析失败: {str(e)}"}


# ===== 前台线索领取API =====
@router.post("/clue-board/verify")
def verify_team_password(data: dict, db: DBSession = Depends(get_db)):
    """验证团队密码，返回团队信息"""
    from models import RecruitTeam
    team_name = data.get("team_name", "")
    password = data.get("password", "")
    team = db.query(RecruitTeam).filter(RecruitTeam.name == team_name, RecruitTeam.is_active == True).first()
    if not team:
        return {"code": 404, "message": "团队不存在"}
    if team.require_password and team.password != password:
        return {"code": 401, "message": "密码错误"}
    return {"code": 0, "data": {"team_id": team.id, "team_name": team.name, "require_password": team.require_password}}


@router.get("/clue-board/teams")
def list_active_teams(db: DBSession = Depends(get_db)):
    """获取所有活跃团队列表（用于选择团队）"""
    from models import RecruitTeam
    teams = db.query(RecruitTeam).filter(RecruitTeam.is_active == True).all()
    return {"code": 0, "data": [{"id": t.id, "name": t.name, "require_password": t.require_password} for t in teams]}


@router.get("/clue-board/assignments")
def get_team_assignments(team_id: int = Query(...), status: Optional[str] = None,
                         page: int = 1, size: int = 50, db: DBSession = Depends(get_db)):
    """获取团队的线索分配列表"""
    from models import ClueAssignment, ApiClue, RecruitEmployee
    query = db.query(ClueAssignment).filter(ClueAssignment.team_id == team_id)
    if status:
        query = query.filter(ClueAssignment.status == status)
    total = query.count()
    items = query.order_by(ClueAssignment.assigned_at.desc()).offset((page - 1) * size).limit(size).all()
    result = []
    for a in items:
        clue = a.clue
        emp = a.employee
        result.append({
            "id": a.id, "clue_id": a.clue_id,
            "assigned_at": a.assigned_at, "claimed_at": a.claimed_at,
            "status": a.status, "feedback": a.feedback, "remark": a.remark,
            "employee_name": emp.name if emp else None,
            # 线索信息
            "phone_decrypted": clue.phone_decrypted if clue else None,
            "phone_masked": clue.phone_masked if clue else None,
            "is_decrypted": clue.is_decrypted if clue else False,
            "nickname": clue.nickname if clue else None,
            "name": clue.name if clue else None,
            "lead_time": clue.lead_time if clue else None,
            "create_time_detail": clue.create_time_detail if clue else None,
            "anchor_names": clue.anchor_names if clue else None,
            "weixin": clue.weixin if clue else None,
            "weixin_manual": clue.weixin_manual if clue else None,
            "city_name": clue.city_name if clue else None,
            "effective_state": clue.effective_state if clue else None,
            "product_name": clue.product_name if clue else None,
        })
    return {"code": 0, "data": {"items": result, "total": total}}


@router.get("/clue-board/detail/{assignment_id}")
def get_clue_detail(assignment_id: int, db: DBSession = Depends(get_db)):
    """获取线索详情（含评论）"""
    from models import ClueAssignment, ApiClue, Comment
    assignment = db.query(ClueAssignment).get(assignment_id)
    if not assignment:
        return {"code": 404, "message": "分配记录不存在"}
    clue = assignment.clue
    if not clue:
        return {"code": 404, "message": "线索不存在"}

    # 查询该线索关联用户的评论（按昵称或手机号匹配）
    comments = []
    if clue.session_id:
        nickname = clue.author_nickname or clue.name or ""
        phone = clue.phone_decrypted or ""
        if nickname or phone:
            q = db.query(Comment).filter(Comment.session_id == clue.session_id)
            if nickname:
                matched = q.filter(Comment.nickname == nickname).all()
                comments = [{"content": c.content, "time": c.create_time, "has_lead": c.has_lead} for c in matched]
            if not comments and phone:
                matched = q.filter(Comment.phone == phone).all()
                comments = [{"content": c.content, "time": c.create_time, "has_lead": c.has_lead} for c in matched]

    # 获取备注（从raw_data或notes字段）
    notes = ""
    if clue.raw_data:
        try:
            raw = json.loads(clue.raw_data) if isinstance(clue.raw_data, str) else clue.raw_data
            notes = raw.get("notes", "") or raw.get("备注", "")
        except:
            pass

    return {
        "code": 0,
        "data": {
            "id": assignment.id,
            "clue_id": clue.clue_id,
            "name": clue.name or clue.author_nickname,
            "phone_decrypted": clue.phone_decrypted,
            "phone_masked": clue.phone_masked,
            "is_decrypted": clue.is_decrypted,
            "weixin": clue.weixin or clue.weixin_manual,
            "city_name": clue.city_name,
            "anchor_names": clue.anchor_names,
            "create_time_detail": clue.create_time_detail,
            "product_name": clue.product_name,
            "promotion_name": clue.promotion_name,
            "effective_state": clue.effective_state,
            "notes": notes,
            "comments": comments,
            "status": assignment.status,
            "feedback": assignment.feedback,
            "remark": assignment.remark,
        }
    }


@router.post("/clue-board/claim/{assignment_id}")
def claim_clue(assignment_id: int, data: dict, db: DBSession = Depends(get_db)):
    """领取线索"""
    from models import ClueAssignment
    assignment = db.query(ClueAssignment).get(assignment_id)
    if not assignment:
        return {"code": 404, "message": "分配记录不存在"}
    if assignment.status != "unclaimed":
        return {"code": 400, "message": "该线索已被领取"}
    assignment.status = "following"
    assignment.claimed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.commit()
    return {"code": 0, "message": "领取成功"}


@router.post("/clue-board/feedback/{assignment_id}")
def submit_feedback(assignment_id: int, data: dict, db: DBSession = Depends(get_db)):
    """提交线索反馈"""
    from models import ClueAssignment
    assignment = db.query(ClueAssignment).get(assignment_id)
    if not assignment:
        return {"code": 404, "message": "分配记录不存在"}
    assignment.feedback = data.get("feedback", "")
    assignment.remark = data.get("remark", "")
    if data.get("status"):
        assignment.status = data.get("status")
    db.commit()
    return {"code": 0, "message": "反馈已提交"}


# ===== 投流统计 =====
@router.get("/ad-plans/stats")
def ad_plans_stats(date_from: Optional[str] = None, date_to: Optional[str] = None,
                   account_id: Optional[int] = None, db: DBSession = Depends(get_db)):
    """投流计划效果统计"""
    from models import AdPlan, AdPlanSpend, AdAccount
    query = db.query(AdPlan)
    if account_id:
        query = query.filter(AdPlan.account_id == account_id)
    plans = query.all()
    result = []
    for p in plans:
        sq = db.query(AdPlanSpend).filter(AdPlanSpend.plan_id == p.id)
        if date_from: sq = sq.filter(AdPlanSpend.record_date >= date_from)
        if date_to: sq = sq.filter(AdPlanSpend.record_date <= date_to)
        spends = sq.all()
        total_spend = sum(s.spend_amount or 0 for s in spends)
        total_result = sum(s.result_count or 0 for s in spends)
        cost_per_result = round(total_spend / total_result, 2) if total_result > 0 else 0
        result.append({
            "plan_id": p.id, "plan_name": p.plan_name, "plan_douyin_id": p.plan_id,
            "account_name": p.account.account_name if p.account else None,
            "bid_price": p.bid_price, "status": p.status,
            "total_spend": total_spend, "total_result": total_result,
            "cost_per_result": cost_per_result,
            "spend_records": [{"date": s.record_date, "amount": s.spend_amount, "result": s.result_count} for s in spends[-30:]],
        })
    return {"code": 0, "data": result}

# ===== 评论洞察分析 API =====
@router.post("/comment-insight")
def receive_comment_insight(data: CommentInsightData, db: DBSession = Depends(get_db)):
    """接收油猴脚本收集的评论洞察数据"""
    from datetime import datetime
    
    # 解析时间
    try:
        start_dt = datetime.strptime(data.session_start, "%Y-%m-%d %H:%M:%S")
        end_dt = datetime.strptime(data.session_end, "%Y-%m-%d %H:%M:%S")
        duration_minutes = int((end_dt - start_dt).total_seconds() / 60)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"时间解析失败: {str(e)}")
    
    # 查找或创建Session
    session = db.query(Session).filter(Session.start_time == data.session_start).first()
    if not session:
        session = Session(
            start_time=data.session_start,
            end_time=data.session_end,
            duration_minutes=duration_minutes
        )
        db.add(session)
        db.flush()  # 获取session.id
    
    # 更新room_id和comment_summary
    if data.room_id:
        session.room_id = data.room_id
    if data.summary:
        session.comment_summary = data.summary
    
    # 批量写入comments（去重：同一场次+同nickname+同comment_time的评论跳过）
    comment_count = 0
    for c in data.comments:
        # 检查是否已存在（使用unique constraint）
        existing = db.query(Comment).filter(
            Comment.session_id == session.id,
            Comment.nickname == c.nickname,
            Comment.comment_time == c.comment_time
        ).first()
        
        if not existing:
            db.add(Comment(
                session_id=session.id,
                nickname=c.nickname,
                has_lead=c.has_lead,
                content=c.content,
                comment_time=c.comment_time
            ))
            comment_count += 1
        else:
            # 更新已存在的评论（如果有新信息）
            if c.content and not existing.content:
                existing.content = c.content
            if c.has_lead != existing.has_lead:
                existing.has_lead = c.has_lead
    
    try:
        db.commit()
        return {
            "code": 0,
            "message": "success",
            "session_id": session.id,
            "comment_count": comment_count,
            "total_comments": db.query(Comment).filter(Comment.session_id == session.id).count()
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"数据库写入失败: {str(e)}")

@router.get("/anchors/by-date")
def get_anchors_by_date(date: str = Query(..., description="日期，格式：2026-06-03"), 
                        db: DBSession = Depends(get_db)):
    """按日期查询主播时段（用于评论洞察分析的主播分组）"""
    from datetime import datetime as dt, timedelta
    from models import Anchor
    
    # 验证日期格式
    try:
        from datetime import datetime as dt
        dt.strptime(date, "%Y-%m-%d")
    except ValueError:
        return {"code": 400, "message": "date参数格式错误，应为YYYY-MM-DD"}
    
    # 查询该日期的所有场次
    next_date = (dt.strptime(date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    sessions = db.query(Session).filter(
        Session.start_time >= f"{date} 00:00:00",
        Session.start_time < f"{next_date} 00:00:00"
    ).all()
    
    if not sessions:
        return {"code": 0, "data": []}
    
    session_ids = [s.id for s in sessions]
    
    # 查询这些场次的主播时段
    anchors_data = []
    seen = set()  # 去重
    
    session_anchors = db.query(SessionAnchor).filter(
        SessionAnchor.session_id.in_(session_ids)
    ).all()
    
    for sa in session_anchors:
        anchor = db.query(Anchor).get(sa.anchor_id)
        if not anchor:
            continue
        
        # 去重key
        key = f"{anchor.name}_{sa.on_time}_{sa.off_time}"
        if key in seen:
            continue
        seen.add(key)
        
        anchors_data.append({
            "name": anchor.name,
            "on_time": sa.on_time,
            "off_time": sa.off_time,
            "anchor_order": sa.anchor_order,
            "gender": anchor.gender,
            "style": anchor.style
        })
    
    # 如果没有session_anchors数据，尝试从schedule_bindings获取
    if not anchors_data:
        binding = db.query(ScheduleBinding).filter(ScheduleBinding.date == date).first()
        if binding:
            anchor_mapping = json.loads(binding.anchor_mapping) if binding.anchor_mapping else {}
            anchor_ids = [int(v) for v in anchor_mapping.values() if v]
            anchors = db.query(Anchor).filter(Anchor.id.in_(anchor_ids)).all()
            
            # 获取排班方案的时段信息
            plan = db.query(SchedulePlan).get(binding.plan_id)
            if plan:
                slots = db.query(ScheduleSlot).filter(ScheduleSlot.plan_id == plan.id).order_by(ScheduleSlot.time_slot).all()
                
                for anchor in anchors:
                    # 查找该主播在排班中的位置
                    slot_key = None
                    for k, v in anchor_mapping.items():
                        if str(v) == str(anchor.id):
                            slot_key = k
                            break
                    
                    if slot_key:
                        # 解析slot_key获取时段
                        # slot_key格式可能是 "0_0" (time_slot_index_room_index)
                        parts = slot_key.split("_")
                        if len(parts) >= 2:
                            anchors_data.append({
                                "name": anchor.name,
                                "on_time": plan.start_time,
                                "off_time": plan.end_time,
                                "anchor_order": int(parts[1]) + 1 if len(parts) > 1 else None,
                                "gender": anchor.gender,
                                "style": anchor.style
                            })
    
    return {"code": 0, "data": anchors_data}
