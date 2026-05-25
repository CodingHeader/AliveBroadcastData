# Phase 7: 邮件推送服务 — 三级原子化执行方案

## Milestone 上下文

| 项 | 内容 |
|---|------|
| 所属Milestone | AliveBroadcastData 抖音直播数据分析系统 |
| 业务目标 | 自动发送HTML格式邮件，推送前日直播数据汇总+AI分析结果 |
| 在整体中的位置 | **第7个Phase**，依赖Phase 6（AI分析结果） |
| 被依赖方 | Phase 8（报告生成后可复用邮件发送）、Phase 9 |

## Phase 概要

| 项 | 内容 |
|---|------|
| 工期 | 1天 |
| 前置依赖 | Phase 6（AI分析服务）、Phase 5（邮箱配置） |
| 产出文件 | 3个新建 + 1个修改 |
| 涉及模块 | 邮件服务、HTML模板、定时任务 |
| 外部依赖 | SMTP服务器（smtp.163.com:465 SSL） |

## 产出文件总览

| 文件路径 | 类型 | 用途 |
|----------|------|------|
| `server/services/email_service.py` | 新建 | 邮件发送核心服务 |
| `server/templates/email/daily_report.html` | 新建 | 日报邮件HTML模板 |
| `server/templates/email/session_report.html` | 新建 | 单场速报邮件HTML模板 |
| `server/services/scheduler.py` | 修改 | 新增email_job定时任务 |

---

## Task 列表总览

| # | Task | 优先级 | 依赖 | 预估 |
|---|------|--------|------|------|
| 7.1 | 邮件发送模块 | P0 | Phase 5 | 3h |
| 7.2 | 邮件HTML模板 | P0 | Task 7.1 | 2h |
| 7.3 | 推送逻辑+定时任务 | P0 | Task 7.1/7.2 | 2h |

---

## Task 7.1: 邮件发送模块

### 任务描述
编写 `email_service.py`，实现SMTP SSL连接、HTML邮件构造、多收件人发送、错误处理。

### 执行逻辑

#### 1. 触发
| 项目 | 内容 |
|------|------|
| 调用方式 | scheduler定时调用 / admin API测试发送 |
| 外部服务 | smtp.163.com:465 (SSL) |

#### 2. 处理流程
```
1. 从settings表读取邮箱配置（host/port/sender/password/receivers）
2. 建立SMTP SSL连接
3. 构造MIMEMultipart邮件（HTML格式）
4. 逐个发送给所有收件人
5. 记录发送日志
6. 异常时记录错误，不中断其他收件人
```

#### 3. 数据库
| 项目 | 内容 |
|------|------|
| 读取表 | settings（邮箱配置）、sessions、session_metrics、leads、reports |
| 操作 | 只读 |

### 文件操作

**新建：**

| 路径 | 用途 |
|------|------|
| `server/services/email_service.py` | 邮件服务 |

### 伪代码

```python
import smtplib
import json
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from sqlalchemy.orm import Session as DBSession
from jinja2 import Environment, FileSystemLoader
from models import Setting, Session, SessionMetric, Lead, Report
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Jinja2模板环境
email_templates = Environment(loader=FileSystemLoader("templates/email"))

def get_email_config(db: DBSession) -> dict:
    """从settings表加载邮箱配置"""
    keys = ["email_smtp_host", "email_smtp_port", "email_sender", "email_password", "email_receivers"]
    settings = db.query(Setting).filter(Setting.key.in_(keys)).all()
    config = {s.key: s.value for s in settings}
    if not config.get("email_sender") or not config.get("email_password"):
        raise Exception("邮箱配置不完整")
    config["email_receivers"] = json.loads(config.get("email_receivers", "[]"))
    if not config["email_receivers"]:
        raise Exception("收件人列表为空")
    return config

def send_email(subject: str, html: str, config: dict, receivers: list):
    """SMTP发送HTML邮件"""
    host = config.get("email_smtp_host", "smtp.163.com")
    port = int(config.get("email_smtp_port", 465))
    sender = config["email_sender"]
    password = config["email_password"]
    
    for receiver in receivers:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = sender
            msg["To"] = receiver
            msg.attach(MIMEText(html, "html", "utf-8"))
            
            with smtplib.SMTP_SSL(host, port) as server:
                server.login(sender, password)
                server.sendmail(sender, receiver, msg.as_string())
            
            logger.info(f"邮件发送成功: {receiver}")
        except Exception as e:
            logger.error(f"邮件发送失败 [{receiver}]: {e}")

def send_daily_report(db: DBSession, date: str = None):
    """发送日报邮件"""
    if not date:
        date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    config = get_email_config(db)
    
    # 7.1 修复月末日期计算bug（如2026-05-31+1会生成无效日期）
    next_date = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    sessions = db.query(Session).filter(
        Session.start_time >= date + " 00:00:00",
        Session.start_time < next_date + " 00:00:00"
    ).all()
    
    if not sessions:
        logger.info(f"日期{date}无场次数据，跳过邮件推送")
        return
    
    # 聚合数据
    total_leads = 0
    total_spend = 0
    session_data_list = []
    
    for s in sessions:
        metrics = db.query(SessionMetric).filter(SessionMetric.session_id == s.id).first()
        leads_count = db.query(Lead).filter(Lead.session_id == s.id).count()
        report = db.query(Report).filter(Report.session_id == s.id, Report.report_type == "session").first()
        
        spend = float(metrics.ad_spend or 0) if metrics else 0
        total_leads += leads_count
        total_spend += spend
        
        session_data_list.append({
            "start_time": s.start_time,
            "end_time": s.end_time,
            "duration": s.duration_minutes,
            "leads": leads_count,
            "spend": spend,
            "lead_cost": round(spend / leads_count, 1) if leads_count > 0 else 0,
            "max_online": metrics.max_online if metrics else 0,
            "avg_watch": metrics.avg_watch_duration if metrics else "--",
            "ai_summary": report.content[:300] + "..." if report and len(report.content) > 300 else (report.content if report else "暂无AI分析"),
        })
    
    # 渲染邮件模板
    template = email_templates.get_template("daily_report.html")
    html = template.render(
        date=date,
        session_count=len(sessions),
        total_leads=total_leads,
        total_spend=round(total_spend, 2),
        avg_lead_cost=round(total_spend / total_leads, 1) if total_leads > 0 else 0,
        sessions=session_data_list,
    )
    
    # 发送
    subject = f"【直播日报】{date} 直播数据汇总"
    send_email(subject, html, config, config["email_receivers"])

def send_session_report(db: DBSession, session_id: int):
    """发送单场速报"""
    config = get_email_config(db)
    session = db.query(Session).get(session_id)
    # ... 类似daily_report，渲染session_report.html
    subject = f"【直播速报】{session.start_time[:16]} 场次数据"
    # ...
```

### 关联关系
- `email_service.py` ← 引用 `models.py`、`database.py`
- `email_service.py` ← 引用 `templates/email/*.html`（Jinja2模板）
- `email_service.py` → 被 `scheduler.py`（email_job）调用
- `email_service.py` → 被 `admin.py`（测试发送）调用

### 验收条件
- [ ] SMTP SSL连接正常
- [ ] HTML邮件构造正确（MIMEMultipart）
- [ ] 多收件人逐个发送
- [ ] 单个收件人失败不影响其他
- [ ] 配置缺失时抛出明确错误

---

## Task 7.2: 邮件HTML模板

### 任务描述
编写日报和单场速报的HTML邮件模板，大方有条理。

### 文件操作

**新建：**

| 路径 | 用途 |
|------|------|
| `server/templates/email/daily_report.html` | 日报邮件 |
| `server/templates/email/session_report.html` | 单场速报 |

### 伪代码

**`daily_report.html`：**
```html
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, 'Microsoft YaHei', sans-serif; max-width: 700px; margin: 0 auto; padding: 20px; background: #f5f5f5;">
    
    <!-- 标题 -->
    <div style="background: #fff; border-radius: 8px; padding: 24px; margin-bottom: 16px;">
        <h1 style="color: #1a1a1a; border-bottom: 2px solid #1890ff; padding-bottom: 10px; margin: 0;">
            📊 直播日报 | {{ date }}
        </h1>
    </div>

    <!-- 总览卡片 -->
    <div style="background: #fff; border-radius: 8px; padding: 24px; margin-bottom: 16px;">
        <h2 style="color: #333; margin-top: 0;">昨日总览</h2>
        <table style="width: 100%; border-collapse: collapse;">
            <tr style="background: #f6f8fa;">
                <td style="padding: 12px; text-align: center; border: 1px solid #e8e8e8;">
                    <div style="font-size: 24px; font-weight: bold; color: #1890ff;">{{ session_count }}</div>
                    <div style="color: #999; font-size: 12px;">场次</div>
                </td>
                <td style="padding: 12px; text-align: center; border: 1px solid #e8e8e8;">
                    <div style="font-size: 24px; font-weight: bold; color: #52c41a;">{{ total_leads }}</div>
                    <div style="color: #999; font-size: 12px;">总线索</div>
                </td>
                <td style="padding: 12px; text-align: center; border: 1px solid #e8e8e8;">
                    <div style="font-size: 24px; font-weight: bold; color: #fa8c16;">¥{{ total_spend }}</div>
                    <div style="color: #999; font-size: 12px;">总消耗</div>
                </td>
                <td style="padding: 12px; text-align: center; border: 1px solid #e8e8e8;">
                    <div style="font-size: 24px; font-weight: bold; color: {% if avg_lead_cost > 200 %}#ff4d4f{% else %}#52c41a{% endif %};">¥{{ avg_lead_cost }}</div>
                    <div style="color: #999; font-size: 12px;">线索成本</div>
                </td>
            </tr>
        </table>
    </div>

    <!-- 各场次数据 -->
    {% for s in sessions %}
    <div style="background: #fff; border-radius: 8px; padding: 24px; margin-bottom: 16px;">
        <h3 style="color: #333; margin-top: 0;">
            第{{ loop.index }}场 {{ s.start_time[11:16] }}~{{ s.end_time[11:16] }}
        </h3>
        <table style="width: 100%; border-collapse: collapse; margin-bottom: 12px;">
            <tr>
                <td style="padding: 8px; border: 1px solid #e8e8e8;">线索 <strong>{{ s.leads }}</strong>个</td>
                <td style="padding: 8px; border: 1px solid #e8e8e8;">消耗 <strong>¥{{ s.spend }}</strong></td>
                <td style="padding: 8px; border: 1px solid #e8e8e8;">成本 <strong style="color:{% if s.lead_cost > 200 %}#ff4d4f{% else %}#333{% endif %}">¥{{ s.lead_cost }}</strong></td>
                <td style="padding: 8px; border: 1px solid #e8e8e8;">时长 <strong>{{ s.duration }}min</strong></td>
            </tr>
        </table>
        <div style="background: #f6f8fa; border-radius: 4px; padding: 12px;">
            <strong>AI分析摘要：</strong>
            <p style="color: #555; margin: 8px 0 0;">{{ s.ai_summary }}</p>
        </div>
    </div>
    {% endfor %}

    <!-- 页脚 -->
    <div style="text-align: center; color: #999; font-size: 12px; padding: 16px;">
        此邮件由 AliveBroadcastData 系统自动发送
    </div>
</body>
</html>
```

### 验收条件
- [ ] 邮件在PC/手机邮件客户端正确渲染
- [ ] 总览卡片4个指标显示正确
- [ ] 各场次数据展示正确
- [ ] AI分析摘要展示（截断300字+...）
- [ ] 线索成本>200红色标注
- [ ] max-width:700px自适应

---

## Task 7.3: 推送逻辑+定时任务

### 任务描述
配置每天01:30自动推送日报邮件，等待AI分析完成后再发送。

### 执行逻辑

#### 定时任务
| 任务ID | cron | 说明 |
|--------|------|------|
| email_job | `30 1 * * *` | 每天01:30（等AI分析01:05完成后） |

#### 推送流程
```
1. 计算昨天日期
2. 检查昨天场次是否全部AI分析完成
   - 如果有未分析的 → 等待最多10分钟（每30秒检查）
   - 超时后仍按现有数据发送
3. 调用 send_daily_report(date=yesterday)
4. 记录发送日志
```

### 伪代码（scheduler.py追加）

```python
def email_job():
    """每天01:30推送日报邮件"""
    db = SessionLocal()
    try:
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        
        # 等待AI分析完成（最多10分钟）
        for i in range(20):  # 20次 × 30秒 = 10分钟
            # 7.1 同样修复月末日期计算bug
            next_day = (datetime.strptime(yesterday, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
            unanalyzed = db.query(Session).filter(
                Session.start_time >= yesterday + " 00:00:00",
                Session.start_time < next_day + " 00:00:00",
                Session.analyzed == False
            ).count()
            if unanalyzed == 0:
                break
            logger.info(f"等待AI分析完成，剩余{unanalyzed}场未分析")
            time.sleep(30)
        
        send_daily_report(db, yesterday)
        logger.info(f"日报邮件发送完成: {yesterday}")
    except Exception as e:
        logger.error(f"日报邮件发送失败: {e}")
    finally:
        db.close()

# scheduler.py init_scheduler() 中追加
scheduler.add_job(email_job, CronTrigger(hour=1, minute=30), id="email_job", replace_existing=True)
```

### 验收条件
- [ ] 每天01:30触发邮件推送
- [ ] 等待AI分析完成后再发送
- [ ] 等待超时10分钟后仍发送（不阻塞）
- [ ] 邮件内容包含昨日汇总+各场数据+AI摘要
- [ ] 测试邮件功能（后台按钮）正常

---

## Phase 7 整体验收清单

- [ ] SMTP SSL连接正常（smtp.163.com:465）
- [ ] HTML邮件格式正确、美观
- [ ] 多收件人全部收到
- [ ] 异常数据红色标注
- [ ] AI分析摘要包含在邮件中
- [ ] 定时任务01:30自动执行
- [ ] 等待AI分析完成机制正常
- [ ] 测试发送功能正常
- [ ] 错误日志记录完善
