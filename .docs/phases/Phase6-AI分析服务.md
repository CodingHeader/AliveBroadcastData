# Phase 6: AI分析服务 — 三级原子化执行方案

## Milestone 上下文

| 项 | 内容 |
|---|------|
| 所属Milestone | AliveBroadcastData 抖音直播数据分析系统 |
| 业务目标 | 自动/手动调用AI分析直播场次数据，生成Markdown报告 |
| 在整体中的位置 | **第6个Phase**，依赖Phase 1（数据库+配置） |
| 被依赖方 | Phase 7（邮件需包含AI分析）、Phase 8（报告基于AI结果） |

## Phase 概要

| 项 | 内容 |
|---|------|
| 工期 | 1天 |
| 前置依赖 | Phase 1（数据库+Settings表）、Phase 5（AI配置页面） |
| 产出文件 | 2个新建 + 1个修改 |
| 涉及模块 | AI服务、定时任务、后台API |
| 外部依赖 | OpenAI兼容API（需用户配置API Key） |

## 产出文件总览

| 文件路径 | 类型 | 用途 |
|----------|------|------|
| `server/services/ai_service.py` | 新建 | AI分析核心服务 |
| `server/services/scheduler.py` | 新建 | APScheduler定时任务配置 |
| `server/routers/admin.py` | 修改 | 新增手动触发分析API |

---

## Task 列表总览

| # | Task | 优先级 | 依赖 | 预估 |
|---|------|--------|------|------|
| 6.1 | AI调用模块 | P0 | Phase 1/5 | 4h |
| 6.2 | 手动触发分析 | P0 | Task 6.1 | 1h |
| 6.3 | 自动分析（定时任务） | P0 | Task 6.1 | 2h |

---

## Task 6.1: AI调用模块

### 任务描述
编写 `ai_service.py`，实现从数据库加载配置、渲染提示词模板、调用OpenAI兼容API、存储分析结果。

### 执行逻辑

#### 1. 触发
| 项目 | 内容 |
|------|------|
| 调用方式 | 被 scheduler（自动）或 admin API（手动）调用 |
| 输入 | session_id |
| 输出 | Markdown格式分析报告，存入reports表 |

#### 2. 处理流程
```
1. 从settings表加载AI配置：api_key, base_url, model, system_prompt, user_prompt_template
2. 从数据库查询session + metrics + leads + comments + high_intent_users
3. 渲染用户提示词模板（替换{{变量}}）
4. 调用OpenAI兼容API（system + user message）
5. 将AI返回的Markdown存入reports表（type="session"）
6. 更新sessions表：analyzed=True, analyzed_at=now
```

#### 3. 数据库
| 项目 | 内容 |
|------|------|
| 读取表 | settings, sessions, session_metrics, leads, comments, high_intent_users |
| 写入表 | reports（新增报告）, sessions（更新analyzed状态） |

#### 4. 响应（内部函数返回值）
| 场景 | 返回 |
|------|------|
| 成功 | report_id |
| 配置缺失 | raise Exception("AI API Key未配置") |
| API超时 | raise Exception("AI API调用超时") |
| 余额不足 | raise Exception("AI API返回错误: insufficient_quota") |

### 文件操作

**新建：**

| 路径 | 用途 |
|------|------|
| `server/services/ai_service.py` | AI分析服务 |

### 伪代码

**`server/services/ai_service.py`：**
```python
from openai import OpenAI
from sqlalchemy.orm import Session as DBSession
from models import Session, SessionMetric, Lead, Comment, HighIntentUser, Report, Setting
from datetime import datetime

def get_ai_config(db: DBSession) -> dict:
    """从settings表加载AI配置"""
    keys = ["ai_api_key", "ai_base_url", "ai_model", "ai_system_prompt", "ai_user_prompt_template"]
    settings = db.query(Setting).filter(Setting.key.in_(keys)).all()
    config = {s.key: s.value for s in settings}
    if not config.get("ai_api_key"):
        raise Exception("AI API Key未配置，请在后台设置")
    return config

def build_user_prompt(db: DBSession, session_id: int, template: str) -> str:
    """渲染用户提示词模板"""
    session = db.query(Session).get(session_id)
    metrics = db.query(SessionMetric).filter(SessionMetric.session_id == session_id).first()
    leads = db.query(Lead).filter(Lead.session_id == session_id).all()
    comments = db.query(Comment).filter(Comment.session_id == session_id).all()
    hiu = db.query(HighIntentUser).filter(HighIntentUser.session_id == session_id).all()
    
    # 6.2 中文字段映射，提升AI理解质量
    FIELD_LABELS = {
        "exposure_count": "曝光人数", "cumulative_viewers": "累计观看人数",
        "exposure_entry_rate": "曝光进入率", "max_online": "最高在线人数",
        "avg_watch_duration": "平均观看时长", "ad_spend": "营销消耗(元)",
        "total_leads": "全场景留资人数", "phone_submits": "填手机号人数",
        "comment_count": "评论次数", "comment_rate": "评论率",
        "interaction_count": "互动次数", "interaction_rate": "互动率",
        "share_count": "分享次数", "like_count": "点赞次数",
        "follow_count": "涨粉人数", "follow_rate": "关注率",
        "component_click_count": "组件点击次数", "component_click_rate": "组件点击率",
        "lead_conversion_rate": "留资转化率", "gmv": "成交金额",
        "order_count": "订单数", "order_cost": "订单成本",
    }
    # 构造指标文本
    metrics_text = ""
    if metrics:
        metrics_dict = {c.name: getattr(metrics, c.name) for c in metrics.__table__.columns if c.name not in ('id','session_id','created_at')}
        for k, v in metrics_dict.items():
            if v is not None:
                label = FIELD_LABELS.get(k, k)  # 有中文名用中文，否则用字段名
                metrics_text += f"- {label}: {v}\n"
    
    # 构造线索文本
    leads_text = "\n".join([f"- {l.nickname} | {l.city} | {l.path} | {l.ad_account}" for l in leads])
    
    # 构造评论文本
    comments_text = "\n".join([f"- {c.nickname}{'[已留资]' if c.has_lead else ''}: {c.content}" for c in comments])
    
    # 构造高意向用户文本
    hiu_text = "\n".join([f"- {h.nickname} | 评论{h.comment_count}次 | 停留{h.stay_duration} | {h.status}" for h in hiu])
    
    # 替换模板变量
    prompt = template.replace("{{start_time}}", session.start_time or "")
    prompt = prompt.replace("{{end_time}}", session.end_time or "")
    prompt = prompt.replace("{{duration_minutes}}", str(session.duration_minutes))
    prompt = prompt.replace("{{ad_spend}}", str(metrics.ad_spend if metrics else 0))
    prompt = prompt.replace("{{metrics_text}}", metrics_text)
    prompt = prompt.replace("{{leads_count}}", str(len(leads)))
    prompt = prompt.replace("{{leads_text}}", leads_text)
    prompt = prompt.replace("{{comments_count}}", str(len(comments)))
    prompt = prompt.replace("{{comments_text}}", comments_text)
    prompt = prompt.replace("{{high_intent_count}}", str(len(hiu)))
    prompt = prompt.replace("{{high_intent_text}}", hiu_text)
    
    return prompt

def analyze_session(db: DBSession, session_id: int) -> int:
    """分析单场直播，返回report_id"""
    config = get_ai_config(db)
    
    # 构建提示词
    system_prompt = config.get("ai_system_prompt", "你是一位专业的直播数据分析师。")
    user_template = config.get("ai_user_prompt_template", "请分析以下直播数据：\n{{metrics_text}}")
    user_prompt = build_user_prompt(db, session_id, user_template)
    
    # 调用AI API
    client = OpenAI(
        api_key=config["ai_api_key"],
        base_url=config.get("ai_base_url", "https://api.openai.com/v1")
    )
    
    try:
        response = client.chat.completions.create(
            model=config.get("ai_model", "gpt-4o"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            timeout=120  # 超时120秒
        )
        ai_content = response.choices[0].message.content
    except Exception as e:
        raise Exception(f"AI API调用失败: {str(e)}")
    
    # 存储报告
    session = db.query(Session).get(session_id)
    report = Report(
        session_id=session_id,
        report_type="session",
        period=session.start_time[:10],  # "2026-05-21"
        content=ai_content,
    )
    db.add(report)
    
    # 更新session分析状态
    session.analyzed = True
    session.analyzed_at = datetime.now().isoformat()
    db.commit()
    
    return report.id
```

### 默认提示词（来自功能设计文档6.1/6.2）

**系统提示词：**
```
你是一位专业的直播数据分析师，擅长分析抖音本地生活直播间的运营数据。
请根据提供的直播数据，输出一份专业的分析报告。
分析要求：
1. 整体评价（优秀/良好/一般/较差），综合评分1-10
2. 流量效率（曝光进入率、观看时长、在线趋势）
3. 互动质量（评论率、点赞率、分享率、粉丝转化）
4. 转化效率（留资率、线索成本、组件点击率）
5. 线索质量（城市分布、留资路径偏好、停留时长）
6. 3-5条可执行优化建议
7. 趋势判断（如有多场对比）
输出格式：Markdown，重点数据加粗。
```

### 关联关系
- `ai_service.py` ← 引用 `models.py`（所有表）、`database.py`（Session管理）
- `ai_service.py` → 被 `scheduler.py`（自动分析）、`admin.py`（手动触发）调用
- `ai_service.py` ← 外部依赖 `openai` 库

### 验收条件
- [ ] 配置正确时调用AI API返回Markdown报告
- [ ] 报告存入reports表（type=session）
- [ ] sessions表analyzed=True更新
- [ ] 配置缺失时抛出明确错误
- [ ] API超时处理（120秒）
- [ ] 提示词模板变量全部正确替换

---

## Task 6.2: 手动触发分析

### 任务描述
实现后台API手动触发单场分析，前端显示loading状态。

### 执行逻辑

#### 1. 路由
| 项目 | 内容 |
|------|------|
| API | POST `/admin/api/sessions/{id}/analyze` |
| 认证 | JWT Token |

#### 2. 伪代码

**admin.py：**
```python
@router.post("/sessions/{session_id}/analyze")
def manual_analyze(session_id: int, admin=Depends(get_current_admin), db=Depends(get_db)):
    session = db.query(Session).get(session_id)
    if not session:
        raise HTTPException(404, detail="场次不存在")
    
    try:
        report_id = analyze_session(db, session_id)
        return {"code": 0, "message": "分析完成", "report_id": report_id}
    except Exception as e:
        return {"code": 500, "message": str(e)}
```

**前端触发（session_detail.html AI分析Tab）：**
```javascript
async analyzeNow() {
    this.analyzing = true;
    const resp = await adminFetch(`/admin/api/sessions/${this.sessionId}/analyze`, {method:'POST'});
    const data = await resp.json();
    this.analyzing = false;
    if (data.code === 0) {
        this.loadReport(); // 重新加载报告内容
    } else {
        alert('分析失败: ' + data.message);
    }
}
```

### 验收条件
- [ ] 点击"分析"按钮触发AI分析
- [ ] Loading状态显示
- [ ] 分析完成后自动刷新报告内容
- [ ] 错误时显示友好提示

---

## Task 6.3: 自动分析（定时任务）

### 任务描述
配置APScheduler，每小时自动检查未分析场次并逐场分析。

### 执行逻辑

#### 1. 定时任务配置

| 任务ID | cron表达式 | 说明 |
|--------|-----------|------|
| analyze_job | `5 * * * *` | 每小时第5分钟 |

#### 2. 处理流程
```
1. 查询 sessions 表 analyzed=False 的所有场次
2. 按 start_time 正序排列
3. 逐场调用 analyze_session()
4. 每场之间间隔5秒（避免API频率限制）
5. 单场失败不影响后续场次（catch异常记录日志）
```

### 文件操作

**新建：**

| 路径 | 用途 |
|------|------|
| `server/services/scheduler.py` | 定时任务配置 |

### 伪代码

**`server/services/scheduler.py`：**
```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from database import SessionLocal
from models import Session
from services.ai_service import analyze_session
import logging
import time

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()

def analyze_job():
    """每小时自动分析未分析场次"""
    db = SessionLocal()
    try:
        unanalyzed = db.query(Session).filter(Session.analyzed == False).order_by(Session.start_time).all()
        if not unanalyzed:
            logger.info("无未分析场次")
            return
        
        logger.info(f"发现{len(unanalyzed)}个未分析场次")
        for session in unanalyzed:
            # 6.1 超过3次失败的场次不再重试，防止配置错误时无限重试消耗API额度
            attempts = getattr(session, 'analyze_attempts', 0) or 0
            if attempts >= 3:
                logger.warning(f"场次{session.id}分析已失败{attempts}次，跳过")
                continue
            try:
                report_id = analyze_session(db, session.id)
                logger.info(f"场次{session.id}分析完成，report_id={report_id}")
                time.sleep(5)  # 间隔5秒
            except Exception as e:
                logger.error(f"场次{session.id}分析失败: {e}")
                session.analyze_attempts = attempts + 1  # 递增失败次数
                db.commit()
                continue  # 不中断后续
    finally:
        db.close()

def init_scheduler():
    """初始化定时任务"""
    scheduler.add_job(analyze_job, CronTrigger(minute=5), id="analyze_job", replace_existing=True)
    # Phase 7/8 的定时任务将在后续Phase添加
    # X.3 数据库每日自动备份（04:00）
    scheduler.add_job(backup_job, CronTrigger(hour=4, minute=0), id="backup_job", replace_existing=True)
    scheduler.start()
    logger.info("定时任务已启动")


import shutil
from pathlib import Path

def backup_job():
    """X.3 每天04:00备份data.db（保留最近7天，防文件损坏导致数据丢失）"""
    src = Path("data.db")
    if not src.exists():
        return
    backup_dir = Path("backups")
    backup_dir.mkdir(exist_ok=True)
    backup_name = f"data_{datetime.now().strftime('%Y%m%d')}.db"
    shutil.copy2(src, backup_dir / backup_name)
    for old in sorted(backup_dir.glob("data_*.db"))[:-7]:
        old.unlink()
    logger.info(f"数据库备份完成: {backup_name}")
```

**`server/main.py` 修改 — 启动时初始化scheduler：**
```python
from services.scheduler import init_scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    init_scheduler()
    yield
    scheduler.shutdown()
```

### 关联关系
- `scheduler.py` → 调用 `ai_service.py`（analyze_session）
- `scheduler.py` → 被 `main.py`（lifespan）调用启动
- Phase 7/8 将在此文件追加 email_job / report_job

### 验收条件
- [ ] APScheduler启动日志输出
- [ ] 每小时第5分钟触发analyze_job
- [ ] 未分析场次被逐场分析
- [ ] 单场失败不影响后续
- [ ] 分析完成后sessions.analyzed=True

---

## Phase 6 整体验收清单

- [ ] AI配置正确读取（api_key/base_url/model/prompts）
- [ ] 提示词模板渲染正确（所有{{变量}}替换）
- [ ] AI API调用成功返回Markdown
- [ ] 报告存入reports表
- [ ] sessions.analyzed状态更新
- [ ] 手动触发分析正常（前端按钮+loading+结果）
- [ ] 自动分析每小时执行
- [ ] 错误处理完善（配置缺失/超时/余额不足）
- [ ] 日志记录清晰
