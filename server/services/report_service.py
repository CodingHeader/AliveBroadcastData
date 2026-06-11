from sqlalchemy import func
from sqlalchemy.orm import Session as DBSession
from models import Session, SessionMetric, Lead, Report, Deal, SessionAnchor, Anchor
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

def _change(current, previous) -> str:
    if previous == 0: return "——" if current > 0 else "0%"
    pct = (current - previous) / previous * 100
    return f"+{pct:.1f}%" if pct >= 0 else f"{pct:.1f}%"

def generate_daily_report(db: DBSession, date: str) -> int:
    next_date = (datetime.strptime(date,"%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    sessions = db.query(Session).filter(Session.start_time >= date+" 00:00:00", Session.start_time < next_date+" 00:00:00").order_by(Session.start_time).all()
    if not sessions: return None
    ids = [s.id for s in sessions]
    total_leads = db.query(func.count(Lead.id)).filter(Lead.session_id.in_(ids)).scalar() or 0
    total_spend = db.query(func.sum(SessionMetric.ad_spend)).filter(SessionMetric.session_id.in_(ids)).scalar() or 0
    total_deals = db.query(func.count(Deal.id)).filter(Deal.session_id.in_(ids)).scalar() or 0
    total_deal_amount = db.query(func.sum(Deal.amount)).filter(Deal.session_id.in_(ids)).scalar() or 0
    deal_rate = total_deals/total_leads*100 if total_leads>0 else 0
    avg_cost = f"¥{total_spend/total_leads:.1f}" if total_leads > 0 else "--"
    md = f"# 直播日报 | {date}\n\n## 总览\n| 指标 | 数值 |\n|------|------|\n| 场次 | {len(sessions)} |\n| 线索 | {total_leads} |\n| 消耗 | ¥{total_spend:.2f} |\n| 线索成本 | {avg_cost} |\n| 成单 | {total_deals} |\n| 成单金额 | ¥{total_deal_amount or 0:.2f} |\n| 成单率 | {deal_rate:.1f}% |\n\n## 场次明细\n"
    metrics = db.query(SessionMetric).filter(SessionMetric.session_id.in_(ids)).all()
    metric_dict = {m.session_id: m for m in metrics}
    lead_counts = db.query(Lead.session_id, func.count(Lead.id)).filter(Lead.session_id.in_(ids)).group_by(Lead.session_id).all()
    lead_dict = {sid: cnt for sid, cnt in lead_counts}
    reports = db.query(Report).filter(Report.session_id.in_(ids), Report.report_type == "session").all()
    report_dict = {r.session_id: r for r in reports}
    for i,s in enumerate(sessions,1):
        m = metric_dict.get(s.id)
        lc = lead_dict.get(s.id, 0)
        spend = float(m.ad_spend or 0) if m else 0
        cost = f"¥{spend/lc:.1f}" if lc > 0 else "--"
        md += f"\n### 第{i}场 {s.start_time[11:16]}~{s.end_time[11:16]}\n- 时长: {s.duration_minutes}min\n- 线索: {lc}\n- 消耗: ¥{spend:.2f}\n- 线索成本: {cost}\n"
        if m: md += f"- 最高在线: {m.max_online}\n- 人均观看: {m.avg_watch_duration}\n"
        ai = report_dict.get(s.id)
        if ai: md += f"\n**AI分析:** {ai.content[:300]}...\n"
        md += "\n---\n"
    existing = db.query(Report).filter(Report.report_type=="daily", Report.period==date).first()
    if existing: existing.content = md; existing.generated_at = datetime.now().isoformat(); db.commit(); return existing.id
    r = Report(report_type="daily", period=date, content=md, generated_at=datetime.now().isoformat()); db.add(r); db.commit(); return r.id

def generate_weekly_report(db: DBSession, week_str: str = None) -> int:
    today = datetime.now()
    last_monday = today - timedelta(days=today.weekday() + 7)
    last_sunday = last_monday + timedelta(days=6)
    date_from = last_monday.strftime("%Y-%m-%d")
    date_to = last_sunday.strftime("%Y-%m-%d")
    week_str = f"{last_monday.strftime('%Y')}-W{last_monday.isocalendar()[1]:02d}"
    
    sessions = db.query(Session).filter(Session.start_time >= date_from, Session.start_time <= date_to+" 23:59:59").all()
    if not sessions: return None
    ids = [s.id for s in sessions]
    total_leads = db.query(func.count(Lead.id)).filter(Lead.session_id.in_(ids)).scalar() or 0
    total_spend = db.query(func.sum(SessionMetric.ad_spend)).filter(SessionMetric.session_id.in_(ids)).scalar() or 0
    
    prev_from = (datetime.strptime(date_from,"%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")
    prev_to = (datetime.strptime(date_to,"%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")
    prev_sessions = db.query(Session).filter(Session.start_time >= prev_from, Session.start_time <= prev_to+" 23:59:59").all()
    prev_ids = [s.id for s in prev_sessions]
    prev_leads = db.query(func.count(Lead.id)).filter(Lead.session_id.in_(prev_ids)).scalar() or 0
    prev_spend = db.query(func.sum(SessionMetric.ad_spend)).filter(SessionMetric.session_id.in_(prev_ids)).scalar() or 0
    
    deals = db.query(Deal).filter(Deal.deal_time >= date_from, Deal.deal_time <= date_to).all()
    total_deal_amount = sum(d.amount for d in deals)
    roi = round(total_deal_amount/total_spend, 2) if total_spend > 0 else 0
    
    md = f"# 周报 | {week_str} ({date_from} ~ {date_to})\n\n## 周度总览\n\n"
    md += f"| 指标 | 本周 | 上周 | 环比 |\n|------|------|------|------|\n"
    md += f"| 场次 | {len(sessions)} | {len(prev_sessions)} | {_change(len(sessions),len(prev_sessions))} |\n"
    md += f"| 线索 | {total_leads} | {prev_leads} | {_change(total_leads,prev_leads)} |\n"
    md += f"| 消耗 | ¥{total_spend:.0f} | ¥{prev_spend:.0f} | {_change(total_spend,prev_spend)} |\n"
    md += f"| 成单 | {len(deals)}笔 / ¥{total_deal_amount:.0f} | - | - |\n"
    md += f"| ROI | {roi} | - | - |\n\n## 主播表现\n\n"
    
    anchors = db.query(Anchor).all()
    for a in anchors:
        a_ids = [sa.session_id for sa in db.query(SessionAnchor).filter(SessionAnchor.anchor_id==a.id, SessionAnchor.session_id.in_(ids)).all()]
        if a_ids:
            a_leads = db.query(func.count(Lead.id)).filter(Lead.session_id.in_(a_ids)).scalar() or 0
            md += f"- **{a.name}**: {len(a_ids)}场, {a_leads}线索\n"
    
    # AI周度分析
    try:
        from openai import OpenAI
        from models import Setting
        ai_keys = ["ai_api_key","ai_base_url","ai_model","ai_system_prompt"]
        ai_settings = db.query(Setting).filter(Setting.key.in_(ai_keys)).all()
        ai_config = {s.key: s.value for s in ai_settings}
        if ai_config.get("ai_api_key"):
            client = OpenAI(api_key=ai_config["ai_api_key"], base_url=ai_config.get("ai_base_url","https://api.openai.com/v1"))
            ai_prompt = f"请基于以下一周直播数据汇总，给出周度趋势分析和下周优化建议：\n\n{md}"
            response = client.chat.completions.create(
                model=ai_config.get("ai_model","gpt-4o"),
                messages=[{"role":"system","content":ai_config.get("ai_system_prompt","")},{"role":"user","content":ai_prompt}],
                timeout=120
            )
            md += f"\n## AI周度分析\n\n{response.choices[0].message.content}\n"
    except Exception as e:
        logger.warning(f"周报AI分析失败: {e}")
        md += "\n## AI周度分析\n\n（生成失败，请手动触发）\n"
    
    existing = db.query(Report).filter(Report.report_type=="weekly", Report.period==week_str).first()
    if existing: existing.content = md; existing.generated_at = datetime.now().isoformat(); db.commit(); return existing.id
    r = Report(report_type="weekly", period=week_str, content=md, generated_at=datetime.now().isoformat()); db.add(r); db.commit(); return r.id

def generate_monthly_report(db: DBSession, month_str: str = None) -> int:
    if not month_str:
        last_month = datetime.now().replace(day=1) - timedelta(days=1)
        month_str = last_month.strftime("%Y-%m")
    year, month = month_str.split("-")
    year, month = int(year), int(month)
    date_from = f"{month_str}-01"
    date_to_exclusive = f"{year+1}-01-01" if month==12 else f"{year}-{month+1:02d}-01"
    
    sessions = db.query(Session).filter(Session.start_time >= date_from, Session.start_time < date_to_exclusive).all()
    if not sessions: return None
    ids = [s.id for s in sessions]
    total_leads = db.query(func.count(Lead.id)).filter(Lead.session_id.in_(ids)).scalar() or 0
    total_spend = db.query(func.sum(SessionMetric.ad_spend)).filter(SessionMetric.session_id.in_(ids)).scalar() or 0
    deals = db.query(Deal).filter(Deal.deal_time >= date_from, Deal.deal_time < date_to_exclusive).all()
    total_deal_amount = sum(d.amount for d in deals)
    roi = round(total_deal_amount/total_spend, 2) if total_spend > 0 else 0
    avg_leads_per_session = round(total_leads / len(sessions), 1) if sessions else 0
    avg_spend_per_session = round(total_spend / len(sessions), 1) if sessions else 0
    
    # Previous month comparison
    prev_last_day = datetime(year, month, 1) - timedelta(days=1)
    prev_from = prev_last_day.replace(day=1).strftime("%Y-%m-%d")
    prev_to_exclusive = f"{year}-{month:02d}-01"
    prev_sessions = db.query(Session).filter(Session.start_time >= prev_from, Session.start_time < prev_to_exclusive).all()
    prev_ids = [s.id for s in prev_sessions]
    prev_leads = db.query(func.count(Lead.id)).filter(Lead.session_id.in_(prev_ids)).scalar() or 0
    prev_spend = db.query(func.sum(SessionMetric.ad_spend)).filter(SessionMetric.session_id.in_(prev_ids)).scalar() or 0
    prev_deals = db.query(Deal).filter(Deal.deal_time >= prev_from, Deal.deal_time < prev_to_exclusive).all()
    prev_deal_amount = sum(d.amount for d in prev_deals)
    prev_roi = round(prev_deal_amount/prev_spend, 2) if prev_spend > 0 else 0
    
    # Week-by-week breakdown
    weeks = []
    for week_num in range(5):
        week_start = datetime(year, month, 1) + timedelta(days=week_num*7)
        if week_start.month != month: break
        week_end = min(week_start + timedelta(days=6), datetime(year, month, 28) + timedelta(days=3))
        if week_end.month > month: week_end = datetime(year, month, 28) + timedelta(days=3)
        ws = week_start.strftime("%Y-%m-%d")
        we = week_end.strftime("%Y-%m-%d") + " 23:59:59"
        w_sessions = db.query(Session).filter(Session.start_time >= ws, Session.start_time <= we).all()
        w_ids = [s.id for s in w_sessions]
        w_leads = db.query(func.count(Lead.id)).filter(Lead.session_id.in_(w_ids)).scalar() or 0
        w_spend = db.query(func.sum(SessionMetric.ad_spend)).filter(SessionMetric.session_id.in_(w_ids)).scalar() or 0
        w_deals = db.query(Deal).filter(Deal.deal_time >= ws, Deal.deal_time <= we).all()
        w_amount = sum(d.amount for d in w_deals)
        if w_sessions:
            weeks.append({"week": f"W{week_num+1}", "sessions": len(w_sessions), "leads": w_leads, "spend": w_spend, "deals": len(w_deals), "amount": w_amount})
    
    # Top sessions by leads (批量查询优化)
    metrics = db.query(SessionMetric).filter(SessionMetric.session_id.in_(ids)).all()
    metric_dict = {m.session_id: m for m in metrics}
    lead_counts = db.query(Lead.session_id, func.count(Lead.id)).filter(Lead.session_id.in_(ids)).group_by(Lead.session_id).all()
    lead_dict = {sid: cnt for sid, cnt in lead_counts}
    top_sessions = []
    for s in sessions:
        lc = lead_dict.get(s.id, 0)
        m = metric_dict.get(s.id)
        spend = float(m.ad_spend or 0) if m else 0
        top_sessions.append({"time": f"{s.start_time[5:16]}~{s.end_time[11:16]}", "leads": lc, "spend": spend, "max_online": m.max_online if m else 0})
    top_sessions.sort(key=lambda x: x["leads"], reverse=True)
    
    # Anchor performance
    anchors_data = []
    anchors = db.query(Anchor).all()
    for a in anchors:
        a_ids = [sa.session_id for sa in db.query(SessionAnchor).filter(SessionAnchor.anchor_id==a.id, SessionAnchor.session_id.in_(ids)).all()]
        if a_ids:
            a_leads = db.query(func.count(Lead.id)).filter(Lead.session_id.in_(a_ids)).scalar() or 0
            a_spend = db.query(func.sum(SessionMetric.ad_spend)).filter(SessionMetric.session_id.in_(a_ids)).scalar() or 0
            a_deals = db.query(Deal).filter(Deal.session_id.in_(a_ids)).all()
            a_amount = sum(d.amount for d in a_deals)
            anchors_data.append({"name": a.name, "sessions": len(a_ids), "leads": a_leads, "spend": a_spend or 0, "deals": len(a_deals), "amount": a_amount})
    anchors_data.sort(key=lambda x: x["leads"], reverse=True)
    
    # AI suggestions from session reports
    ai_reports = db.query(Report).filter(Report.report_type=="session", Report.period >= date_from, Report.period < date_to_exclusive).all()
    suggestions = []
    for r in ai_reports:
        if r.content and "建议" in r.content:
            idx = r.content.find("建议")
            suggestions.append(r.content[idx:idx+100].strip())
    unique_suggestions = list(dict.fromkeys(suggestions))[:5]
    
    # Build markdown
    md = f"# 月报 | {month_str}\n\n## 月度总览\n\n"
    md += f"| 指标 | 本月 | 上月 | 环比 |\n|------|------|------|------|\n"
    md += f"| 场次 | {len(sessions)} | {len(prev_sessions)} | {_change(len(sessions),len(prev_sessions))} |\n"
    md += f"| 线索 | {total_leads} | {prev_leads} | {_change(total_leads,prev_leads)} |\n"
    md += f"| 消耗 | ¥{total_spend:.0f} | ¥{prev_spend:.0f} | {_change(total_spend,prev_spend)} |\n"
    md += f"| 场均线索 | {avg_leads_per_session} | {round(prev_leads/len(prev_sessions),1) if prev_sessions else 0} | - |\n"
    md += f"| 场均消耗 | ¥{avg_spend_per_session:.0f} | ¥{round(prev_spend/len(prev_sessions),0) if prev_sessions else 0} | - |\n"
    md += f"| 成单 | {len(deals)}笔 / ¥{total_deal_amount:.0f} | {len(prev_deals)}笔 / ¥{prev_deal_amount:.0f} | {_change(len(deals),len(prev_deals))} |\n"
    md += f"| ROI | {roi} | {prev_roi} | {_change(roi,prev_roi) if prev_roi else '-'} |\n\n"
    
    if weeks:
        md += "## 周度趋势\n\n| 周次 | 场次 | 线索 | 消耗 | 成单 | 金额 |\n|------|------|------|------|------|------|\n"
        for w in weeks:
            md += f"| {w['week']} | {w['sessions']} | {w['leads']} | ¥{w['spend']:.0f} | {w['deals']} | ¥{w['amount']:.0f} |\n"
        md += "\n"
    
    if top_sessions:
        md += "## 场次排行 (Top 5 by 线索)\n\n| 时间 | 线索 | 消耗 | 最高在线 |\n|------|------|------|----------|\n"
        for t in top_sessions[:5]:
            md += f"| {t['time']} | {t['leads']} | ¥{t['spend']:.0f} | {t['max_online']} |\n"
        md += "\n"
    
    if anchors_data:
        md += "## 主播表现\n\n| 主播 | 场次 | 线索 | 消耗 | 成单 | 金额 |\n|------|------|------|------|------|------|\n"
        for a in anchors_data:
            md += f"| {a['name']} | {a['sessions']} | {a['leads']} | ¥{a['spend']:.0f} | {a['deals']} | ¥{a['amount']:.0f} |\n"
        md += "\n"
    
    if unique_suggestions:
        md += "## 优化建议\n\n"
        for i, s in enumerate(unique_suggestions, 1):
            md += f"{i}. {s}\n"
        md += "\n"
    
    existing = db.query(Report).filter(Report.report_type=="monthly", Report.period==month_str).first()
    if existing: existing.content = md; existing.generated_at = datetime.now().isoformat(); db.commit(); return existing.id
    r = Report(report_type="monthly", period=month_str, content=md, generated_at=datetime.now().isoformat()); db.add(r); db.commit(); return r.id
