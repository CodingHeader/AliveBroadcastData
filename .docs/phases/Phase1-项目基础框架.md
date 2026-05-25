# Phase 1: 项目基础框架 — 三级原子化执行方案

## Milestone 上下文

| 项 | 内容 |
|---|------|
| 所属Milestone | AliveBroadcastData 抖音直播数据分析系统 |
| 业务目标 | 搭建项目骨架，使后续所有Phase有稳定的运行基座 |
| 在整体中的位置 | **第1个Phase**，无前置依赖，所有后续Phase依赖此Phase |
| 被依赖方 | Phase 2/3/4/5/6/7/8/9 均依赖本Phase |

## Phase 概要

| 项 | 内容 |
|---|------|
| 工期 | 2天 |
| 前置依赖 | 无 |
| 产出文件 | 12个新建文件 |
| 涉及模块 | 后端框架、数据库、认证、配置 |
| 技术栈 | Python 3.11+, FastAPI, SQLAlchemy 2.0, python-jose, bcrypt, APScheduler |

## 产出文件总览

| 文件路径 | 类型 | 用途 |
|----------|------|------|
| `server/requirements.txt` | 新建 | Python依赖清单 |
| `server/config.py` | 新建 | 配置常量 |
| `server/database.py` | 新建 | 数据库连接+建表+Session管理 |
| `server/models.py` | 新建 | 10张表ORM模型定义 |
| `server/auth.py` | 新建 | JWT认证+密码哈希 |
| `server/main.py` | 新建 | FastAPI入口 |
| `server/routers/__init__.py` | 新建 | 路由包初始化 |
| `server/routers/api.py` | 新建 | 占位（Phase 2填充） |
| `server/routers/admin.py` | 新建 | 占位（Phase 5填充） |
| `server/routers/pages.py` | 新建 | 占位（Phase 4填充） |
| `server/services/__init__.py` | 新建 | 服务包初始化 |
| `server/utils.py` | 新建 | 通用工具函数 |

---

## Task 列表总览

| # | Task | 优先级 | 依赖 | 预估 |
|---|------|--------|------|------|
| 1.1 | 项目初始化（目录+依赖+配置） | P0 | - | 2h |
| 1.2 | 数据库层（ORM模型+连接管理） | P0 | Task 1.1 | 4h |
| 1.3 | 认证模块（JWT+密码哈希） | P0 | Task 1.1 | 2h |
| 1.4 | FastAPI入口（应用实例+启动） | P0 | Task 1.1/1.2/1.3 | 2h |

---

## Task 1.1: 项目初始化

### 任务描述
创建项目目录结构，编写 `requirements.txt` 和 `config.py`，确保所有依赖可安装。

### 执行逻辑

#### 1. 触发
| 项目 | 内容 |
|------|------|
| 触发条件 | Phase 1 开始 |
| 操作类型 | 文件创建 |

#### 2. 文件操作

**新建：**

| 路径 | 用途 |
|------|------|
| `server/` | 后端代码主目录 |
| `server/routers/` | API路由模块目录 |
| `server/services/` | 业务服务模块目录 |
| `server/templates/` | Jinja2模板目录 |
| `server/templates/admin/` | 后台模板子目录 |
| `server/templates/email/` | 邮件模板子目录 |
| `server/static/css/` | CSS静态资源目录 |
| `server/static/js/` | JS静态资源目录 |
| `tampermonkey/` | 油猴脚本目录 |

#### 3. 伪代码

**`server/requirements.txt`：**
```
fastapi==0.104.1
uvicorn[standard]==0.24.0
sqlalchemy==2.0.23
apscheduler==3.10.4
openai==1.6.0
python-jose[cryptography]==3.3.0
bcrypt==4.1.2
passlib[bcrypt]==1.7.4
jinja2==3.1.2
python-multipart==0.0.6
openpyxl==3.1.2
aiofiles==23.2.1
httpx==0.25.2
```

**`server/config.py`：**
```python
import os
from pathlib import Path

# 项目路径
BASE_DIR = Path(__file__).resolve().parent

# 数据库
DATABASE_URL = f"sqlite:///{BASE_DIR / 'data.db'}"

# JWT认证
SECRET_KEY = os.getenv("SECRET_KEY", "alive-broadcast-data-secret-key-2026")
TOKEN_EXPIRE_DAYS = 7
ALGORITHM = "HS256"

# 默认管理员
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin123"

# 服务器
HOST = "0.0.0.0"
PORT = 8000

# 日志（X.2 统一规范）
import logging
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
```

### 数据结构
无（配置常量）

### 关联关系
- `config.py` → 被 `database.py`、`auth.py`、`main.py` 引用
- `requirements.txt` → 被 `pip install -r` 安装依赖

### 验收条件
- [ ] `server/` 目录结构创建完成（routers/、services/、templates/、static/）
- [ ] `pip install -r server/requirements.txt` 安装成功无报错
- [ ] `config.py` 可被其他模块正常 import

---

## Task 1.2: 数据库层

### 任务描述
编写 SQLAlchemy ORM 模型（10张表），创建数据库连接管理和 Session 依赖注入。

### 执行逻辑

#### 1. 触发
| 项目 | 内容 |
|------|------|
| 触发条件 | Task 1.1 完成后 |
| 操作类型 | 文件创建 |

#### 2. 路由
无（数据层，不涉及HTTP路由）

#### 3. 逻辑处理
| 项目 | 内容 |
|------|------|
| 处理目录 | `server/` |
| 处理文件 | `database.py` + `models.py` |
| 核心功能 | 建表、连接管理、Session注入 |

#### 4. 数据库

**10张表定义：**

| 表名 | 字段数 | 关键字段 | 索引 |
|------|--------|----------|------|
| sessions | 7 | start_time(UNIQUE), analyzed, duration_minutes | idx_sessions_start_time |
| session_metrics | 45 | session_id(FK), 44个指标字段 | idx_metrics_session |
| leads | 13 | session_id(FK), lead_time, is_valid, is_deal | idx_leads_session |
| comments | 7 | session_id(FK), nickname, content | - |
| high_intent_users | 7 | session_id(FK), nickname, status | - |
| reports | 6 | session_id(FK nullable), report_type, period | - |
| anchors | 3 | name(UNIQUE) | - |
| session_anchors | 3 | session_id(FK), anchor_id(FK), UNIQUE约束 | - |
| deals | 9 | session_id(FK), lead_id(FK), amount, deal_time | - |
| settings | 4 | key(UNIQUE), value | - |

### 文件操作

**新建：**

| 路径 | 用途 |
|------|------|
| `server/database.py` | 引擎创建+Session管理+建表 |
| `server/models.py` | 10张表ORM类定义 |

### 伪代码

**`server/database.py`：**
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 1.1 WAL模式 + busy_timeout（防止并发写入锁冲突）
from sqlalchemy import event
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()

class Base(DeclarativeBase):
    pass

def init_db():
    """创建所有表 + 初始化默认配置"""
    Base.metadata.create_all(bind=engine)
    # 初始化settings默认值（admin密码哈希等）

def get_db():
    """FastAPI依赖注入: 提供数据库Session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

**`server/models.py` 核心结构：**
```python
from sqlalchemy import Column, Integer, Text, Boolean, Float, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from database import Base

# 1.2 命名约定：导入时使用别名避免与SQLAlchemy Session冲突
# from models import Session as LiveSession  （在路由中推荐使用此别名）
# from sqlalchemy.orm import Session as DBSession  （依赖注入使用）
class Session(Base):
    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    start_time = Column(Text, nullable=False, unique=True)
    end_time = Column(Text, nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    analyzed = Column(Boolean, default=False)
    analyzed_at = Column(Text, nullable=True)
    created_at = Column(Text, server_default="CURRENT_TIMESTAMP")
    # relationships
    metrics = relationship("SessionMetric", back_populates="session")
    leads = relationship("Lead", back_populates="session")
    comments = relationship("Comment", back_populates="session")
    high_intent_users = relationship("HighIntentUser", back_populates="session")
    anchors = relationship("SessionAnchor", back_populates="session")

class SessionMetric(Base):
    __tablename__ = "session_metrics"
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    # 44个指标字段... (exposure_count, cumulative_viewers, ...)
    session = relationship("Session", back_populates="metrics")

class Lead(Base):
    __tablename__ = "leads"
    # 13字段: id, session_id, lead_time, nickname, lead_id, phone_masked,
    #         product_name, city, path, tags, ad_account, is_valid, is_deal, created_at

class Comment(Base):
    __tablename__ = "comments"
    # 7字段: id, session_id, nickname, has_lead, content, comment_time, created_at

class HighIntentUser(Base):
    __tablename__ = "high_intent_users"
    # 7字段: id, session_id, nickname, avatar_url, comment_count, stay_duration, status, created_at

class Report(Base):
    __tablename__ = "reports"
    # 6字段: id, session_id(nullable), report_type, period, content, generated_at

class Anchor(Base):
    __tablename__ = "anchors"
    # 3字段: id, name(unique), created_at

class SessionAnchor(Base):
    __tablename__ = "session_anchors"
    # 3字段: id, session_id(FK), anchor_id(FK)
    __table_args__ = (UniqueConstraint("session_id", "anchor_id"),)

class Deal(Base):
    __tablename__ = "deals"
    # 9字段: id, session_id, lead_id, customer_name, amount, deal_time, employee, notes, created_at

class Setting(Base):
    __tablename__ = "settings"
    # 4字段: id, key(unique), value, updated_at
```

### 数据结构
详见上方10张表定义，字段完整规格参照 `功能设计文档.md` 第三章。

### 关联关系
- `models.py` → 被 `database.py`（init_db）引用
- `models.py` → 被 `routers/api.py`、`routers/admin.py`、`services/*.py` 引用
- `database.py` → 被 `main.py`（启动时init_db）、所有路由（get_db依赖）引用
- `database.py` ← 引用 `config.py`（DATABASE_URL）

### 验收条件
- [ ] `python -c "from models import *; from database import init_db; init_db()"` 执行无报错
- [ ] `data.db` 文件生成，sqlite3打开可见10张表
- [ ] 每张表字段与功能设计文档一致（逐字段核对）
- [ ] 外键关系正确（session_id关联sessions.id等）
- [ ] settings表有13个预置配置项

---

## Task 1.3: 认证模块

### 任务描述
编写JWT Token生成/验证、bcrypt密码哈希/验证、FastAPI依赖函数 `get_current_admin`。

### 执行逻辑

#### 1. 触发
| 项目 | 内容 |
|------|------|
| 触发条件 | Task 1.1 完成后（与Task 1.2可并行） |
| 调用场景 | 后台管理API请求时验证身份 |

#### 2. 路由
| 项目 | 内容 |
|------|------|
| 后端API | POST /admin/api/login（Phase 5实现，本Task提供工具函数） |
| 认证头 | Authorization: Bearer {token} |

#### 3. 逻辑处理
| 项目 | 内容 |
|------|------|
| 处理文件 | `server/auth.py` |
| 核心函数 | create_token / verify_token / hash_password / verify_password / get_current_admin |

### 文件操作

**新建：**

| 路径 | 用途 |
|------|------|
| `server/auth.py` | JWT认证 + 密码哈希工具 |

### 伪代码

**`server/auth.py`：**
```python
from datetime import datetime, timedelta
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from config import SECRET_KEY, ALGORITHM, TOKEN_EXPIRE_DAYS

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

def hash_password(password: str) -> str:
    """密码 → bcrypt哈希"""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证明文密码与哈希是否匹配"""
    return pwd_context.verify(plain_password, hashed_password)

def create_token(username: str) -> str:
    """生成JWT Token，有效期7天"""
    expire = datetime.utcnow() + timedelta(days=TOKEN_EXPIRE_DAYS)
    payload = {"sub": username, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str) -> str:
    """验证Token，返回username；失败抛异常"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="无效Token")
        return username
    except JWTError:
        raise HTTPException(status_code=401, detail="Token过期或无效")

async def get_current_admin(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """FastAPI依赖：验证后台请求的JWT Token"""
    return verify_token(credentials.credentials)
```

### 数据结构

**JWT Payload：**
```json
{
  "sub": "admin",
  "exp": 1716422400
}
```

### 关联关系
- `auth.py` ← 引用 `config.py`（SECRET_KEY, ALGORITHM, TOKEN_EXPIRE_DAYS）
- `auth.py` → 被 `routers/admin.py`（get_current_admin依赖）引用
- `auth.py` → 被 `database.py`（init_db中hash默认密码）引用

### 验收条件
- [ ] `hash_password("admin123")` 返回bcrypt哈希字符串
- [ ] `verify_password("admin123", hashed)` 返回 True
- [ ] `create_token("admin")` 返回合法JWT字符串
- [ ] `verify_token(valid_token)` 返回 "admin"
- [ ] `verify_token("invalid")` 抛出 HTTPException 401

---

## Task 1.4: FastAPI入口

### 任务描述
创建FastAPI应用实例，注册路由、静态文件、模板引擎，启动时初始化数据库。

### 执行逻辑

#### 1. 触发
| 项目 | 内容 |
|------|------|
| 触发条件 | Task 1.1/1.2/1.3 全部完成 |
| 操作类型 | 创建应用入口 |

#### 2. 路由
| 项目 | 内容 |
|------|------|
| 路由注册 | api_router, admin_router, pages_router |
| 静态文件 | /static → server/static/ |
| CORS | 允许所有来源（油猴脚本跨域） |

#### 3. 逻辑处理
| 项目 | 内容 |
|------|------|
| 处理文件 | `server/main.py` |
| 启动流程 | 创建app → 注册CORS → 挂载静态文件 → 注册路由 → init_db → uvicorn.run |

### 文件操作

**新建：**

| 路径 | 用途 |
|------|------|
| `server/main.py` | 应用入口 |
| `server/routers/__init__.py` | 路由包 |
| `server/routers/api.py` | 前台API路由（占位） |
| `server/routers/admin.py` | 后台API路由（占位） |
| `server/routers/pages.py` | 页面路由（占位） |
| `server/services/__init__.py` | 服务包 |
| `server/utils.py` | 工具函数 |

### 伪代码

**`server/main.py`：**
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
from database import init_db
from routers import api, admin, pages

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时
    init_db()
    yield
    # 关闭时（如需清理）

app = FastAPI(title="AliveBroadcastData", lifespan=lifespan)

# CORS（允许油猴脚本跨域）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")

# 模板
templates = Jinja2Templates(directory="templates")

# 注册路由
app.include_router(api.router, prefix="/api", tags=["前台API"])
app.include_router(admin.router, prefix="/admin/api", tags=["后台API"])
app.include_router(pages.router, tags=["页面"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
```

**`server/routers/api.py`（占位）：**
```python
from fastapi import APIRouter
router = APIRouter()

# Phase 2/4 填充具体路由
```

**`server/routers/admin.py`（占位）：**
```python
from fastapi import APIRouter
router = APIRouter()

# Phase 5 填充具体路由
```

**`server/routers/pages.py`（占位）：**
```python
from fastapi import APIRouter
router = APIRouter()

# Phase 4/5 填充具体路由
```

**`server/utils.py`：**
```python
import re
from datetime import datetime

def parse_number(text: str):
    """数值格式化: "4.4万"→44000, "34,180"→34180, "3.68%"→"3.68%" """
    if not text or text == "--":
        return None
    text = text.strip()
    if "万" in text:
        return int(float(text.replace("万", "")) * 10000)
    if "%" in text:
        return text  # 百分比保持文本存储
    text = text.replace(",", "")
    try:
        if "." in text:
            return float(text)
        return int(text)
    except ValueError:
        return text  # 无法解析则保持原文本

def parse_time(text: str) -> str:
    """时间补全: "05-21 09：28" → "2026-05-21 09:28:00" """
    # 1.4 兼容已含年份的完整格式（如AI分析报告中的2026-05-21 09:28:38）
    if re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", text):
        return text
    text = text.replace("：", ":")  # 全角→半角
    now = datetime.now()
    # 解析月-日 时:分格式
    match = re.match(r"(\d{2})-(\d{2})\s+(\d{2}):(\d{2})(?::(\d{2}))?", text)
    if match:
        month, day, hour, minute = int(match.group(1)), int(match.group(2)), int(match.group(3)), int(match.group(4))
        second = int(match.group(5)) if match.group(5) else 0
        year = now.year if month <= now.month else now.year - 1
        return f"{year}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}"
    return text

def format_duration(minutes: int) -> str:
    """时长格式化: 248 → "4h8min" """
    h, m = divmod(minutes, 60)
    if h > 0:
        return f"{h}h{m}min"
    return f"{m}min"
```

### 关联关系
- `main.py` ← 引用 `database.py`（init_db）、`routers/*`（路由注册）
- `main.py` → 被 `uvicorn` 启动命令引用
- `utils.py` → 被 `routers/api.py`（数据解析）引用
- 所有 `routers/*.py` ← 引用 `database.py`（get_db）、`models.py`

### 验收条件
- [ ] `cd server && python main.py` 启动无报错
- [ ] 浏览器访问 `http://localhost:8000/docs` 可见 Swagger 文档
- [ ] `data.db` 文件自动创建
- [ ] CORS 配置生效（跨域请求不被阻止）
- [ ] `/static/` 路径可访问静态资源

---

## Phase 1 整体验收清单

- [ ] 项目目录结构完整（server/routers/, server/services/, server/templates/, server/static/, tampermonkey/）
- [ ] `pip install -r requirements.txt` 无报错
- [ ] `python main.py` 启动成功，端口8000监听
- [ ] SQLite `data.db` 自动生成，包含10张表
- [ ] 所有表字段与功能设计文档第三章完全一致
- [ ] settings表包含13个预置配置项（admin_username ~ push_frequency）
- [ ] JWT认证函数正常工作（生成/验证Token）
- [ ] bcrypt密码哈希正常（默认admin123正确验证）
- [ ] Swagger文档 `/docs` 可正常访问
- [ ] CORS中间件已配置
