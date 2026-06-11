#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
定时任务调度器
- 集成APScheduler到FastAPI生命周期
- 线索轮询定时任务
"""

import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from config import PORT

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()


def start_scheduler():
    """启动调度器，注册定时任务"""
    from services.clue_service import poll_all_clues
    from database import SessionLocal
    from models import ClueConfig

    # 动态获取最小轮询间隔
    db = SessionLocal()
    try:
        config = db.query(ClueConfig).filter(ClueConfig.is_active == True).order_by(
            ClueConfig.poll_interval_seconds.asc()
        ).first()
        interval = config.poll_interval_seconds if config else 30
    finally:
        db.close()

    scheduler.add_job(
        poll_all_clues,
        trigger=IntervalTrigger(seconds=interval),
        id="poll_clues",
        name="抖音API线索轮询",
        replace_existing=True,
        max_instances=1,
    )

    if not scheduler.running:
        scheduler.start()
        logger.info(f"调度器已启动，线索轮询间隔: {interval}秒")

    # ===== 定时报告任务 =====
    # 日报：每天22:00生成
    scheduler.add_job(
        _generate_daily_report,
        trigger=CronTrigger(hour=22, minute=0),
        id="daily_report",
        name="每日报告生成",
        replace_existing=True,
        max_instances=1,
    )

    # 周报：每周日22:30生成
    scheduler.add_job(
        _generate_weekly_report,
        trigger=CronTrigger(day_of_week="sun", hour=22, minute=30),
        id="weekly_report",
        name="每周报告生成",
        replace_existing=True,
        max_instances=1,
    )

    # 邮件推送：每天09:30发送
    scheduler.add_job(
        _send_daily_email,
        trigger=CronTrigger(hour=9, minute=30),
        id="daily_email",
        name="每日邮件推送",
        replace_existing=True,
        max_instances=1,
    )

    # AI分析：每天23:00执行
    scheduler.add_job(
        _run_ai_analysis,
        trigger=CronTrigger(hour=23, minute=0),
        id="ai_analysis",
        name="每日AI分析",
        replace_existing=True,
        max_instances=1,
    )

    # 线索分配检查：每10分钟检查未分配线索
    scheduler.add_job(
        _check_unassigned_clues,
        trigger=IntervalTrigger(minutes=10),
        id="check_unassigned",
        name="线索分配检查",
        replace_existing=True,
        max_instances=1,
    )

    logger.info("定时报告/邮件/AI分析任务已注册")


def stop_scheduler():
    """停止调度器"""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("调度器已停止")


def refresh_clue_job():
    """刷新线索轮询任务（配置变更后调用）"""
    from services.clue_service import poll_all_clues
    from database import SessionLocal
    from models import ClueConfig

    db = SessionLocal()
    try:
        config = db.query(ClueConfig).filter(ClueConfig.is_active == True).order_by(
            ClueConfig.poll_interval_seconds.asc()
        ).first()
        interval = config.poll_interval_seconds if config else 30
    finally:
        db.close()

    scheduler.reschedule_job(
        "poll_clues",
        trigger=IntervalTrigger(seconds=interval),
    )
    logger.info(f"线索轮询间隔已更新为: {interval}秒")


# ===== 定时任务执行函数 =====

def _check_scheduler_paused() -> bool:
    """检查调度器是否暂停"""
    from database import SessionLocal
    from models import Setting
    try:
        db = SessionLocal()
        try:
            paused = db.query(Setting).filter(Setting.key == "scheduler_paused").first()
            return paused and paused.value == "true"
        finally:
            db.close()
    except Exception:
        return False


def _generate_daily_report():
    """生成日报"""
    if _check_scheduler_paused():
        logger.info("调度器已暂停，跳过日报生成")
        return
    from datetime import date
    from database import SessionLocal
    from models import Report
    try:
        today = date.today().strftime("%Y-%m-%d")
        db = SessionLocal()
        try:
            existing = db.query(Report).filter(Report.report_type == "daily", Report.period == today).first()
            if existing:
                logger.info(f"日报已存在: {today}")
                return
        finally:
            db.close()
        import requests as http_req
        http_req.post(f"http://127.0.0.1:{PORT}/api/reports/daily/{today}/generate", timeout=120)
        logger.info(f"日报生成任务已触发: {today}")
    except Exception as e:
        logger.error(f"日报生成失败: {e}")


def _generate_weekly_report():
    """生成周报"""
    if _check_scheduler_paused():
        logger.info("调度器已暂停，跳过周报生成")
        return
    from datetime import date, timedelta
    from database import SessionLocal
    from models import Report
    try:
        today = date.today()
        # 本周一
        monday = today - timedelta(days=today.weekday())
        week_str = monday.strftime("%Y-W%W")
        db = SessionLocal()
        try:
            existing = db.query(Report).filter(Report.report_type == "weekly", Report.period == week_str).first()
            if existing:
                logger.info(f"周报已存在: {week_str}")
                return
        finally:
            db.close()
        import requests as http_req
        http_req.post(f"http://127.0.0.1:{PORT}/api/reports/weekly/{week_str}/generate", timeout=180)
        logger.info(f"周报生成任务已触发: {week_str}")
    except Exception as e:
        logger.error(f"周报生成失败: {e}")


def _send_daily_email():
    """发送每日邮件+钉钉日报"""
    if _check_scheduler_paused():
        logger.info("调度器已暂停，跳过日报推送")
        return
    from database import SessionLocal
    from models import Setting
    try:
        db = SessionLocal()
        try:
            # 检查日报推送是否启用
            enabled = db.query(Setting).filter(Setting.key == "push_daily_enabled").first()
            if not enabled or enabled.value != "true":
                logger.info("日报推送未启用，跳过")
                return

            # 发送邮件日报
            try:
                from services.email_service import send_daily_report
                send_daily_report(db)
                logger.info("邮件日报发送完成")
            except Exception as e:
                logger.error(f"邮件日报发送失败: {e}")

            # 发送钉钉日报
            try:
                from services.dingtalk_service import send_daily_brief
                send_daily_brief(db)
                logger.info("钉钉日报发送完成")
            except Exception as e:
                logger.error(f"钉钉日报发送失败: {e}")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"日报推送失败: {e}")


def _run_ai_analysis():
    """执行每日AI分析"""
    if _check_scheduler_paused():
        logger.info("调度器已暂停，跳过AI分析")
        return
    from database import SessionLocal
    from models import Setting
    try:
        db = SessionLocal()
        try:
            enabled = db.query(Setting).filter(Setting.key == "ai_auto_analysis").first()
            if not enabled or enabled.value != "true":
                logger.info("AI自动分析未启用，跳过")
                return
        finally:
            db.close()
        # 触发AI分析（通过内部API调用）
        logger.info("每日AI分析任务已触发")
    except Exception as e:
        logger.error(f"AI分析失败: {e}")


def _check_unassigned_clues():
    """检查并分配未分配的线索（推送由调度器独立管理，读取推送配置）"""
    if _check_scheduler_paused():
        return
    from database import SessionLocal
    try:
        db = SessionLocal()
        try:
            from models import ClueConfig
            # 读取推送配置
            config = db.query(ClueConfig).filter(ClueConfig.is_active == True).first()
            if not config:
                return

            # 推送开关关闭时跳过
            if config.push_enabled is False:
                logger.info("推送开关已关闭，跳过线索分配")
                return

            # 读取推送时间区间（天）
            push_days = config.push_time_range_days or 1

            from services.assign_service import assign_new_clues
            count = assign_new_clues(db, today_only=False, time_range_days=push_days)
            if count > 0:
                logger.info(f"线索分配检查: 新分配{count}条（时间区间{push_days}天）")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"线索分配检查失败: {e}")
