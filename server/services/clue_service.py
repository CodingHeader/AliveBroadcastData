#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
抖音开放平台API线索服务
- 后台常驻：通过APScheduler定时轮询
- 多账号矩阵号支持：遍历ClueConfig表中所有活跃账号
- clue_id去重：拉取后先查数据库，已存在则跳过
- 按需解密：仅对新线索调用解密接口，配额用完保留加密值
- 线索→主播关联：通过create_time_detail匹配排班表
"""

import requests
import json
import time
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


def get_access_token(client_key: str, client_secret: str) -> Optional[str]:
    """获取client_token"""
    url = "https://open.douyin.com/oauth/client_token/"
    headers = {"Content-Type": "application/json"}
    payload = {
        "client_key": client_key,
        "client_secret": client_secret,
        "grant_type": "client_credential"
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("data", {}).get("error_code") == 0:
            return data["data"]["access_token"]
        else:
            logger.error(f"获取token失败: {data}")
            return None
    except Exception as e:
        logger.error(f"请求token异常: {e}")
        return None


def query_clues(access_token: str, account_id: str, page: int = 1, page_size: int = 100,
                start_time: str = None, end_time: str = None) -> Optional[Dict[str, Any]]:
    """查询线索列表"""
    now = int(time.time())
    if not end_time:
        end_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now - 60))
    if not start_time:
        start_time = time.strftime("%Y-%m-%d 00:00:00", time.localtime(now))

    url = "https://open.douyin.com/goodlife/v1/open_api/crm/clue/query/"
    headers = {
        "Content-Type": "application/json",
        "access-token": access_token,
    }
    params = {
        "account_id": account_id,
        "start_time": start_time,
        "end_time": end_time,
        "page": page,
        "page_size": page_size,
    }
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        data_obj = result.get("data", {})
        if data_obj.get("error_code") == 0:
            return data_obj
        else:
            logger.error(f"查询线索失败: {data_obj}")
            return None
    except Exception as e:
        logger.error(f"查询线索异常: {e}")
        return None


def batch_decrypt_phone(access_token: str, account_id: str, encrypted_phones: List[str]) -> Dict[str, str]:
    """批量解密手机号，返回密文→明文映射"""
    if not encrypted_phones:
        return {}
    url = "https://open.douyin.com/goodlife/v1/open/common_biz/crypto/decrypt/batch/"
    headers = {
        "Content-Type": "application/json",
        "access-token": access_token,
    }
    payload = {
        "account_id": account_id,
        "cipher_texts": encrypted_phones,
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if data.get("data", {}).get("error_code") == 0:
            results = data["data"].get("results", [])
            mapping = {}
            for item in results:
                if item.get("is_success"):
                    mapping[item["cipher_text"]] = item.get("plain_text", "")
                else:
                    logger.warning(f"解密失败: {item.get('cipher_text')} -> {item.get('error_msg')}")
            return mapping
        else:
            logger.error(f"批量解密失败: {data}")
            return {}
    except Exception as e:
        logger.error(f"解密接口异常: {e}")
        return {}


def _time_in_range(on_time: str, off_time: str, target_time: str) -> bool:
    """判断时间是否在主播时段内（支持跨天）"""
    try:
        target_min = int(target_time[:2]) * 60 + int(target_time[3:5])
        on_min = int(on_time[:2]) * 60 + int(on_time[3:])
        off_min = int(off_time[:2]) * 60 + int(off_time[3:])
        if off_min <= on_min:
            off_min += 24 * 60
        if target_min < on_min:
            target_min += 24 * 60
        return on_min <= target_min < off_min
    except (ValueError, IndexError, TypeError):
        return False


def match_anchor(create_time_detail: str, db) -> Optional[int]:
    """根据线索创建时间匹配主播的实际直播时段
    优先从 SessionAnchor（实际场次）匹配 on_time/off_time 区间
    回退到 ScheduleBinding 排班方案匹配
    """
    if not create_time_detail:
        return None
    try:
        from models import SessionAnchor, Session, Anchor
        clue_dt = datetime.strptime(create_time_detail, "%Y-%m-%d %H:%M:%S")
        date_str = clue_dt.strftime("%Y-%m-%d")
        time_str = clue_dt.strftime("%H:%M")

        # 方式1：从 SessionAnchor 按 on_time/off_time 区间匹配（最高优先级）
        sessions = db.query(Session).filter(
            Session.start_time >= f"{date_str} 00:00:00",
            Session.start_time < f"{date_str} 23:59:59"
        ).all()
        for session in sessions:
            sa_list = db.query(SessionAnchor).filter(
                SessionAnchor.session_id == session.id
            ).all()
            for sa in sa_list:
                if sa.on_time and sa.off_time and _time_in_range(sa.on_time, sa.off_time, time_str):
                    return sa.anchor_id

        # 方式2：从 ScheduleBinding 排班方案匹配（备选）
        binding = db.query(ScheduleBinding).filter(ScheduleBinding.date == date_str).first()
        if binding:
            plan = db.query(SchedulePlan).filter(SchedulePlan.id == binding.plan_id).first()
            if plan:
                slot = db.query(ScheduleSlot).filter(
                    ScheduleSlot.plan_id == plan.id,
                    ScheduleSlot.time_slot <= time_str
                ).order_by(ScheduleSlot.time_slot.desc()).first()
                if slot and slot.anchor_slot:
                    anchor_mapping = json.loads(binding.anchor_mapping) if binding.anchor_mapping else {}
                    if anchor_mapping:
                        anchor_id_str = anchor_mapping.get(str(slot.anchor_slot))
                        if anchor_id_str:
                            return int(anchor_id_str)
                    # 方式3：按anchor_slot序号映射
                    anchors = db.query(Anchor).order_by(Anchor.is_parttime, Anchor.id).all()
                    if slot.anchor_slot and slot.anchor_slot <= len(anchors):
                        return anchors[slot.anchor_slot - 1].id

        return None
    except Exception as e:
        logger.warning(f"匹配主播失败: {e}")
        return None


def poll_clues_for_account(config, db, triggered_by="scheduler"):
    """为单个账号拉取线索"""
    from models import ApiClue, PollLog

    # 获取有效的商家ID：优先使用关联直播账户的merchant_id
    def _get_account_id(cfg):
        if cfg.ad_account_id and hasattr(cfg, 'ad_account') and cfg.ad_account:
            return cfg.ad_account.merchant_id or cfg.account_id
        return cfg.account_id

    start_ms = int(time.time() * 1000)
    token = get_access_token(config.client_key, config.client_secret)
    account_id = _get_account_id(config)
    if not token:
        logger.error(f"账号{config.account_name}获取token失败，跳过")
        log = PollLog(
            account_name=config.account_name, account_id=account_id,
            status="error", message="获取token失败",
            triggered_by=triggered_by, duration_ms=int(time.time() * 1000) - start_ms,
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        db.add(log); db.commit()
        return 0, 0

    page = 1
    new_count = 0
    decrypt_count = 0

    while True:
        clue_data = query_clues(token, account_id, page=page)
        if not clue_data:
            break

        clue_list = clue_data.get("clue_data", [])
        pagination = clue_data.get("page", {})

        if not clue_list:
            break

        # 去重：批量查询已有clue_id
        clue_ids = [c.get("clue_id") for c in clue_list if c.get("clue_id")]
        existing_ids = set()
        if clue_ids:
            existing_records = db.query(ApiClue.clue_id).filter(
                ApiClue.clue_id.in_(clue_ids)
            ).all()
            existing_ids = {r[0] for r in existing_records}

        # 过滤出新线索
        new_clues = [c for c in clue_list if c.get("clue_id") and c["clue_id"] not in existing_ids]

        if new_clues and config.decrypt_enabled:
            # 按需解密：收集新线索的加密手机号
            enc_phones = [c.get("enc_telephone") for c in new_clues if c.get("enc_telephone")]
            dec_map = {}
            if enc_phones:
                dec_map = batch_decrypt_phone(token, account_id, enc_phones)
                decrypt_count += len([v for v in dec_map.values() if v])
        else:
            dec_map = {}

        # 入库
        for clue in new_clues:
            clue_id = clue.get("clue_id")
            enc_phone = clue.get("enc_telephone")
            phone_dec = dec_map.get(enc_phone) if enc_phone else None

            anchor_id = match_anchor(clue.get("create_time_detail"), db)
            anchor_name = None
            if anchor_id:
                from models import Anchor
                anchor_obj = db.query(Anchor).get(anchor_id)
                if anchor_obj:
                    anchor_name = anchor_obj.name

            record = ApiClue(
                clue_id=clue_id,
                account_id=account_id,
                enc_telephone=enc_phone,
                phone_decrypted=phone_dec,
                is_decrypted=bool(phone_dec),
                name=clue.get("name"),
                create_time_detail=clue.get("create_time_detail"),
                modify_time=clue.get("modify_time"),
                author_nickname=clue.get("author_nickname"),
                author_douyin_id=clue.get("author_douyin_id"),
                author_role=clue.get("author_role"),
                advertiser_id=clue.get("advertiser_id"),
                advertiser_name=clue.get("advertiser_name"),
                ad_type=clue.get("ad_type"),
                promotion_id=clue.get("promotion_id"),
                promotion_name=clue.get("promotion_name"),
                product_id=clue.get("product_id"),
                product_name=clue.get("product_name"),
                product_type=clue.get("product_type"),
                content_id=clue.get("content_id"),
                video_id=clue.get("video_id"),
                flow_entrance=clue.get("flow_entrance"),
                flow_type=clue.get("flow_type"),
                leads_page=clue.get("leads_page"),
                clue_type=clue.get("clue_type"),
                clue_intention=clue.get("clue_intention"),
                convert_status=clue.get("convert_status"),
                allocation_status=clue.get("allocation_status"),
                effective_state=clue.get("effective_state"),
                is_private_clue=clue.get("is_private_clue", 0),
                auto_city_name=clue.get("auto_city_name"),
                auto_province_name=clue.get("auto_province_name"),
                province_name=clue.get("province_name"),
                city_name=clue.get("city_name"),
                county_name=clue.get("county_name"),
                tel_addr=clue.get("tel_addr"),
                ad_id=clue.get("ad_id"),
                search_bid_word=clue.get("search_bid_word"),
                gender=clue.get("gender"),
                age=clue.get("age"),
                weixin=clue.get("weixin"),
                tags=json.dumps(clue.get("tags"), ensure_ascii=False) if isinstance(clue.get("tags"), (list, dict)) else clue.get("tags"),
                system_tags=json.dumps(clue.get("system_tags"), ensure_ascii=False) if isinstance(clue.get("system_tags"), (list, dict)) else clue.get("system_tags"),
                ext_info=json.dumps(clue.get("ext_info"), ensure_ascii=False) if isinstance(clue.get("ext_info"), (list, dict)) else clue.get("ext_info"),
                anchor_id=anchor_id,
                anchor_names=anchor_name,
                raw_data=json.dumps(clue, ensure_ascii=False),
            )
            db.add(record)
            new_count += 1

        db.commit()

        # 翻页
        page_size = pagination.get("page_size", 100)
        total = pagination.get("total", 0)
        if len(clue_list) < page_size or page * page_size >= total:
            break
        page += 1

    logger.info(f"账号{config.account_name}: 新增{new_count}条线索, 解密{decrypt_count}条")

    # 写入采集日志
    log = PollLog(
        account_name=config.account_name, account_id=account_id,
        status="success", new_count=new_count, decrypt_count=decrypt_count,
        total_count=new_count, message=f"新增{new_count}条线索, 解密{decrypt_count}条",
        triggered_by=triggered_by, duration_ms=int(time.time() * 1000) - start_ms,
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )
    db.add(log); db.commit()

    return new_count, decrypt_count


def poll_all_clues(triggered_by="scheduler"):
    """定时任务入口：遍历所有活跃账号拉取线索"""
    from database import SessionLocal
    from models import ClueConfig, PollLog, Setting

    db = SessionLocal()
    try:
        # 检查调度器是否暂停（手动触发不受影响）
        if triggered_by == "scheduler":
            paused = db.query(Setting).filter(Setting.key == "scheduler_paused").first()
            if paused and paused.value == "true":
                logger.info("调度器已暂停，跳过自动线索轮询")
                return

        configs = db.query(ClueConfig).filter(ClueConfig.is_active == True).all()
        if not configs:
            logger.info("无活跃的API线索账号配置，跳过")
            return

        total_new = 0
        total_decrypt = 0
        for config in configs:
            try:
                new_count, decrypt_count = poll_clues_for_account(config, db, triggered_by=triggered_by)
                total_new += new_count
                total_decrypt += decrypt_count
            except Exception as e:
                logger.error(f"账号{config.account_name}拉取异常: {e}")
                db.rollback()
                # 写入异常日志
                err_log = PollLog(
                    account_name=config.account_name, account_id=account_id,
                    status="error", message=str(e)[:500],
                    triggered_by=triggered_by,
                    created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                )
                db.add(err_log); db.commit()

        logger.info(f"线索轮询完成: 共新增{total_new}条, 解密{total_decrypt}条")

        # 采集与推送已解耦：采集只负责入库，推送由调度器独立管理
    finally:
        db.close()
