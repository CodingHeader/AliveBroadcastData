#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
抖音来客线索获取脚本 v3.1
- 时间范围：今日 00:00:00 至 当前时间前 1 分钟
- 自动翻页获取所有线索（不限制条数）
- 手机号解密作为可选开关（默认关闭，不解密）
- 不保存文件，直接打印结果
"""

import requests
import json
import time
from typing import List, Dict, Any, Optional


# ========== 配置参数（请替换成你自己的真实信息）==========
CLIENT_KEY = "aw8ioetwuyy0dgxo"                # 应用 Key
CLIENT_SECRET = "2202bd430f9f447133b83f06e4c5e340"          # 应用 Secret
ACCOUNT_ID = "7565802820982065215"                # 抖音来客商家 ID

# 是否解密手机号（True=解密，消耗配额；False=不解密，保留原始加密值）
DECRYPT_PHONE = False                 # 默认不解密

END_TIME_OFFSET_SECONDS = 60          # 结束时间提前 1 分钟
# ====================================================


def get_access_token() -> Optional[str]:
    """获取 client_token（作为 access_token 使用）"""
    url = "https://open.douyin.com/oauth/client_token/"
    headers = {"Content-Type": "application/json"}
    payload = {
        "client_key": CLIENT_KEY,
        "client_secret": CLIENT_SECRET,
        "grant_type": "client_credential"
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("data", {}).get("error_code") == 0:
            token = data["data"]["access_token"]
            print(f"[SUCCESS] Access token 获取成功: {token[:20]}...")
            return token
        else:
            print(f"[ERROR] 获取 token 失败: {data}")
            return None
    except Exception as e:
        print(f"[ERROR] 请求 token 异常: {e}")
        return None


def query_clues(access_token: str, page: int = 1, page_size: int = 100) -> Optional[Dict[str, Any]]:
    """
    查询线索
    时间范围：今天 00:00:00 至 当前时间 - END_TIME_OFFSET_SECONDS
    """
    now = int(time.time())
    end_time = now - END_TIME_OFFSET_SECONDS          # 提前指定秒数
    # 今天 00:00:00
    start_time = int(time.mktime(time.strptime(time.strftime("%Y-%m-%d"), "%Y-%m-%d")))

    start_time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(start_time))
    end_time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(end_time))

    url = "https://open.douyin.com/goodlife/v1/open_api/crm/clue/query/"
    headers = {
        "Content-Type": "application/json",
        "access-token": access_token,
    }
    params = {
        "account_id": ACCOUNT_ID,
        "start_time": start_time_str,
        "end_time": end_time_str,
        "page": page,
        "page_size": page_size,
    }

    print(f"[INFO] 查询第 {page} 页，时间范围: {start_time_str} 至 {end_time_str}")

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        data_obj = result.get("data", {})
        if data_obj.get("error_code") == 0:
            return data_obj   # 包含 clue_data, page 等字段
        else:
            print(f"[ERROR] 查询线索失败: {data_obj}")
            return None
    except Exception as e:
        print(f"[ERROR] 查询线索异常: {e}")
        return None


def batch_decrypt_phone(access_token: str, encrypted_phones: List[str]) -> Dict[str, str]:
    """
    批量解密手机号（完整明文版，消耗解密配额）
    返回密文 -> 明文手机号的映射
    """
    if not encrypted_phones:
        return {}
    url = "https://open.douyin.com/goodlife/v1/open/common_biz/crypto/decrypt/batch/"
    headers = {
        "Content-Type": "application/json",
        "access-token": access_token,
    }
    payload = {
        "account_id": ACCOUNT_ID,
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
                    print(f"[WARNING] 解密失败: {item.get('cipher_text')} -> {item.get('error_msg')}")
            return mapping
        else:
            print(f"[ERROR] 批量解密失败: {data}")
            return {}
    except Exception as e:
        print(f"[ERROR] 解密接口异常: {e}")
        return {}


def process_all_clues():
    """主流程：拉取今日所有线索，根据 DECRYPT_PHONE 配置决定是否解密手机号，打印结果（不保存文件）"""
    token = get_access_token()
    if not token:
        return

    page = 1
    all_clues = []
    while True:
        clue_data = query_clues(token, page=page)
        if not clue_data:
            print(f"[WARNING] 第 {page} 页请求失败，停止拉取")
            break

        clue_list = clue_data.get("clue_data", [])
        pagination = clue_data.get("page", {})
        total = pagination.get("total", 0)

        if not clue_list:
            print(f"[INFO] 第 {page} 页无线索，拉取完成")
            break

        # 处理手机号：根据配置决定是否解密
        if DECRYPT_PHONE:
            # 收集当前页所有加密手机号
            enc_phones = [c.get("enc_telephone") for c in clue_list if c.get("enc_telephone")]
            if enc_phones:
                dec_map = batch_decrypt_phone(token, enc_phones)
            else:
                dec_map = {}
            # 将解密后的明文手机号附加到每个线索中
            for clue in clue_list:
                enc = clue.get("enc_telephone")
                clue["phone_number"] = dec_map.get(enc, enc)  # 如果解密失败则保留原始密文
        else:
            # 不解密：直接使用加密字段作为手机号
            for clue in clue_list:
                clue["phone_number"] = clue.get("enc_telephone", None)

        all_clues.extend(clue_list)
        print(f"[SUCCESS] 第 {page} 页获取 {len(clue_list)} 条线索，累计 {len(all_clues)} 条")

        # 翻页判断：如果当前页数量小于 page_size 或者已经拉完总数，则退出
        page_size = pagination.get("page_size", 100)
        if len(clue_list) < page_size or page * page_size >= total:
            break
        page += 1

    # 输出结果摘要
    print("\n" + "=" * 60)
    phone_status = "解密后明文" if DECRYPT_PHONE else "原始加密值（未解密）"
    print(f"今日（00:00 至 前1分钟）共拉取 {len(all_clues)} 条线索，手机号显示：{phone_status}")
    if all_clues:
        print("\n所有线索明细:")
        for idx, clue in enumerate(all_clues, 1):
            clue_id = clue.get('clue_id')
            phone = clue.get('phone_number')
            nickname = clue.get('author_nickname')
            create_time = clue.get('create_time_detail')
            # 如果手机号很长（加密值），打印时适当截断以便查看
            phone_display = phone if len(str(phone)) <= 30 else str(phone)[:30] + "..."
            print(f"[{idx}] 线索ID: {clue_id}, 手机号: {phone_display}, 昵称: {nickname}, 创建时间: {create_time}")
    else:
        print("今日暂无线索。")

    # 注意：不保存任何文件，仅控制台输出


if __name__ == "__main__":
    print("=" * 60)
    print("抖音来客线索获取脚本 v3.1")
    print(f"时间范围：今日 00:00:00 至 当前时间前 {END_TIME_OFFSET_SECONDS} 秒")
    print(f"手机号解密：{'开启' if DECRYPT_PHONE else '关闭'}")
    print("输出：直接打印在控制台，不保存文件")
    print("=" * 60)
    process_all_clues()