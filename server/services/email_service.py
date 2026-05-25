import smtplib, json, logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from sqlalchemy import func
from sqlalchemy.orm import Session as DBSession
from jinja2 import Environment, FileSystemLoader
from models import Setting, Session, SessionMetric, Lead, Report, PrivateMessage, HighIntentUser
from utils import format_duration
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)
email_templates = Environment(loader=FileSystemLoader(str(Path(__file__).parent.parent / "templates" / "email")))

def get_email_config(db: DBSession) -> dict:
    keys = ["email_smtp_host","email_smtp_port","email_sender","email_password","email_receivers"]
    settings = db.query(Setting).filter(Setting.key.in_(keys)).all()
    config = {s.key: s.value for s in settings}
    if not config.get("email_sender"): raise Exception("邮箱未配置")
    config["email_receivers"] = json.loads(config.get("email_receivers","[]"))
    return config

def send_email(subject: str, html: str, config: dict, receivers: list):
    host = config.get("email_smtp_host","smtp.163.com"); port = int(config.get("email_smtp_port",465))
    sender = config["email_sender"]; password = config["email_password"]
    for receiver in receivers:
        try:
            msg = MIMEMultipart("alternative"); msg["Subject"] = subject; msg["From"] = sender; msg["To"] = receiver
            msg.attach(MIMEText(html,"html","utf-8"))
            with smtplib.SMTP_SSL(host, port) as server: server.login(sender, password); server.sendmail(sender, receiver, msg.as_string())
            logger.info(f"邮件发送成功: {receiver}")
        except Exception as e: logger.error(f"邮件发送失败 [{receiver}]: {e}")

def send_daily_report(db: DBSession, date: str = None):
    if not date: date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    config = get_email_config(db)
    next_date = (datetime.strptime(date,"%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    sessions = db.query(Session).filter(Session.start_time >= date+" 00:00:00", Session.start_time < next_date+" 00:00:00").all()
    if not sessions: return
    
    session_ids = [s.id for s in sessions]
    
    # 批量查询SessionMetric（防御None访问）
    metrics = db.query(SessionMetric).filter(SessionMetric.session_id.in_(session_ids)).all()
    metric_dict = {m.session_id: m for m in metrics}
    
    # 批量查询Lead count
    lead_counts = db.query(Lead.session_id, func.count(Lead.id)).filter(Lead.session_id.in_(session_ids)).group_by(Lead.session_id).all()
    lead_dict = {sid: cnt for sid, cnt in lead_counts}

    # 批量查询PrivateMessage count（私信人数）
    pm_counts = db.query(PrivateMessage.session_id, func.count(PrivateMessage.id)).filter(PrivateMessage.session_id.in_(session_ids)).group_by(PrivateMessage.session_id).all()
    pm_dict = {sid: cnt for sid, cnt in pm_counts}

    # 批量查询留资人数（PrivateMessage has_lead=True）
    lead_user_counts = db.query(PrivateMessage.session_id, func.count(PrivateMessage.id)).filter(PrivateMessage.session_id.in_(session_ids), PrivateMessage.has_lead == True).group_by(PrivateMessage.session_id).all()
    lead_user_dict = {sid: cnt for sid, cnt in lead_user_counts}

    # 批量查询HighIntentUser count（高意向人数）
    hi_counts = db.query(HighIntentUser.session_id, func.count(HighIntentUser.id)).filter(HighIntentUser.session_id.in_(session_ids)).group_by(HighIntentUser.session_id).all()
    hi_dict = {sid: cnt for sid, cnt in hi_counts}

    # 批量查询Report
    reports = db.query(Report).filter(Report.session_id.in_(session_ids), Report.report_type == "session").all()
    report_dict = {r.session_id: r for r in reports}
    
    # 计算动态阈值
    total_spend = sum(float((metric_dict.get(s.id).ad_spend or 0) if metric_dict.get(s.id) else 0) for s in sessions)
    total_leads = sum(lead_dict.get(s.id, 0) for s in sessions)
    avg_cost = total_spend / total_leads if total_leads > 0 else 0
    cost_threshold = avg_cost * 1.5
    
    session_data = []
    for s in sessions:
        m = metric_dict.get(s.id)
        lc = lead_dict.get(s.id, 0)
        spend = float(m.ad_spend or 0) if m else 0
        
        ai_report = report_dict.get(s.id)
        ai_summary = ai_report.content[:200] + "..." if ai_report and ai_report.content else None
        
        session_data.append({
            "start_time":s.start_time,"end_time":s.end_time,"duration":s.duration_minutes,
            "duration_text": format_duration(s.duration_minutes),
            "leads":lc,"spend":spend,"lead_cost":round(spend/lc,1) if lc>0 else 0,
            "pm_count": pm_dict.get(s.id, 0),
            "lead_users": lead_user_dict.get(s.id, 0),
            "high_intent": hi_dict.get(s.id, 0),
            "ai_summary": ai_summary
        })
    
    total_pm = sum(pm_dict.get(s.id, 0) for s in sessions)
    total_lead_users = sum(lead_user_dict.get(s.id, 0) for s in sessions)
    total_high_intent = sum(hi_dict.get(s.id, 0) for s in sessions)
    total_duration_text = format_duration(sum(s.duration_minutes or 0 for s in sessions))

    template = email_templates.get_template("daily_report.html")
    html = template.render(date=date, session_count=len(sessions), total_leads=total_leads, total_spend=round(total_spend,2),
        total_pm=total_pm, total_lead_users=total_lead_users, total_high_intent=total_high_intent, total_duration_text=total_duration_text,
        sessions=session_data, cost_threshold=cost_threshold)
    send_email(f"【直播核心数据】{date}", html, config, config["email_receivers"])

def get_push_config(db: DBSession) -> dict:
    """读取推送配置，空收件人数组回退到全局email_receivers"""
    keys = ["push_daily_enabled","push_daily_receivers","push_weekly_enabled","push_weekly_receivers","push_monthly_enabled","push_monthly_receivers","email_receivers"]
    settings = db.query(Setting).filter(Setting.key.in_(keys)).all()
    cfg = {s.key: s.value for s in settings}
    global_receivers = json.loads(cfg.get("email_receivers", "[]"))
    result = {}
    for ptype in ["daily", "weekly", "monthly"]:
        enabled = cfg.get(f"push_{ptype}_enabled", "false") == "true"
        receivers = json.loads(cfg.get(f"push_{ptype}_receivers", "[]"))
        if not receivers:
            receivers = global_receivers
        result[ptype] = {"enabled": enabled, "receivers": receivers}
    return result

def markdown_to_html(md: str) -> str:
    """基础Markdown转HTML（表格/标题/加粗/列表/分隔线）"""
    import re
    lines = md.split("\n")
    html_lines = []
    in_table = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("---"):
            html_lines.append("<hr>")
            continue
        if stripped.startswith("# "):
            html_lines.append(f"<h2>{stripped[2:]}</h2>")
        elif stripped.startswith("## "):
            html_lines.append(f"<h3>{stripped[3:]}</h3>")
        elif stripped.startswith("### "):
            html_lines.append(f"<h4>{stripped[4:]}</h4>")
        elif stripped.startswith("| ") and "|" in stripped[1:]:
            cells = [c.strip() for c in stripped.split("|")[1:-1]]
            if all(set(c) <= set("- :") for c in cells):
                continue
            tag = "th" if not in_table else "td"
            row = "".join(f"<{tag}>{c}</{tag}>" for c in cells)
            html_lines.append(f"<tr>{row}</tr>")
            in_table = True
        elif stripped.startswith("- "):
            html_lines.append(f"<li>{stripped[2:]}</li>")
        elif stripped:
            text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', stripped)
            html_lines.append(f"<p>{text}</p>")
        else:
            if in_table:
                in_table = False
            html_lines.append("")
    result = "\n".join(html_lines)
    result = result.replace("<tr>", "<table style='width:100%;border-collapse:collapse;margin:10px 0'><tr>", 1)
    if "</tr>" in result:
        last = result.rfind("</tr>")
        result = result[:last] + "</tr></table>" + result[last+5:]
    return result

def send_weekly_report(db: DBSession, week_str: str = None):
    """发送周报邮件：从Report表读取已生成的周报内容"""
    if not week_str:
        today = datetime.now()
        last_monday = today - timedelta(days=today.weekday() + 7)
        week_str = f"{last_monday.strftime('%Y')}-W{last_monday.isocalendar()[1]:02d}"
    config = get_email_config(db)
    push_cfg = get_push_config(db)
    receivers = push_cfg["weekly"]["receivers"]
    if not receivers:
        logger.warning("周报收件人为空，跳过发送")
        return
    report = db.query(Report).filter(Report.report_type == "weekly", Report.period == week_str).first()
    if not report:
        logger.warning(f"周报未生成: {week_str}")
        return
    content_html = markdown_to_html(report.content or "")
    template = email_templates.get_template("report_wrapper.html")
    html = template.render(title=f"直播周报 | {week_str}", content_html=content_html)
    send_email(f"【直播周报】{week_str}", html, config, receivers)
    logger.info(f"周报邮件已发送: {week_str}")

def send_monthly_report(db: DBSession, month_str: str = None):
    """发送月报邮件：从Report表读取已生成的月报内容"""
    if not month_str:
        month_str = (datetime.now() - timedelta(days=30)).strftime("%Y-%m")
    config = get_email_config(db)
    push_cfg = get_push_config(db)
    receivers = push_cfg["monthly"]["receivers"]
    if not receivers:
        logger.warning("月报收件人为空，跳过发送")
        return
    report = db.query(Report).filter(Report.report_type == "monthly", Report.period == month_str).first()
    if not report:
        logger.warning(f"月报未生成: {month_str}")
        return
    content_html = markdown_to_html(report.content or "")
    template = email_templates.get_template("report_wrapper.html")
    html = template.render(title=f"直播月报 | {month_str}", content_html=content_html)
    send_email(f"【直播月报】{month_str}", html, config, receivers)
    logger.info(f"月报邮件已发送: {month_str}")
