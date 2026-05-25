from openai import OpenAI
import openai
from sqlalchemy.orm import Session as DBSession
from models import Session, SessionMetric, Lead, Comment, HighIntentUser, Report, Setting, Anchor, SessionAnchor
from datetime import datetime

def get_ai_config(db: DBSession) -> dict:
    keys = ["ai_api_key", "ai_base_url", "ai_model", "ai_system_prompt", "ai_user_prompt_template"]
    settings = db.query(Setting).filter(Setting.key.in_(keys)).all()
    config = {s.key: s.value for s in settings}
    if not config.get("ai_api_key"): raise Exception("AI API Key未配置")
    return config

def analyze_session(db: DBSession, session_id: int) -> int:
    config = get_ai_config(db)
    session = db.query(Session).get(session_id)
    metrics = db.query(SessionMetric).filter(SessionMetric.session_id == session_id).first()
    leads = db.query(Lead).filter(Lead.session_id == session_id).all()
    comments = db.query(Comment).filter(Comment.session_id == session_id).all()
    hiu = db.query(HighIntentUser).filter(HighIntentUser.session_id == session_id).all()
    
    # 构建主播信息
    session_anchors = db.query(SessionAnchor).filter(SessionAnchor.session_id == session_id).all()
    anchor_ids = [sa.anchor_id for sa in session_anchors]
    anchors = db.query(Anchor).filter(Anchor.id.in_(anchor_ids)).all() if anchor_ids else []
    anchors_text = f"本场主播：{', '.join([a.name for a in anchors])}" if anchors else "本场主播：未关联"
    
    FIELD_LABELS = {
        "exposure_count":"曝光人数","cumulative_viewers":"累计观看人数","exposure_entry_rate":"曝光进入率",
        "gmv":"直播间成交金额","order_count":"订单人数","marketing_orders":"营销订单数",
        "phone_submits":"填手机号","ad_spend":"营销消耗(元)","total_leads":"全场景留资人数",
        "order_cost":"订单成本","lead_cost":"线索成本","new_followers":"涨粉量",
        "comment_count":"评论次数","comment_users":"评论人数","watch_gt_1min":">1分钟观看次数",
        "avg_watch_duration":"人均观看时长","fan_stay_duration":"粉丝停留时长","max_online":"最高在线人数",
        "interaction_count":"互动次数","interaction_users":"互动人数","interaction_rate":"互动率",
        "fan_club_joins":"加粉丝团人数","fan_club_rate":"加团率","component_clicks":"风车房子点击次数",
        "click_rate":"点击率","gift_amount":"打赏金额","gift_count":"打赏次数",
        "comment_rate":"评论率","lead_conversion_rate":"线索转化率","like_rate":"点赞率",
        "like_users":"点赞人数","like_count":"点赞次数","product_exposure":"商品曝光次数",
        "product_clicks":"商品点击次数","product_click_rate":"商品点击率","follow_rate":"关注率",
        "share_count":"分享次数","share_users":"分享人数","share_rate":"分享率","gmv_per_mille":"千次观看GMV",
        "fan_ratio":"粉丝占比","exposure_times":"曝光次数","view_count":"直播间观看次数",
        "avg_online":"平均在线人数","realtime_online":"实时在线人数"
    }
    
    # 构建指标文本
    metrics_text = ""
    if metrics:
        for c in metrics.__table__.columns:
            if c.name in ('id','session_id','created_at'): continue
            v = getattr(metrics, c.name)
            if v is not None:
                metrics_text += f"- {FIELD_LABELS.get(c.name, c.name)}: {v}\n"
    if anchors_text:
        metrics_text = anchors_text + "\n\n" + metrics_text
    
    # 构建线索文本（前15条）
    leads_text = ""
    if leads:
        leads_text = f"## 线索列表（共{len(leads)}条，展示前15条）\n"
        for l in leads[:15]:
            src = f"ID:{l.ad_account}" if l.ad_account and l.ad_account != '--' else '自然'
            leads_text += f"- {l.nickname} | {l.city or '-'} | {l.path or '-'} | {l.tags or '-'} | 来源:{src}\n"
    
    # 构建评论文本（前30条）
    comments_text = ""
    if comments:
        comments_text = f"## 评论明细（共{len(comments)}条，展示前30条）\n"
        for c in comments[:30]:
            tag = "[已留资]" if c.has_lead else ""
            comments_text += f"- {c.nickname}{tag}: {c.content or '-'} ({c.comment_time or '-'})\n"
    
    # 构建高意向用户文本
    hiu_text = ""
    if hiu:
        hiu_text = f"## 高意向用户（共{len(hiu)}个）\n"
        for h in hiu:
            hiu_text += f"- {h.nickname} | 评论{h.comment_count}次 | 停留{h.stay_duration or '-'} | {h.status or '-'}\n"
    
    # 使用settings中的模板或默认格式
    template = config.get("ai_user_prompt_template", "")
    if template and "{{" in template:
        user_prompt = template.replace("{{start_time}}", session.start_time) \
            .replace("{{end_time}}", session.end_time) \
            .replace("{{duration_minutes}}", str(session.duration_minutes)) \
            .replace("{{ad_spend}}", str(metrics.ad_spend if metrics else 0)) \
            .replace("{{metrics_text}}", metrics_text) \
            .replace("{{leads_count}}", str(len(leads))) \
            .replace("{{leads_text}}", leads_text) \
            .replace("{{comments_count}}", str(len(comments))) \
            .replace("{{comments_text}}", comments_text) \
            .replace("{{high_intent_count}}", str(len(hiu))) \
            .replace("{{high_intent_text}}", hiu_text)
    else:
        user_prompt = f"""请按以下结构分析本场直播数据：

## 基础信息
- 直播时间：{session.start_time} ~ {session.end_time}
- 直播时长：{session.duration_minutes}分钟
- 营销消耗：¥{metrics.ad_spend if metrics else 0}

## 核心指标（44项）
{metrics_text}
{leads_text}
{comments_text}
{hiu_text}

## 分析要求
请遵循五维四率方法论和复盘策略，按以下格式输出：

### 一、整体评价
用1-10分评价本场表现，1-2句话概括

### 二、五维数据概览
按五个维度逐层展示数据：曝光人数→观看人数→商品曝光次数→商品点击人数→留资人数

### 三、四率漏斗分析
逐层计算转化率，标注瓶颈环节：
1. 观看点击率(进房率) = 观看人数/曝光人数
2. 商品点击率 = 商品点击人数/观看人数
3. 商品留资率 = 留资人数/商品点击人数
4. 点击成交率(结合成单数据)

### 四、复盘亮点与问题
- 亮点：曝光和进房峰值时段分析，高互动话术总结
- 问题：数据异常环节识别

### 五、优化建议
区分运营侧和主播侧，给出3-5条具体可执行的建议"""
    
    # AI调用（带重试机制）
    client = OpenAI(api_key=config["ai_api_key"], base_url=config.get("ai_base_url","https://api.openai.com/v1"))
    max_retries = 3
    last_error = None
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=config.get("ai_model","gpt-4o"),
                messages=[{"role":"system","content":config.get("ai_system_prompt","你是一位专业的抖音本地生活直播数据分析师，擅长从数据中挖掘可执行的运营策略。\n\n## 分析方法论\n\n### 五维四率（核心框架）\n- 五维：曝光人数 → 观看人数 → 商品曝光次数 → 商品点击人数 → 留资人数\n- 四率：观看点击率(进房率)、商品点击率、商品留资率、点击成交率\n\n请按此漏斗逐层分析：哪个环节转化率最低？为什么？如何优化？\n\n### 复盘策略\n#### 日复盘\n- 查看数据曲线中曝光量和进房人数最高的时间点\n- 分析该时间点的画面和话术亮点，总结可复用的好经验\n\n#### 周复盘\n- 找流量规律：哪场数据好/为什么/投流计划调整方向\n- 找高互动话术和内容模式\n\n#### 阶段性复盘\n- 主播需理解运营思维：曝光量、进房率、留资数量、投流成本\n- 运用表格进行深度数据对比\n- 团队配合：运营负责最大化曝光，主播负责转化\n- 投流计划优化迭代（圈地域/人群/时间点/出价等）\n- 私域产品升级（已报名学员专场直播、品牌IP塑造等）\n\n### 输出要求\n1. 五维四率漏斗分析（标注每个环节转化率，找出瓶颈环节）\n2. 日复盘亮点和留存策略\n3. 本场表现的量化评价\n4. 3-5条具体可执行的优化建议（区分运营侧和主播侧）")},{"role":"user","content":user_prompt}],
                timeout=120
            )
            break
        except openai.AuthenticationError as e:
            raise Exception(f"AI API Key无效: {e}")
        except (openai.APITimeoutError, openai.APIConnectionError, openai.RateLimitError) as e:
            last_error = e
            if attempt < max_retries - 1:
                import time; time.sleep(5)
                continue
        except openai.APIError as e:
            last_error = e
            if attempt < max_retries - 1:
                import time; time.sleep(5)
                continue
    else:
        raise Exception(f"AI API调用{max_retries}次均失败: {last_error}")
    
    existing = db.query(Report).filter(Report.session_id == session_id, Report.report_type == "session").first()
    if existing:
        existing.content = response.choices[0].message.content
        existing.generated_at = datetime.now().isoformat()
        report_id = existing.id
    else:
        report = Report(session_id=session_id, report_type="session", period=session.start_time[:10], content=response.choices[0].message.content)
        db.add(report); db.flush()
        report_id = report.id
    session.analyzed = True; session.analyzed_at = datetime.now().isoformat()
    db.commit(); return report_id
