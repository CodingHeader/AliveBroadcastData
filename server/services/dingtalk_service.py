#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
钉钉推送服务
- 发送线索分配通知到钉钉群
- @对应招生老师
"""

import time
import hmac
import hashlib
import base64
import urllib.parse
import requests
import json
import logging

logger = logging.getLogger(__name__)


def _generate_sign(secret: str) -> tuple:
    """生成钉钉机器人签名"""
    timestamp = str(round(time.time() * 1000))
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(secret.encode("utf-8"), string_to_sign.encode("utf-8"),
                         digestmod=hashlib.sha256).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
    return timestamp, sign


def send_dingtalk_message(webhook_url: str, secret: str, content: str, at_mobiles: list = None) -> bool:
    """发送钉钉消息"""
    try:
        timestamp, sign = _generate_sign(secret)
        final_url = f"{webhook_url}&timestamp={timestamp}&sign={sign}"

        message = {
            "msgtype": "text",
            "text": {"content": content},
            "at": {
                "atMobiles": at_mobiles or [],
                "isAtAll": False,
            }
        }

        resp = requests.post(final_url, headers={"Content-Type": "application/json"},
                             data=json.dumps(message), timeout=10)
        result = resp.json()
        if result.get("errcode") == 0:
            logger.info("钉钉消息发送成功")
            return True
        else:
            logger.error(f"钉钉消息发送失败: {result}")
            return False
    except Exception as e:
        logger.error(f"钉钉消息发送异常: {e}")
        return False


def send_clue_notification(team, employee_id: int, clue, db) -> bool:
    """发送线索分配通知"""
    from models import RecruitEmployee

    if not team.dingtalk_webhook:
        logger.warning(f"团队[{team.name}]未配置钉钉webhook，跳过推送")
        return False

    employee = db.query(RecruitEmployee).get(employee_id)
    if not employee:
        return False

    # 构建消息内容
    # 钉钉推送使用明文电话（已解密的phone_decrypted），不使用加密的phone_masked
    phone = clue.phone_decrypted or clue.phone_masked or "未提供"
    anchor_info = clue.anchor_names or "未知"
    city = clue.city_name or ""
    create_time = clue.create_time_detail or clue.lead_time or ""

    content = f"【新线索分配】\n"
    content += f"分配老师：{employee.name}\n"
    content += f"电话：{phone}\n"
    content += f"主播：{anchor_info}\n"
    if city:
        content += f"城市：{city}\n"
    if create_time:
        content += f"留资时间：{create_time}\n"
    content += f"领取源：腾讯文档 / http://36.134.158.50:12306/clue-board\n"
    content += f"密码：hd1994\n"
    content += f"\n请及时领取并跟进！"

    at_mobiles = []
    if employee.dingtalk_phone:
        at_mobiles.append(employee.dingtalk_phone)

    return send_dingtalk_message(team.dingtalk_webhook, team.dingtalk_secret or "", content, at_mobiles)


def send_daily_brief(db) -> bool:
    """发送每日直播战绩通报到钉钉（使用第一个有webhook的团队）"""
    from models import RecruitTeam, Session, SessionAnchor, Anchor, SessionMetric
    from sqlalchemy import func
    from datetime import datetime, timedelta

    # 找到有webhook的团队
    team = db.query(RecruitTeam).filter(
        RecruitTeam.is_active == True,
        RecruitTeam.dingtalk_webhook != None,
        RecruitTeam.dingtalk_webhook != "",
    ).first()
    if not team:
        logger.warning("无配置钉钉webhook的活跃团队，跳过日报推送")
        return False

    # 查询前一天的数据
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    today = datetime.now().strftime("%Y-%m-%d")

    sessions = db.query(Session).filter(
        Session.start_time >= yesterday + " 00:00:00",
        Session.start_time < today + " 00:00:00",
    ).all()

    if not sessions:
        logger.info(f"{yesterday}无直播数据，跳过日报推送")
        return False

    session_ids = [s.id for s in sessions]

    # 查询主播信息
    sa_rows = db.query(SessionAnchor).filter(SessionAnchor.session_id.in_(session_ids)).all()
    anchor_ids = list(set(sa.anchor_id for sa in sa_rows if sa.anchor_id))
    anchors = db.query(Anchor).filter(Anchor.id.in_(anchor_ids)).all() if anchor_ids else []
    anchor_names = "、".join([a.name for a in anchors]) if anchors else "无"

    # 查询直播时段
    time_ranges = []
    for s in sessions:
        start = s.start_time[11:16] if s.start_time and len(s.start_time) >= 16 else "?"
        end = s.end_time[11:16] if s.end_time and len(s.end_time) >= 16 else "?"
        time_ranges.append(f"{start}——{end}")
    time_str = "，".join(time_ranges) if time_ranges else "无"

    # 查询线索量（Lead表）
    from models import Lead
    lead_count = db.query(func.count(Lead.id)).filter(Lead.session_id.in_(session_ids)).scalar() or 0

    # 查询投流金额（SessionMetric.ad_spend）
    metrics = db.query(SessionMetric).filter(SessionMetric.session_id.in_(session_ids)).all()
    total_spend = sum(float(m.ad_spend or 0) for m in metrics)

    # 格式化日期（如6.7）
    date_display = f"{int(yesterday[5:7])}.{int(yesterday[8:10])}"

    # 构建消息
    content = f"📌{date_display}日直播战绩通报\n\n"
    content += f"👩🏼‍💻直播人员：{anchor_names}\n"
    content += f"⏰直播时段：{time_str}\n"
    content += f"📈今日线索量：{lead_count}\n"
    content += f"💰今日投流金额：{round(total_spend, 2)}\n"
    content += f"🎉今日转化量：0"

    return send_dingtalk_message(team.dingtalk_webhook, team.dingtalk_secret or "", content)
