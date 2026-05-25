from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session as DBSession
from sqlalchemy import Integer as SAInt, Float as SAFloat, func
from database import get_db
from models import Session, SessionMetric, Lead, Comment, HighIntentUser, PrivateMessage, Report, Anchor, SessionAnchor, Deal, Setting
from utils import parse_number, parse_time, format_duration, format_duration_hms
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

class HighIntentItem(BaseModel):
    nickname: str; avatar_url: Optional[str] = None; comment_count: int = 0; stay_duration: Optional[str] = None; status: Optional[str] = None

class SessionData(BaseModel):
    version: str = "1.0"
    start_time: str; end_time: str; metrics: dict; leads: List[LeadItem] = []
    comments: List[CommentItem] = []; high_intent_users: List[HighIntentItem] = []
    review: Optional[dict] = None
    private_messages: Optional[list] = None

SUPPORTED_VERSIONS = ["1.0"]

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
        for ld in data.leads: db.add(Lead(session_id=session.id, **ld.model_dump()))
        for c in data.comments: db.add(Comment(session_id=session.id, **c.model_dump()))
        for h in data.high_intent_users: db.add(HighIntentUser(session_id=session.id, **h.model_dump()))
        if data.private_messages:
            for pm in data.private_messages:
                db.add(PrivateMessage(session_id=session.id, nickname=pm.get('nickname',''), douyin_id=pm.get('douyin_id',''), has_lead=pm.get('has_lead',False), last_message_time=pm.get('last_message_time',''), last_reply_time=pm.get('last_reply_time',''), pending_reply=pm.get('pending_reply',''), message_count=pm.get('message_count',0), ai_reply_count=pm.get('ai_reply_count',0)))
        db.commit(); return {"code": 0, "message": "success", "session_id": session.id}
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
def dashboard_api(time_range: str = Query("week", alias="range"), date: str = Query(None), db: DBSession = Depends(get_db)):
    import calendar
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
    total = query.count(); items = query.order_by(Lead.created_at.desc()).offset((page-1)*size).limit(size).all()
    all_q = db.query(Lead).join(Session)
    if keyword: all_q = all_q.filter(Lead.nickname.contains(keyword))
    if city: all_q = all_q.filter(Lead.city == city)
    paid = all_q.filter(Lead.ad_account != None, Lead.ad_account != '--').count()
    city_stats = db.query(Lead.city, func.count()).group_by(Lead.city).order_by(func.count().desc()).limit(10).all()
    return {"code":0,"data":{"items":[{"id":l.id,"lead_time":l.lead_time,"nickname":l.nickname,"city":l.city,"path":l.path,"ad_account":l.ad_account,"is_deal":l.is_deal,"is_valid":l.is_valid} for l in items],
        "total":total,"page":page,"size":size,"charts":{"source":{"paid":paid,"organic":total-paid},"city_top10":[{"city":c[0],"count":c[1]} for c in city_stats]}}}

@router.get("/anchors/stats")
def anchor_stats(date_from: Optional[str] = None, date_to: Optional[str] = None, db: DBSession = Depends(get_db)):
    anchors = db.query(Anchor).all()
    result = []
    for a in anchors:
        ids = [sa.session_id for sa in db.query(SessionAnchor).filter(SessionAnchor.anchor_id==a.id).all()]
        if not ids: continue
        sessions = db.query(Session).filter(Session.id.in_(ids))
        if date_from: sessions = sessions.filter(Session.start_time >= date_from)
        if date_to: sessions = sessions.filter(Session.start_time <= date_to)
        s_list = sessions.all(); s_ids = [s.id for s in s_list]
        leads = db.query(func.count(Lead.id)).filter(Lead.session_id.in_(s_ids)).scalar() or 0
        spend = db.query(func.sum(SessionMetric.ad_spend)).filter(SessionMetric.session_id.in_(s_ids)).scalar() or 0
        deals_count = db.query(func.count(Deal.id)).filter(Deal.session_id.in_(s_ids)).scalar() or 0
        deals_amount = db.query(func.sum(Deal.amount)).filter(Deal.session_id.in_(s_ids)).scalar() or 0
        deal_rate = round(deals_count/leads*100,1) if leads>0 else 0
        result.append({"anchor_id":a.id,"anchor_name":a.name,"session_count":len(s_list),"avg_leads":round(leads/len(s_list),1) if s_list else 0,"avg_spend":round(float(spend)/len(s_list),1) if s_list else 0,"total_leads":leads,"total_spend":float(spend or 0),"deal_count":deals_count,"deal_amount":float(deals_amount or 0),"deal_rate":deal_rate})
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
