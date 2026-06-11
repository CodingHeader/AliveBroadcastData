# Phase 8: 报告生成服务 — 三级原子化执行方案

## Milestone 上下文

| 项 | 内容 |
|---|------|
| 所属Milestone | AliveBroadcastData 抖音直播数据分析系统 |
| 业务目标 | 自动聚合数据生成日报/周报/月报，支持筛选下载 |
| 在整体中的位置 | **第8个Phase**，依赖Phase 6（AI分析）+ Phase 7（邮件） |
| 被依赖方 | Phase 9（端到端测试） |

## Phase 概要

| 项 | 内容 |
|---|------|
| 工期 | 1天 |
| 前置依赖 | Phase 6（AI分析结果作为报告组成部分） |
| 产出文件 | 1个新建 + 1个修改 |
| 涉及模块 | 报告生成服务、定时任务 |

## 产出文件总览

| 文件路径 | 类型 | 用途 |
|----------|------|------|
| `server/services/report_service.py` | 新建 | 报告生成核心服务 |
| `server/services/scheduler.py` | 修改 | 新增日报/周报/月报定时任务 |

---

## Task 列表总览

| # | Task | 优先级 | 依赖 | 预估 |
|---|------|--------|------|------|
| 8.1 | 报告生成模块 | P0 | Phase 6 | 4h |
| 8.2 | 定时生成任务 | P0 | Task 8.1 | 2h |
| 8.3 | 下载功能完善 | P1 | Task 8.1 | 1h |

---

## Task 8.1: 报告生成模块

### 任务描述
编写 `report_service.py`，实现日报/周报/月报的数据聚合和Markdown生成。

### 执行逻辑

#### 1. 报告类型

| 类型 | period格式 | 数据范围 | 触发时间 |
|------|-----------|----------|----------|
| session | "2026-05-21" | 单场 | AI分析时自动生成 |
| daily | "2026-05-21" | 一天所有场次 | 每天01:00 |
| weekly | "2026-W21" | 一周(周一~周日) | 每周一02:00 |
| monthly | "2026-05" | 一个月 | 每月1号03:00 |

#### 2. 处理流程（以日报为例）
```
1. 确定日期范围
2. 查询范围内所有sessions + metrics
3. 聚合统计：总场次、总线索、总消耗、平均线索成本
4. 查询已有的AI分析报告（type=session）
5. 组装Markdown报告
6. 存入reports表（type=daily）
7. 检查是否已存在同period报告 → 存在则更新，不存在则新建
```

### 文件操作

**新建：**

| 路径 | 用途 |
|------|------|
| `server/services/report_service.py` | 报告生成服务 |

### 伪代码

```python
from sqlalchemy import func
from sqlalchemy.orm import Session as DBSession
from models import Session, SessionMetric, Lead, Report, Deal, SessionAnchor, Anchor
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

def generate_daily_report(db: DBSession, date: str) -> int:
    """
    生成日报
    date: "2026-05-21"
    返回: report_id
    """
    next_date = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    
    # 查询当日场次
    sessions = db.query(Session).filter(
        Session.start_time >= date + " 00:00:00",
        Session.start_time < next_date + " 00:00:00"
    ).order_by(Session.start_time).all()
    
    if not sessions:
        logger.info(f"日期{date}无场次，跳过日报")
        return None
    
    # 聚合统计
    session_ids = [s.id for s in sessions]
    total_leads = db.query(func.count(Lead.id)).filter(Lead.session_id.in_(session_ids)).scalar() or 0
    total_spend = db.query(func.sum(SessionMetric.ad_spend)).filter(SessionMetric.session_id.in_(session_ids)).scalar() or 0
    avg_cost = round(total_spend / total_leads, 1) if total_leads > 0 else 0
    
    # 组装Markdown
    md = f"# 直播日报 | {date}\n\n"
    md += f"## 总览\n\n"
    md += f"| 指标 | 数值 |\n|------|------|\n"
    md += f"| 场次数 | {len(sessions)} |\n"
    md += f"| 总线索 | {total_leads} |\n"
    md += f"| 总消耗 | ¥{total_spend:.2f} |\n"
    md += f"| 平均线索成本 | ¥{avg_cost} |\n\n"
    
    # 各场次详情
    md += f"## 场次明细\n\n"
    for i, s in enumerate(sessions, 1):
        metrics = db.query(SessionMetric).filter(SessionMetric.session_id == s.id).first()
        leads_count = db.query(func.count(Lead.id)).filter(Lead.session_id == s.id).scalar()
        spend = float(metrics.ad_spend or 0) if metrics else 0
        cost = round(spend / leads_count, 1) if leads_count > 0 else 0
        
        md += f"### 第{i}场 {s.start_time[11:16]}~{s.end_time[11:16]}\n\n"
        md += f"- 时长：{s.duration_minutes}分钟\n"
        md += f"- 线索：{leads_count}个\n"
        md += f"- 消耗：¥{spend:.2f}\n"
        md += f"- 线索成本：¥{cost}\n"
        
        if metrics:
            md += f"- 最高在线：{metrics.max_online}人\n"
            md += f"- 人均观看：{metrics.avg_watch_duration}\n"
        
        # 引用AI分析
        ai_report = db.query(Report).filter(Report.session_id == s.id, Report.report_type == "session").first()
        if ai_report:
            md += f"\n**AI分析摘要：**\n\n{ai_report.content[:500]}\n\n"
        md += "---\n\n"
    
    # 存储（更新或新建）
    existing = db.query(Report).filter(Report.report_type == "daily", Report.period == date).first()
    if existing:
        existing.content = md
        existing.generated_at = datetime.now().isoformat()
        db.commit()
        return existing.id
    else:
        report = Report(report_type="daily", period=date, content=md)
        db.add(report)
        db.commit()
        return report.id


def generate_weekly_report(db: DBSession, week_str: str = None) -> int:
    """
    生成周报
    week_str: "2026-W21"（不传则自动计算上周）
    """
    if not week_str:
        today = datetime.now()
        last_monday = today - timedelta(days=today.weekday() + 7)
        last_sunday = last_monday + timedelta(days=6)
        week_str = last_monday.strftime("%Y-W%V")
        date_from = last_monday.strftime("%Y-%m-%d")
        date_to = last_sunday.strftime("%Y-%m-%d")
    else:
        # 解析week_str得到日期范围
        year, week = week_str.split("-W")
        from datetime import date as dt_date
        first_day = dt_date.fromisocalendar(int(year), int(week), 1)
        last_day = dt_date.fromisocalendar(int(year), int(week), 7)
        date_from = first_day.isoformat()
        date_to = last_day.isoformat()
    
    # 本周数据
    sessions = db.query(Session).filter(
        Session.start_time >= date_from,
        Session.start_time < date_to + " 23:59:59"
    ).all()
    
    session_ids = [s.id for s in sessions]
    total_leads = db.query(func.count(Lead.id)).filter(Lead.session_id.in_(session_ids)).scalar() or 0
    total_spend = db.query(func.sum(SessionMetric.ad_spend)).filter(SessionMetric.session_id.in_(session_ids)).scalar() or 0
    
    # 上周数据（用于环比）
    prev_from = (datetime.strptime(date_from, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")
    prev_to = (datetime.strptime(date_to, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")
    prev_sessions = db.query(Session).filter(Session.start_time >= prev_from, Session.start_time < prev_to + " 23:59:59").all()
    prev_ids = [s.id for s in prev_sessions]
    prev_leads = db.query(func.count(Lead.id)).filter(Lead.session_id.in_(prev_ids)).scalar() or 0
    prev_spend = db.query(func.sum(SessionMetric.ad_spend)).filter(SessionMetric.session_id.in_(prev_ids)).scalar() or 0
    
    # 成单数据（周报含ROI）
    deals = db.query(Deal).filter(Deal.deal_time >= date_from, Deal.deal_time <= date_to).all()
    total_deal_amount = sum(d.amount for d in deals)
    roi = round(total_deal_amount / total_spend, 2) if total_spend > 0 else 0
    
    # 主播表现
    anchor_stats = db.query(
        Anchor.name,
        func.count(Session.id).label("count"),
    ).join(SessionAnchor, SessionAnchor.anchor_id == Anchor.id
    ).join(Session, Session.id == SessionAnchor.session_id
    ).filter(Session.id.in_(session_ids)
    ).group_by(Anchor.name).all()
    
    # 组装Markdown（来自功能设计文档6.3）
    md = f"# 周报 | {week_str} ({date_from} ~ {date_to})\n\n"
    md += "## 一、周度总览\n\n"
    md += f"| 指标 | 本周 | 上周 | 环比 |\n|------|------|------|------|\n"
    md += f"| 场次 | {len(sessions)} | {len(prev_sessions)} | {_change(len(sessions), len(prev_sessions))} |\n"
    md += f"| 线索 | {total_leads} | {prev_leads} | {_change(total_leads, prev_leads)} |\n"
    md += f"| 消耗 | ¥{total_spend:.0f} | ¥{prev_spend:.0f} | {_change(total_spend, prev_spend)} |\n"
    md += f"| 成单 | {len(deals)}笔 / ¥{total_deal_amount:.0f} | - | - |\n"
    md += f"| ROI | {roi} | - | - |\n\n"
    
    md += "## 二、每日数据\n\n"
    md += "| 日期 | 场次 | 线索 | 消耗 | 成本 |\n|------|------|------|------|------|\n"
    # 按日聚合...
    
    md += "\n## 三、主播表现\n\n"
    md += "| 主播 | 场次 |\n|------|------|\n"
    for a in anchor_stats:
        md += f"| {a.name} | {a.count} |\n"
    
    md += "\n## 四、优化建议回顾\n\n（待补充）\n"
    
    # 8.1 周报AI周度分析（基于整周汇总数据单独调用AI）
    try:
        from services.ai_service import get_ai_config
        from openai import OpenAI
        config = get_ai_config(db)
        client = OpenAI(api_key=config["ai_api_key"], base_url=config.get("ai_base_url", "https://api.openai.com/v1"))
        weekly_prompt = f"""请基于以下一周直播数据汇总，给出周度分析和下周优化建议：\n\n{md}"""
        response = client.chat.completions.create(
            model=config.get("ai_model", "gpt-4o"),
            messages=[{"role": "system", "content": config.get("ai_system_prompt", "")},
                      {"role": "user", "content": weekly_prompt}],
            timeout=120
        )
        md += f"\n## 五、AI周度分析\n\n{response.choices[0].message.content}\n"
    except Exception as e:
        md += f"\n## 五、AI周度分析\n\n（生成失败：{e}）\n"
    
    # 存储
    existing = db.query(Report).filter(Report.report_type == "weekly", Report.period == week_str).first()
    if existing:
        existing.content = md
        db.commit()
        return existing.id
    report = Report(report_type="weekly", period=week_str, content=md)
    db.add(report)
    db.commit()
    return report.id


def generate_monthly_report(db: DBSession, month_str: str = None) -> int:
    """
    生成月报
    month_str: "2026-05"
    结构同周报，增加月度趋势图描述和优化建议回顾
    """
    if not month_str:
        last_month = datetime.now().replace(day=1) - timedelta(days=1)
        month_str = last_month.strftime("%Y-%m")
    
    year, month = month_str.split("-")
    date_from = f"{month_str}-01"
    # 下月第一天
    if int(month) == 12:
        date_to_exclusive = f"{int(year)+1}-01-01"
    else:
        date_to_exclusive = f"{year}-{int(month)+1:02d}-01"
    
    # 8.2 月报完整实现（同周报逻辑，增加按周聚合趋势和建议回顾）
    next_month = f"{year}-{int(month)+1:02d}-01" if int(month) < 12 else f"{int(year)+1}-01-01"
    sessions = db.query(Session).filter(
        Session.start_time >= date_from + " 00:00:00",
        Session.start_time < next_month + " 00:00:00"
    ).order_by(Session.start_time).all()
    
    session_ids = [s.id for s in sessions]
    from sqlalchemy import func
    total_leads = db.query(func.count(Lead.id)).filter(Lead.session_id.in_(session_ids)).scalar() or 0
    total_spend = db.query(func.sum(SessionMetric.ad_spend)).filter(SessionMetric.session_id.in_(session_ids)).scalar() or 0
    avg_cost = round(total_spend / total_leads, 1) if total_leads > 0 else 0
    deals = db.query(Deal).filter(Deal.deal_time >= date_from, Deal.deal_time < next_month).all()
    total_deal_amount = sum(d.amount for d in deals)
    roi = round(total_deal_amount / total_spend, 2) if total_spend > 0 else 0
    
    md = f"# 月报 | {month_str}\n\n"
    md += f"## 一、月度总览\n\n"
    md += f"| 指标 | 数值 |\n|------|------|\n"
    md += f"| 场次数 | {len(sessions)} |\n| 总线索 | {total_leads} |\n"
    md += f"| 总消耗 | ¥{total_spend:.2f} |\n| 平均线索成本 | ¥{avg_cost} |\n"
    md += f"| 成单数 | {len(deals)}笔 / ¥{total_deal_amount:.0f} |\n| 月ROI | {roi} |\n\n"
    
    md += "## 二、月度趋势图描述（按周聚合）\n\n"
    md += "| 周 | 场次 | 线索 | 消耗 |\n|------|------|------|------|\n"
    week_map = {}
    for s in sessions:
        wnum = datetime.strptime(s.start_time[:10], "%Y-%m-%d").strftime("%Y-W%V")
        week_map.setdefault(wnum, []).append(s.id)
    for wnum, ids in sorted(week_map.items()):
        wleads = db.query(func.count(Lead.id)).filter(Lead.session_id.in_(ids)).scalar() or 0
        wspend = db.query(func.sum(SessionMetric.ad_spend)).filter(SessionMetric.session_id.in_(ids)).scalar() or 0
        md += f"| {wnum} | {len(ids)} | {wleads} | ¥{wspend:.0f} |\n"
    
    md += "\n## 三、优化建议回顾\n\n"
    ai_reports = db.query(Report).filter(
        Report.report_type == "session",
        Report.period >= date_from, Report.period < next_month
    ).all()
    md += f"本月共{len(ai_reports)}场次AI分析已生成，建议要点待人工整理导入。\n"
    
    # 存储
    existing = db.query(Report).filter(Report.report_type == "monthly", Report.period == month_str).first()
    if existing:
        existing.content = md
        existing.generated_at = datetime.now().isoformat()
        db.commit()
        return existing.id
    report = Report(report_type="monthly", period=month_str, content=md)
    db.add(report)
    db.commit()
    return report.id


def _change(current, previous) -> str:
    """计算环比变化"""
    if previous == 0:
        return "+∞" if current > 0 else "0%"
    pct = (current - previous) / previous * 100
    return f"+{pct:.1f}%" if pct >= 0 else f"{pct:.1f}%"
```

### 周报/月报内容模板（来自功能设计文档6.3）

**周报结构：**
1. 周度总览（场次数、总线索、总消耗、平均线索成本、成单数/金额、周ROI）
2. 环比对比表（本周 vs 上周，各指标变化率）
3. 每日数据表（日期、场次、线索、消耗、成本）
4. 主播表现（主播、场次、场均线索、场均成本）
5. AI周度分析（基于整周数据单独调用AI生成）

**月报结构：** 同周报 + "月度趋势图描述" + "优化建议回顾"

### 关联关系
- `report_service.py` ← 引用 `models.py`（所有表）
- `report_service.py` → 被 `scheduler.py`（定时任务）调用
- 周报/月报中包含 ROI 计算（需求文档5.5）

### 验收条件
- [ ] 日报正确聚合当日所有场次
- [ ] 日报包含各场数据+AI分析摘要
- [ ] 周报包含环比对比+成单+ROI
- [ ] 月报包含月度趋势描述
- [ ] 同period报告更新而非重复创建
- [ ] Markdown格式正确、可渲染

---

## Task 8.2: 定时生成任务

### 任务描述
在scheduler中注册日报/周报/月报定时任务。

### 定时任务配置

| 任务ID | cron表达式 | 说明 |
|--------|-----------|------|
| daily_report_job | `0 1 * * *` | 每天01:00 |
| weekly_report_job | `0 2 * * 1` | 每周一02:00 |
| monthly_report_job | `0 3 1 * *` | 每月1号03:00 |

### 伪代码（scheduler.py追加）

```python
from services.report_service import generate_daily_report, generate_weekly_report, generate_monthly_report

def daily_report_job():
    db = SessionLocal()
    try:
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        report_id = generate_daily_report(db, yesterday)
        logger.info(f"日报生成完成: {yesterday}, report_id={report_id}")
    except Exception as e:
        logger.error(f"日报生成失败: {e}")
    finally:
        db.close()

def weekly_report_job():
    db = SessionLocal()
    try:
        report_id = generate_weekly_report(db)  # 自动计算上周
        logger.info(f"周报生成完成, report_id={report_id}")
    except Exception as e:
        logger.error(f"周报生成失败: {e}")
    finally:
        db.close()

def monthly_report_job():
    db = SessionLocal()
    try:
        report_id = generate_monthly_report(db)  # 自动计算上月
        logger.info(f"月报生成完成, report_id={report_id}")
    except Exception as e:
        logger.error(f"月报生成失败: {e}")
    finally:
        db.close()

# init_scheduler() 中追加
scheduler.add_job(daily_report_job, CronTrigger(hour=1, minute=0), id="daily_report_job", replace_existing=True)
scheduler.add_job(weekly_report_job, CronTrigger(day_of_week='mon', hour=2, minute=0), id="weekly_report_job", replace_existing=True)
scheduler.add_job(monthly_report_job, CronTrigger(day=1, hour=3, minute=0), id="monthly_report_job", replace_existing=True)
```

### 定时任务执行时间线

```
00:00 - 油猴脚本开始采集昨天数据
00:30 - 数据入库完成（预估）
01:00 - AI自动分析未分析场次（analyze_job，优先完成）
01:05 - 日报生成（daily_report_job，含AI分析摘要）
01:30 - 邮件推送（email_job，含完整AI分析结论）
02:00 - 周报生成（每周一，weekly_report_job）
02:05 - 数据库备份（backup_job，保留7天）
03:00 - 月报生成（每月1号，monthly_report_job）
```

### 验收条件
- [ ] 日报每天01:00自动生成
- [ ] 周报每周一02:00自动生成
- [ ] 月报每月1号03:00自动生成
- [ ] 各任务失败不影响其他任务

---

## Task 8.3: 下载功能完善

### 任务描述
确保报告下载API正确返回Markdown文件流。

### 验证点
- Phase 4已实现 GET /api/reports/{id}/download
- 此Task验证日报/周报/月报下载正确
- 文件名格式：`{type}_{period}.md`（如 `weekly_2026-W21.md`）

### 验收条件
- [ ] 日报下载返回 .md 文件
- [ ] 周报下载返回 .md 文件
- [ ] 月报下载返回 .md 文件
- [ ] 文件名包含类型和周期

---

## Phase 8 整体验收清单

- [ ] 日报正确生成（含各场数据+AI摘要）
- [ ] 周报正确生成（含环比+ROI+主播表现）
- [ ] 月报正确生成（含月度趋势）
- [ ] 定时任务按时执行
- [ ] 报告存入reports表
- [ ] 同period不重复创建（更新已有）
- [ ] 下载功能正常
- [ ] 整体时间线不冲突（01:00→01:05→01:30→02:00→03:00）
