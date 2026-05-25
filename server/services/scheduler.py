from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from database import SessionLocal
from models import Session
import logging, time, shutil
from pathlib import Path
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()

def analyze_job():
    """每小时第5分钟: 自动分析未分析场次"""
    db = SessionLocal()
    try:
        unanalyzed = db.query(Session).filter(Session.analyzed == False).order_by(Session.start_time).all()
        if not unanalyzed: return
        logger.info(f"发现{len(unanalyzed)}个未分析场次")
        for s in unanalyzed:
            try:
                from services.ai_service import analyze_session
                analyze_session(db, s.id)
                logger.info(f"场次{s.id}分析完成")
                time.sleep(5)
            except Exception as e: logger.error(f"分析失败 {s.id}: {e}")
    finally: db.close()

def daily_report_job():
    """每天01:20: 生成日报(AI分析01:05后已完成)"""
    db = SessionLocal()
    try:
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        from services.report_service import generate_daily_report
        report_id = generate_daily_report(db, yesterday)
        logger.info(f"日报生成完成: {yesterday}, report_id={report_id}")
    except Exception as e: logger.error(f"日报生成失败: {e}")
    finally: db.close()

def weekly_report_job():
    """每周一02:00: 生成周报"""
    db = SessionLocal()
    try:
        from services.report_service import generate_weekly_report
        report_id = generate_weekly_report(db)
        logger.info(f"周报生成完成, report_id={report_id}")
    except Exception as e: logger.error(f"周报生成失败: {e}")
    finally: db.close()

def monthly_report_job():
    """每月1号03:00: 生成月报"""
    db = SessionLocal()
    try:
        from services.report_service import generate_monthly_report
        report_id = generate_monthly_report(db)
        logger.info(f"月报生成完成, report_id={report_id}")
    except Exception as e: logger.error(f"月报生成失败: {e}")
    finally: db.close()

def email_job():
    """每天01:30: 推送日报邮件(等待AI分析完成)，检查push_daily_enabled开关"""
    db = SessionLocal()
    try:
        from models import Setting
        enabled = db.query(Setting).filter(Setting.key == "push_daily_enabled").first()
        if enabled and enabled.value != "true":
            logger.info("日报推送已关闭，跳过")
            return
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        next_day = (datetime.strptime(yesterday, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
        
        for i in range(20):
            unanalyzed = db.query(Session).filter(
                Session.start_time >= yesterday + " 00:00:00",
                Session.start_time < next_day + " 00:00:00",
                Session.analyzed == False
            ).count()
            if unanalyzed == 0: break
            logger.info(f"等待AI分析完成，剩余{unanalyzed}场")
            time.sleep(30)
        
        from services.email_service import send_daily_report
        send_daily_report(db, yesterday)
        logger.info(f"日报邮件发送完成: {yesterday}")
    except Exception as e: logger.error(f"邮件推送失败: {e}")
    finally: db.close()

def weekly_email_job():
    """每周一02:30: 推送周报邮件，检查push_weekly_enabled开关"""
    db = SessionLocal()
    try:
        from models import Setting
        enabled = db.query(Setting).filter(Setting.key == "push_weekly_enabled").first()
        if enabled and enabled.value != "true":
            logger.info("周报推送已关闭，跳过")
            return
        from services.email_service import send_weekly_report
        send_weekly_report(db)
        logger.info("周报邮件推送完成")
    except Exception as e: logger.error(f"周报邮件推送失败: {e}")
    finally: db.close()

def monthly_email_job():
    """每月1号03:30: 推送月报邮件，检查push_monthly_enabled开关"""
    db = SessionLocal()
    try:
        from models import Setting
        enabled = db.query(Setting).filter(Setting.key == "push_monthly_enabled").first()
        if enabled and enabled.value != "true":
            logger.info("月报推送已关闭，跳过")
            return
        from services.email_service import send_monthly_report
        send_monthly_report(db)
        logger.info("月报邮件推送完成")
    except Exception as e: logger.error(f"月报邮件推送失败: {e}")
    finally: db.close()

_staleness_last_alert_time = None

def staleness_check_job():
    """每2小时: 检测数据停滞，超过12小时无新session时发送告警邮件"""
    global _staleness_last_alert_time
    db = SessionLocal()
    try:
        from sqlalchemy import func as sa_func
        latest_time = db.query(sa_func.max(Session.created_at)).scalar()
        if not latest_time:
            return  # 首次部署，无数据
        try:
            latest_dt = datetime.strptime(latest_time[:19], "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            return
        hours_since = (datetime.now() - latest_dt).total_seconds() / 3600
        if hours_since <= 12:
            return
        # 24小时内只发一次
        now = datetime.now()
        global _staleness_last_alert_time
        if _staleness_last_alert_time and (now - _staleness_last_alert_time).total_seconds() < 86400:
            return
        _staleness_last_alert_time = now
        from services.email_service import get_email_config, send_email
        import json as _json
        config = get_email_config(db)
        receivers = _json.loads(config.get("email_receivers", "[]"))
        html = f"""
        <h2>【直播数据告警】超过12小时无新数据更新</h2>
        <p>最后采集时间：<strong>{latest_time}</strong></p>
        <p>已停滞：<strong>{hours_since:.1f}小时</strong></p>
        <p>请检查浏览器是否正常运行、油猴脚本是否启用。</p>
        <hr/>
        <p style="color:#999;font-size:12px">此邮件由系统自动发送</p>
        """
        send_email("【直播数据告警】超过12小时无新数据更新", html, config, receivers)
        logger.info(f"数据停滞告警已发送: 停滞{hours_since:.1f}小时")
    except Exception as e:
        logger.error(f"停滞检测失败: {e}")
    finally:
        db.close()

def backup_job():
    """每天04:00: 数据库备份"""
    src = Path("data.db")
    if not src.exists(): return
    backup_dir = Path("backups"); backup_dir.mkdir(exist_ok=True)
    backup_name = f"data_{datetime.now().strftime('%Y%m%d')}.db"
    shutil.copy2(src, backup_dir / backup_name)
    for old in sorted(backup_dir.glob("data_*.db"))[:-7]: old.unlink()
    logger.info(f"备份完成: {backup_name}")

def init_scheduler():
    scheduler.add_job(analyze_job, CronTrigger(minute=5), id="analyze_job", replace_existing=True)
    scheduler.add_job(daily_report_job, CronTrigger(hour=1, minute=20), id="daily_report_job", replace_existing=True)
    scheduler.add_job(email_job, CronTrigger(hour=9, minute=0), id="email_job", replace_existing=True)
    scheduler.add_job(staleness_check_job, CronTrigger(hour='*/2', minute=10), id="staleness_check_job", replace_existing=True)
    scheduler.add_job(weekly_report_job, CronTrigger(day_of_week='mon', hour=2, minute=0), id="weekly_report_job", replace_existing=True)
    scheduler.add_job(weekly_email_job, CronTrigger(day_of_week='mon', hour=2, minute=30), id="weekly_email_job", replace_existing=True)
    scheduler.add_job(monthly_report_job, CronTrigger(day=1, hour=3, minute=0), id="monthly_report_job", replace_existing=True)
    scheduler.add_job(monthly_email_job, CronTrigger(day=1, hour=3, minute=30), id="monthly_email_job", replace_existing=True)
    scheduler.add_job(backup_job, CronTrigger(hour=4, minute=0), id="backup_job", replace_existing=True)
    scheduler.start(); logger.info("定时任务已启动 (9 jobs)")
