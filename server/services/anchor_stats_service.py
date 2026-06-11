"""
主播收入统计服务 - 统一管理所有统计逻辑
包含：场次明细、主播场次顺序、关联场次判定、薪资计算、Excel导出
"""
from typing import Optional, List, Dict, Any
from sqlalchemy import func, case
from collections import defaultdict
from models import Session, Anchor, SessionAnchor, Lead, Comment, SessionMetric, PrivateMessage


def _calc_session_period(on_time: str) -> str:
    """根据上播时间计算关联场次
    06:00-12:00 → 上午场
    12:00-18:00 → 下午场
    18:00-06:00 → 晚间场
    """
    try:
        hour = int(on_time.split(":")[0])
        if 6 <= hour < 12:
            return "上午场"
        elif 12 <= hour < 18:
            return "下午场"
        else:
            return "晚间场"
    except Exception:
        return "未知"


def _calc_duration_minutes(on_time: str, off_time: str, fallback_minutes: int = 0) -> int:
    """计算上播时长(分钟)，支持跨天"""
    try:
        on_parts = on_time.split(":")
        off_parts = off_time.split(":")
        on_mins = int(on_parts[0]) * 60 + int(on_parts[1])
        off_mins = int(off_parts[0]) * 60 + int(off_parts[1])
        if off_mins < on_mins:
            off_mins += 24 * 60
        return off_mins - on_mins
    except Exception:
        return fallback_minutes


def get_comprehensive_stats(
    db,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    anchor_id: Optional[int] = None,
    anchor_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    获取综合分析统计数据（完整版）
    返回：
    - daily_detail: 每日/每场次/每主播的详细统计
    - daily_aggregated: 按(日期,主播)聚合的每日统计
    - anchor_summary: 按主播汇总
    - overall_summary: 全局汇总
    """
    # ===== 查询所有主播排班数据 =====
    query = db.query(
        func.substr(Session.start_time, 1, 10).label('date'),
        Session.id.label('session_id'),
        Session.start_time.label('session_start'),
        Session.end_time.label('session_end'),
        Session.duration_minutes,
        Anchor.id.label('anchor_id'),
        Anchor.name.label('anchor_name'),
        Anchor.is_parttime,
        Anchor.gender,
        Anchor.style,
        SessionAnchor.on_time,
        SessionAnchor.off_time,
        SessionAnchor.anchor_order,
    ).join(
        SessionAnchor, Session.id == SessionAnchor.session_id
    ).join(
        Anchor, SessionAnchor.anchor_id == Anchor.id
    )

    if date_from:
        query = query.filter(Session.start_time >= date_from)
    if date_to:
        query = query.filter(Session.start_time <= date_to + " 23:59:59")
    if anchor_id:
        query = query.filter(Anchor.id == anchor_id)
    if anchor_name:
        query = query.filter(Anchor.name == anchor_name)

    rows = query.order_by(Session.start_time, SessionAnchor.anchor_order).all()

    if not rows:
        return {
            "daily_detail": [],
            "daily_aggregated": [],
            "anchor_summary": [],
            "overall_summary": {},
        }

    # ===== 预加载场次级别的线索和评论统计 =====
    session_ids = list(set(r.session_id for r in rows))

    # 评论统计（按session_id查询后，按主播时段过滤）
    comment_rows = db.query(
        Comment.session_id,
        Comment.comment_time,
        Comment.has_lead,
        Comment.is_consultation,
    ).filter(Comment.session_id.in_(session_ids)).all()
    # 按 session_id 分组
    comment_by_session = defaultdict(list)
    for c in comment_rows:
        comment_by_session[c.session_id].append(c)

    # 场次指标 (用于评论数)
    metric_rows = db.query(
        SessionMetric.session_id,
        SessionMetric.comment_count,
    ).filter(SessionMetric.session_id.in_(session_ids)).all()
    metric_map = {mr.session_id: mr for mr in metric_rows}

    # 私信统计（按session_id查询后，按主播时段过滤）
    pm_rows = db.query(
        PrivateMessage.session_id,
        PrivateMessage.last_message_time,
        PrivateMessage.has_lead,
    ).filter(PrivateMessage.session_id.in_(session_ids)).all()
    pm_by_session = defaultdict(list)
    for pm in pm_rows:
        pm_by_session[pm.session_id].append(pm)

    # ===== 生成逐场次明细 =====
    daily_detail = []
    for r in rows:
        date_str = r.date or ""

        # 直播时长
        if r.on_time and r.off_time:
            dur_mins = _calc_duration_minutes(r.on_time, r.off_time, r.duration_minutes or 0)
        else:
            dur_mins = r.duration_minutes or 0
            if not r.on_time:
                on_t = r.session_start[11:16] if r.session_start else ""
            if not r.off_time:
                off_t = r.session_end[11:16] if r.session_end else ""

        on_t = r.on_time or (r.session_start[11:16] if r.session_start else "")
        off_t = r.off_time or (r.session_end[11:16] if r.session_end else "")

        session_period = _calc_session_period(on_t)

        # 线索统计（按时间精确匹配：只取留资时间落在主播时段内的线索）
        from utils import time_in_range, extract_hhmm
        session_leads = db.query(Lead).filter(Lead.session_id == r.session_id).all()
        on_t = r.on_time or (r.session_start[11:16] if r.session_start else "")
        off_t = r.off_time or (r.session_end[11:16] if r.session_end else "")
        total_leads = ad_leads = natural_leads = effective_leads = 0
        if on_t and off_t and session_leads:
            for l in session_leads:
                hhmm = extract_hhmm(l.lead_time)
                if hhmm and time_in_range(on_t, off_t, hhmm):
                    total_leads += 1
                    if l.ad_account is not None and l.ad_account != '--':
                        ad_leads += 1
                    else:
                        natural_leads += 1
                    if l.is_valid:
                        effective_leads += 1
        elif session_leads:
            total_leads = len(session_leads)
            for l in session_leads:
                if l.ad_account is not None and l.ad_account != '--':
                    ad_leads += 1
                else:
                    natural_leads += 1
                if l.is_valid:
                    effective_leads += 1

        # 评论统计（按主播时段过滤：只取评论时间落在主播时段内的评论）
        session_comments = comment_by_session.get(r.session_id, [])
        comment_count = 0
        comment_leads = 0
        consultation_count = 0
        if on_t and off_t and session_comments:
            for c in session_comments:
                ct_hhmm = extract_hhmm(c.comment_time)
                if ct_hhmm and time_in_range(on_t, off_t, ct_hhmm):
                    comment_count += 1
                    if c.has_lead:
                        comment_leads += 1
                    if c.is_consultation:
                        consultation_count += 1
        else:
            # 无时段信息时全部计入（降级兼容）
            for c in session_comments:
                comment_count += 1
                if c.has_lead:
                    comment_leads += 1
                if c.is_consultation:
                    consultation_count += 1
        # 如果没有评论记录但有场次指标，使用指标数据
        if comment_count == 0:
            mr = metric_map.get(r.session_id)
            comment_count = mr.comment_count if mr else 0

        # 私信统计（按主播时段过滤：只取私信时间落在主播时段内的私信）
        session_pms = pm_by_session.get(r.session_id, [])
        pm_count = 0
        pm_lead_count = 0
        if on_t and off_t and session_pms:
            for pm in session_pms:
                pt_hhmm = extract_hhmm(pm.last_message_time)
                if pt_hhmm and time_in_range(on_t, off_t, pt_hhmm):
                    pm_count += 1
                    if pm.has_lead:
                        pm_lead_count += 1
        else:
            for pm in session_pms:
                pm_count += 1
                if pm.has_lead:
                    pm_lead_count += 1

        daily_detail.append({
            "date": date_str,
            "session_id": r.session_id,
            "session_start": r.session_start,
            "session_end": r.session_end,
            "anchor_id": r.anchor_id,
            "anchor_name": r.anchor_name,
            "anchor_gender": r.gender,
            "anchor_style": r.style,
            "is_parttime": r.is_parttime,
            "on_time": on_t,
            "off_time": off_t,
            "anchor_order": r.anchor_order,              # 主播场次（每天第几场）
            "session_period": session_period,             # 关联场次
            "duration_minutes": dur_mins,
            "duration_hours": round(dur_mins / 60.0, 2),
            "total_leads": total_leads,
            "ad_leads": ad_leads,
            "natural_leads": natural_leads,
            "effective_leads": effective_leads,
            "comment_count": comment_count,
            "comment_leads": comment_leads,
            "consultation_count": consultation_count,
            "comment_conversion_rate": round(comment_leads / consultation_count * 100, 1) if consultation_count > 0 else 0,
            "pm_count": pm_count,
            "pm_lead_count": pm_lead_count,
            "pm_conversion_rate": round(pm_lead_count / pm_count * 100, 1) if pm_count > 0 else 0,
        })

    # ===== 全场次编号（每天统一编号）=====
    session_counter = {}
    for d in daily_detail:
        if d["date"] not in session_counter:
            session_counter[d["date"]] = 0
        session_counter[d["date"]] += 1
        d["session_order"] = session_counter[d["date"]]  # 直播场次

    # ===== 按(日期, 主播)聚合 =====
    agg = defaultdict(lambda: {
        "periods": [], "duration_minutes": 0, "sessions": set(),
        "total_leads": 0, "ad_leads": 0, "natural_leads": 0, "effective_leads": 0,
        "comment_count": 0, "comment_leads": 0, "consultation_count": 0,
        "pm_count": 0, "pm_lead_count": 0,
    })

    for d in daily_detail:
        key = (d["date"], d["anchor_name"])
        a = agg[key]
        a["duration_minutes"] += d["duration_minutes"]
        a["sessions"].add(d["session_id"])
        a["total_leads"] += d["total_leads"]
        a["ad_leads"] += d["ad_leads"]
        a["natural_leads"] += d["natural_leads"]
        a["effective_leads"] += d["effective_leads"]
        a["comment_count"] += d["comment_count"]
        a["comment_leads"] += d["comment_leads"]
        a["consultation_count"] += d.get("consultation_count", 0)
        a["pm_count"] += d["pm_count"]
        a["pm_lead_count"] += d["pm_lead_count"]
        if d["on_time"] and d["off_time"]:
            a["periods"].append(f"{d['on_time']}-{d['off_time']}")

    daily_aggregated = []
    for (date, name), a in agg.items():
        daily_aggregated.append({
            "date": date,
            "anchor_name": name,
            "periods_display": "/".join(a["periods"]),
            "duration_minutes": a["duration_minutes"],
            "total_leads": a["total_leads"],
            "ad_leads": a["ad_leads"],
            "natural_leads": a["natural_leads"],
            "effective_leads": a["effective_leads"],
            "comment_count": a["comment_count"],
            "comment_leads": a["comment_leads"],
            "consultation_count": a["consultation_count"],
            "comment_conversion_rate": round(a["comment_leads"] / a["consultation_count"] * 100, 1) if a["consultation_count"] > 0 else 0,
            "pm_count": a["pm_count"],
            "pm_lead_count": a["pm_lead_count"],
            "session_count": len(a["sessions"]),
        })
    daily_aggregated.sort(key=lambda x: (x["date"], x["anchor_name"]))

    # ===== 按主播汇总 =====
    summ = defaultdict(lambda: {
        "total_minutes": 0, "total_leads": 0, "ad_leads": 0,
        "natural_leads": 0, "effective_leads": 0,
        "comment_count": 0, "comment_leads": 0, "consultation_count": 0,
        "pm_count": 0, "pm_lead_count": 0,
        "days": set(), "sessions": set(), "is_parttime": 0,
        "gender": "", "style": "",
    })

    for d in daily_detail:
        s = summ[d["anchor_name"]]
        s["total_minutes"] += d["duration_minutes"]
        s["total_leads"] += d["total_leads"]
        s["ad_leads"] += d["ad_leads"]
        s["natural_leads"] += d["natural_leads"]
        s["effective_leads"] += d["effective_leads"]
        s["comment_count"] += d["comment_count"]
        s["comment_leads"] += d["comment_leads"]
        s["consultation_count"] += d.get("consultation_count", 0)
        s["pm_count"] += d["pm_count"]
        s["pm_lead_count"] += d["pm_lead_count"]
        s["days"].add(d["date"])
        s["sessions"].add(d["session_id"])
        s["is_parttime"] = d["is_parttime"]
        s["gender"] = d["anchor_gender"] or ""
        s["style"] = d["anchor_style"] or ""

    anchor_summary = [{
        "anchor_name": name,
        "total_hours": round(d["total_minutes"] / 60.0, 1),
        "total_minutes": d["total_minutes"],
        "total_leads": d["total_leads"],
        "ad_leads": d["ad_leads"],
        "natural_leads": d["natural_leads"],
        "effective_leads": d["effective_leads"],
        "comment_count": d["comment_count"],
        "comment_leads": d["comment_leads"],
        "consultation_count": d["consultation_count"],
        "comment_conversion_rate": round(d["comment_leads"] / d["consultation_count"] * 100, 1) if d["consultation_count"] > 0 else 0,
        "pm_count": d["pm_count"],
        "pm_lead_count": d["pm_lead_count"],
        "pm_conversion_rate": round(d["pm_lead_count"] / d["pm_count"] * 100, 1) if d["pm_count"] > 0 else 0,
        "days": len(d["days"]),
        "sessions": len(d["sessions"]),
        "is_parttime": d["is_parttime"],
        "gender": d["gender"],
        "style": d["style"],
    } for name, d in summ.items()]
    anchor_summary.sort(key=lambda x: -x["total_hours"])

    # ===== 全局汇总 =====
    overall = {
        "total_hours": sum(s["total_hours"] for s in anchor_summary),
        "total_leads": sum(s["total_leads"] for s in anchor_summary),
        "total_ad_leads": sum(s["ad_leads"] for s in anchor_summary),
        "total_natural_leads": sum(s["natural_leads"] for s in anchor_summary),
        "total_comments": sum(s["comment_count"] for s in anchor_summary),
        "total_comment_leads": sum(s["comment_leads"] for s in anchor_summary),
        "total_pm": sum(s["pm_count"] for s in anchor_summary),
        "total_pm_leads": sum(s["pm_lead_count"] for s in anchor_summary),
        "anchor_count": len(anchor_summary),
        "total_days": len(set(d["date"] for d in daily_detail)),
    }

    return {
        "daily_detail": daily_detail,
        "daily_aggregated": daily_aggregated,
        "anchor_summary": anchor_summary,
        "overall_summary": overall,
    }


def calc_anchor_salary(
    base_rate: float = 40.0,          # 底薪 元/小时
    lead_commission: float = 0,        # 线索 元/条
    ad_commission: float = 0,          # 广告流线索 元/条
    natural_commission: float = 0,     # 自然流线索 元/条
    anchor_summary: List[Dict] = None,
) -> List[Dict]:
    """计算主播月薪"""
    if not anchor_summary:
        return []
    results = []
    for s in anchor_summary:
        base_pay = s["total_hours"] * base_rate
        commission = (s["total_leads"] * lead_commission +
                      s["ad_leads"] * ad_commission +
                      s["natural_leads"] * natural_commission)
        results.append({
            **s,
            "base_salary": round(base_pay, 2),
            "commission": round(commission, 2),
            "total_salary": round(base_pay + commission, 2),
            "base_rate": base_rate,
            "lead_commission": lead_commission,
            "ad_commission": ad_commission,
            "natural_commission": natural_commission,
        })
    return results


def generate_excel_data(daily_detail: List[Dict], anchor_summary: List[Dict], params: Dict) -> List[Dict]:
    """生成Excel导出用的二维表格数据
    格式：[日期, 直播场次, 主播场次, 关联主播, 关联场次, 直播开始-结束, 主播上播-下播, 评论数, 评论获客, 获客率, 自然流留资, 广告流留资, 总留资, 私信数, 私信获客]
    """
    rows = []
    for d in daily_detail:
        consultation_count = d.get("consultation_count", d["comment_count"])
        comment_rate = round(d["comment_leads"] / consultation_count * 100, 1) if consultation_count > 0 else 0
        rows.append({
            "日期": d["date"],
            "直播场次": d["session_order"],
            "主播场次": d["anchor_order"],
            "关联主播": d["anchor_name"],
            "关联场次": d["session_period"],
            "直播开始时间-结束时间": f"{d['session_start'][:16] if d['session_start'] else ''} - {d['session_end'][:16] if d['session_end'] else ''}",
            "主播上播时间-下播时间": f"{d['on_time']}-{d['off_time']}" if d.get('on_time') and d.get('off_time') else "",
            "评论数": d["comment_count"],
            "评论获客数": d["comment_leads"],
            "获客率": f"{comment_rate}%",
            "自然流留资数": d["natural_leads"],
            "广告流留资数": d["ad_leads"],
            "总留资数": d["total_leads"],
            "私信数": d["pm_count"],
            "私信获客数": d["pm_lead_count"],
        })
    return rows