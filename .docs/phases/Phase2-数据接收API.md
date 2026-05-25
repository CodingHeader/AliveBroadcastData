# Phase 2: 数据接收API — 三级原子化执行方案

## Milestone 上下文

| 项 | 内容 |
|---|------|
| 所属Milestone | AliveBroadcastData 抖音直播数据分析系统 |
| 业务目标 | 提供HTTP接口接收油猴脚本POST的直播场次数据，解析并持久化到SQLite |
| 在整体中的位置 | **第2个Phase**，依赖Phase 1（数据库+框架） |
| 被依赖方 | Phase 3（油猴脚本需要调用此API） |

## Phase 概要

| 项 | 内容 |
|---|------|
| 工期 | 1天 |
| 前置依赖 | Phase 1（数据库层+FastAPI入口） |
| 产出文件 | 1个修改文件 |
| 涉及模块 | 后端API、数据解析、数据校验 |
| 核心API | POST /api/session, GET /api/session/check |

## Task 列表总览

| # | Task | 优先级 | 依赖 | 预估 |
|---|------|--------|------|------|
| 2.1 | 数据接收API实现 | P0 | Phase 1 | 4h |
| 2.2 | 测试验证 | P0 | Task 2.1 | 2h |

---

## Task 2.1: 数据接收API实现

### 任务描述
实现 POST /api/session（接收完整场次数据）和 GET /api/session/check（防重复检查），包括数据校验、格式解析、事务写入。

### 执行逻辑

#### 1. 触发
| 项目 | 内容 |
|------|------|
| 触发来源 | 油猴脚本 fetch POST / 手动测试 |
| 触发事件 | HTTP请求到达 |

#### 2. 路由
| 项目 | 内容 |
|------|------|
| API路径 | POST /api/session |
| API路径 | GET /api/session/check?start_time=xxx |
| 请求格式 | JSON (POST) / Query参数 (GET) |

#### 3. 逻辑处理
| 项目 | 内容 |
|------|------|
| 处理文件 | `server/routers/api.py` |
| 核心函数 | `receive_session()`, `check_session()` |
| 辅助函数 | `server/utils.py` → `parse_number()`, `parse_time()` |

#### 4. 数据请求（接收的JSON结构）

**POST /api/session 请求体：**
```json
{
  "start_time": "05-21 09：28",
  "end_time": "05-21 13：36",
  "metrics": {
    "exposure_count": "34,180",
    "cumulative_viewers": "1,258",
    "exposure_entry_rate": "3.68%",
    "gmv": "0",
    "ad_spend": "1,061.58",
    "total_leads": "4",
    "phone_submits": "4",
    "comment_count": "81",
    "max_online": "16",
    "avg_watch_duration": "30秒",
    ...共44个字段
  },
  "leads": [
    {
      "lead_time": "05-21 13:17",
      "nickname": "用户A",
      "lead_id": "LS_xxx",
      "phone_masked": "*******1956",
      "product_name": "学历提升",
      "city": "重庆",
      "path": "表单提交",
      "tags": "高意向",
      "ad_account": "账户1"
    }
  ],
  "comments": [
    {
      "nickname": "用户B",
      "has_lead": true,
      "content": "怎么报名",
      "comment_time": "13:20"
    }
  ],
  "high_intent_users": [
    {
      "nickname": "用户C",
      "avatar_url": "https://...",
      "comment_count": 3,
      "stay_duration": "8分钟",
      "status": "已留资"
    }
  ]
}
```

#### 5. 数据库
| 项目 | 内容 |
|------|------|
| 数据库 | SQLite (data.db) |
| 涉及表 | sessions, session_metrics, leads, comments, high_intent_users |
| 操作类型 | 事务写入（一次请求写5张表） |
| 事务保证 | 任一表写入失败则全部回滚 |

**写入顺序：**
```
1. sessions表 → 获得 session_id
2. session_metrics表（关联session_id）
3. leads表（批量插入，关联session_id）
4. comments表（批量插入，关联session_id）
5. high_intent_users表（批量插入，关联session_id）
```

#### 6. 响应
| 场景 | 响应 |
|------|------|
| 成功 | `{"code": 0, "message": "success", "session_id": 1}` |
| 重复 | `{"code": 400, "message": "场次已存在", "session_id": 1}` |
| 校验失败 | `{"code": 400, "message": "start_time不能为空"}` |
| 服务器错误 | `{"code": 500, "message": "数据库写入失败"}` |

### 文件操作

**修改：**

| 路径 | 修改点 |
|------|--------|
| `server/routers/api.py` | 从占位改为完整实现POST/GET两个接口 |

### 伪代码

**`server/routers/api.py` — 数据接收部分：**
```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession
from database import get_db
from models import Session, SessionMetric, Lead, Comment, HighIntentUser
from utils import parse_number, parse_time
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

router = APIRouter()

# ===== Pydantic 校验模型 =====
class LeadItem(BaseModel):
    lead_time: str
    nickname: str
    lead_id: Optional[str] = None
    phone_masked: Optional[str] = None
    product_name: Optional[str] = None
    city: Optional[str] = None
    path: Optional[str] = None
    tags: Optional[str] = None
    ad_account: Optional[str] = None

class CommentItem(BaseModel):
    nickname: str
    has_lead: bool = False
    content: Optional[str] = None
    comment_time: Optional[str] = None

class HighIntentItem(BaseModel):
    nickname: str
    avatar_url: Optional[str] = None
    comment_count: int = 0
    stay_duration: Optional[str] = None
    status: Optional[str] = None

class SessionData(BaseModel):
    start_time: str  # 必填
    end_time: str    # 必填
    metrics: dict    # 44字段字典
    _version: str = "1.0"  # X.4 数据格式版本号（两端协商机制）
    leads: List[LeadItem] = []
    comments: List[CommentItem] = []
    high_intent_users: List[HighIntentItem] = []

# ===== 防重复检查 =====
@router.get("/session/check")
def check_session(start_time: str, db: DBSession = Depends(get_db)):
    """检查start_time是否已入库"""
    parsed_time = parse_time(start_time)
    existing = db.query(Session).filter(Session.start_time == parsed_time).first()
    if existing:
        return {"code": 0, "exists": True, "session_id": existing.id}
    return {"code": 0, "exists": False}

# ===== 接收完整场次数据 =====
@router.post("/session")
SUPPORTED_VERSIONS = ["1.0"]

def receive_session(data: SessionData, db: DBSession = Depends(get_db)):
    """接收油猴脚本POST的单场完整数据"""
    # X.4 数据版本校验
    version = data.dict().get("_version", "1.0")
    if version not in SUPPORTED_VERSIONS:
        return {"code": 400, "message": f"不支持的数据版本: {version}，请更新油猴脚本"}
    # 1. 时间解析
    start = parse_time(data.start_time)
    end = parse_time(data.end_time)
    
    # 2. 防重复
    existing = db.query(Session).filter(Session.start_time == start).first()
    if existing:
        return {"code": 400, "message": "场次已存在", "session_id": existing.id}
    
    # 3. 计算时长
    start_dt = datetime.strptime(start, "%Y-%m-%d %H:%M:%S")
    end_dt = datetime.strptime(end, "%Y-%m-%d %H:%M:%S")
    duration_minutes = int((end_dt - start_dt).total_seconds() / 60)
    
    try:
        # 4. 写入sessions表
        session = Session(start_time=start, end_time=end, duration_minutes=duration_minutes)
        db.add(session)
        db.flush()  # 获取session.id
        
        # 5. 写入session_metrics表（解析44字段）
        # 2.1 过滤非SessionMetric字段，避免油猴脚本传入未知字段导致报错
        valid_columns = {c.name for c in SessionMetric.__table__.columns} - {'id', 'session_id', 'created_at'}
        from sqlalchemy import Integer as SAInt, Float as SAFloat
        metrics_data = {}
        for key, value in data.metrics.items():
            if key not in valid_columns:
                continue
            # 2.2 类型感知转换：按列定义的类型做精确转换
            col_type = SessionMetric.__table__.columns[key].type
            parsed = parse_number(value) if isinstance(value, str) else value
            if isinstance(col_type, SAInt):
                metrics_data[key] = int(parsed) if isinstance(parsed, (int, float)) else 0
            elif isinstance(col_type, SAFloat):
                metrics_data[key] = float(parsed) if isinstance(parsed, (int, float)) else 0.0
            else:
                metrics_data[key] = str(parsed) if parsed is not None else None
        metric = SessionMetric(session_id=session.id, **metrics_data)
        db.add(metric)
        
        # 6. 批量写入leads
        for lead_data in data.leads:
            lead = Lead(session_id=session.id, **lead_data.dict())
            db.add(lead)
        
        # 7. 批量写入comments
        for comment_data in data.comments:
            comment = Comment(session_id=session.id, **comment_data.dict())
            db.add(comment)
        
        # 8. 批量写入high_intent_users
        for hiu_data in data.high_intent_users:
            hiu = HighIntentUser(session_id=session.id, **hiu_data.dict())
            db.add(hiu)
        
        # 9. 提交事务
        db.commit()
        return {"code": 0, "message": "success", "session_id": session.id}
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"数据库写入失败: {str(e)}")
```

### 数据解析规则（来自功能设计文档5.2）

| 原始格式 | 解析结果 | 处理函数 |
|----------|----------|----------|
| "34,180" | 34180 (int) | parse_number → 去逗号 |
| "4.4万" | 44000 (int) | parse_number → ×10000 |
| "1,061.58" | 1061.58 (float) | parse_number → 去逗号 |
| "3.68%" | "3.68%" (text) | parse_number → 保持文本 |
| "30秒" | "30秒" (text) | parse_number → 保持文本 |
| "05-21 09：28" | "2026-05-21 09:28:00" | parse_time → 补年/秒/半角 |

### 关联关系
- `routers/api.py` ← 引用 `models.py`（ORM类）、`database.py`（get_db）、`utils.py`（解析函数）
- `routers/api.py` → 被 `main.py`（路由注册）引用
- `routers/api.py` → 被油猴脚本（Phase 3）HTTP调用

### 验收条件
- [ ] POST /api/session 接收JSON数据，返回 `{"code": 0, "session_id": N}`
- [ ] 数据正确写入5张表（sessions/metrics/leads/comments/high_intent）
- [ ] duration_minutes 自动计算正确（248分钟 for 09:28~13:36）
- [ ] 数值格式解析正确（"34,180"→34180, "4.4万"→44000）
- [ ] 时间格式解析正确（全角→半角，补年份和秒）
- [ ] 重复POST同一start_time返回 code=400
- [ ] GET /api/session/check 正确返回 exists 状态

---

## Task 2.2: 测试验证

### 任务描述
用 `.data/20260521_1336/` 目录下的真实样本数据构造测试请求，验证数据完整性。

### 执行逻辑

#### 1. 触发
| 项目 | 内容 |
|------|------|
| 触发条件 | Task 2.1 完成后 |
| 操作方式 | 编写测试脚本 / 使用curl或httpx |

#### 2. 测试数据来源

| 文件 | 提取内容 |
|------|----------|
| `.data/20260521_1336/05-21 09：28～05-21 13：36-*.csv` | 核心指标44字段 |
| `.data/20260521_1336/线索分析列表.csv` | 线索数据 |
| `.data/20260521_1336/评论.txt` | 评论DOM结构 |
| `.data/20260521_1336/高意向.txt` | 高意向用户DOM |

#### 3. 测试用例

| 测试项 | 输入 | 期望结果 |
|--------|------|----------|
| 正常接收 | 完整JSON（含metrics+leads+comments+hiu） | code=0, session_id=1 |
| 重复检查（不存在） | GET /api/session/check?start_time=xxx | exists=false |
| 正常接收后重复检查 | GET /api/session/check?start_time=2026-05-21 09:28:00 | exists=true, session_id=1 |
| 重复POST | 同一start_time再POST | code=400, message="场次已存在" |
| 缺少必填字段 | 无start_time | 422 Validation Error |
| 空线索列表 | leads=[] | 正常接收，leads表无记录 |
| 数值解析验证 | "34,180" | session_metrics.exposure_count=34180 |

### 伪代码

**测试脚本（验证后删除）：**
```python
import httpx

BASE = "http://localhost:8000/api"

# 1. 检查防重复（应不存在）
resp = httpx.get(f"{BASE}/session/check", params={"start_time": "05-21 09：28"})
assert resp.json()["exists"] == False

# 2.3 测试数据应从CSV构造，不手写少量字段
# 构造方式：读取 .data/20260521_1336/复盘表-时间指标单位为秒.csv 自动匹配44字段
import csv
with open(r'.data/20260521_1336/复盘表-时间指标单位为秒.csv', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    row = next(reader)  # 取第一行数据
    metrics_from_csv = {k: v for k, v in row.items() if v}
# POST完整数据
data = {
    "start_time": "05-21 09：28",
    "end_time": "05-21 13：36",
    "metrics": metrics_from_csv,  # 全部44字段
    "leads": [...],  # 从CSV提取
    "comments": [...],
    "high_intent_users": [...]
}
resp = httpx.post(f"{BASE}/session", json=data)
assert resp.json()["code"] == 0

# 3. 验证防重复
resp = httpx.get(f"{BASE}/session/check", params={"start_time": "05-21 09：28"})
assert resp.json()["exists"] == True

# 4. 重复POST
resp = httpx.post(f"{BASE}/session", json=data)
assert resp.json()["code"] == 400
```

### 验收条件
- [ ] 样本数据成功入库
- [ ] SQLite中sessions表有1条记录，duration_minutes=248
- [ ] session_metrics表44字段全部有值（非NULL的字段）
- [ ] leads表有4条记录（与CSV行数一致）
- [ ] 防重复逻辑生效
- [ ] 测试脚本执行后删除

---

## Phase 2 整体验收清单

- [ ] POST /api/session 可接收完整场次JSON数据
- [ ] GET /api/session/check 正确返回exists状态
- [ ] 5张表事务写入正确（任一失败全部回滚）
- [ ] 数值解析覆盖所有格式（逗号、万、百分比、秒）
- [ ] 时间解析正确（全角→半角，补年份+秒）
- [ ] duration_minutes自动计算正确
- [ ] Swagger /docs 展示完整API文档
- [ ] 用真实样本数据测试通过
