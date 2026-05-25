"""
更新settings表中AI提示词为最新默认值。
已有数据库不会自动更新提示词，运行此脚本手动同步。
"""
import sys
sys.path.insert(0, r'e:\Code\AliveBroadcastData\server')

from database import SessionLocal
from models import Setting

def update_prompts():
    db = SessionLocal()
    try:
        # 新的system_prompt默认值
        new_system = ("你是一位专业的抖音本地生活直播数据分析师，擅长从数据中挖掘可执行的运营策略。\n\n"
            "## 分析方法论\n\n"
            "### 五维四率（核心框架）\n"
            "- 五维：曝光人数 → 观看人数 → 商品曝光次数 → 商品点击人数 → 留资人数\n"
            "- 四率：观看点击率(进房率)、商品点击率、商品留资率、点击成交率\n\n"
            "请按此漏斗逐层分析：哪个环节转化率最低？为什么？如何优化？\n\n"
            "### 复盘策略\n"
            "#### 日复盘\n"
            "- 查看数据曲线中曝光量和进房人数最高的时间点\n"
            "- 分析该时间点的画面和话术亮点，总结可复用的好经验\n\n"
            "#### 周复盘\n"
            "- 找流量规律：哪场数据好/为什么/投流计划调整方向\n"
            "- 找高互动话术和内容模式\n\n"
            "#### 阶段性复盘\n"
            "- 主播需理解运营思维：曝光量、进房率、留资数量、投流成本\n"
            "- 运用表格进行深度数据对比\n"
            "- 团队配合：运营负责最大化曝光，主播负责转化\n"
            "- 投流计划优化迭代（圈地域/人群/时间点/出价等）\n"
            "- 私域产品升级（已报名学员专场直播、品牌IP塑造等）\n\n"
            "### 输出要求\n"
            "1. 五维四率漏斗分析（标注每个环节转化率，找出瓶颈环节）\n"
            "2. 日复盘亮点和留存策略\n"
            "3. 本场表现的量化评价\n"
            "4. 3-5条具体可执行的优化建议（区分运营侧和主播侧）")

        # 新的user_prompt_template默认值
        new_template = ("""请按以下结构分析本场直播数据：

## 基础信息
- 直播时间：{{start_time}} ~ {{end_time}}
- 直播时长：{{duration_minutes}}分钟
- 营销消耗：¥{{ad_spend}}

## 核心指标（44项）
{{metrics_text}}

## 线索列表（共{{leads_count}}条）
{{leads_text}}

## 评论明细（共{{comments_count}}条）
{{comments_text}}

## 高意向用户（共{{high_intent_count}}个）
{{high_intent_text}}

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
区分运营侧和主播侧，给出3-5条具体可执行的建议""")

        updates = []
        for key, new_value in [("ai_system_prompt", new_system), ("ai_user_prompt_template", new_template)]:
            setting = db.query(Setting).filter(Setting.key == key).first()
            if setting:
                setting.value = new_value
                updates.append(key)
                print(f"已更新: {key}")
            else:
                print(f"未找到: {key}（请先启动服务初始化数据库）")

        if updates:
            db.commit()
            print(f"\n成功更新 {len(updates)} 项提示词配置")
        else:
            print("\n未更新任何配置")

    finally:
        db.close()

if __name__ == "__main__":
    update_prompts()
