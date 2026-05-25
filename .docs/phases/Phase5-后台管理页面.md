# Phase 5: 后台管理页面 — 三级原子化执行方案

## Milestone 上下文

| 项 | 内容 |
|---|------|
| 所属Milestone | AliveBroadcastData 抖音直播数据分析系统 |
| 业务目标 | 提供需登录的后台管理界面，管理员可配置系统、标记成单、管理主播 |
| 在整体中的位置 | **第5个Phase**，依赖Phase 1（认证+数据库） |
| 被依赖方 | Phase 6（AI配置）、Phase 7（邮件配置）、Phase 9 |

## Phase 概要

| 项 | 内容 |
|---|------|
| 工期 | 3天 |
| 前置依赖 | Phase 1（auth.py + 数据库）|
| 产出文件 | 9个新建 + 2个修改 |
| 涉及模块 | 后台模板、JWT认证、CRUD API |
| 页面数 | 7个后台页面（登录+6个管理页） |

## 产出文件总览

| 文件路径 | 类型 | 用途 |
|----------|------|------|
| `server/templates/admin/base.html` | 新建 | 后台基础布局（侧边栏+内容区） |
| `server/templates/admin/login.html` | 新建 | 登录页 |
| `server/templates/admin/deals.html` | 新建 | 成单管理 |
| `server/templates/admin/anchors.html` | 新建 | 主播配置 |
| `server/templates/admin/ai_config.html` | 新建 | AI配置 |
| `server/templates/admin/email_config.html` | 新建 | 邮箱配置 |
| `server/templates/admin/settings.html` | 新建 | 系统设置 |
| `server/routers/admin.py` | 修改 | 后台管理API（从占位→完整实现） |
| `server/routers/pages.py` | 修改 | 新增后台页面路由 |

---

## Task 列表总览

| # | Task | 优先级 | 依赖 | 预估 |
|---|------|--------|------|------|
| 5.1 | 登录页 + Login API | P0 | Phase 1 | 2h |
| 5.2 | 后台布局 admin/base.html | P0 | Task 5.1 | 1h |
| 5.3 | 成单管理 + CRUD API | P0 | Task 5.2 | 4h |
| 5.4 | 主播配置 + CRUD API | P0 | Task 5.2 | 3h |
| 5.5 | AI配置 + Settings API | P1 | Task 5.2 | 2h |
| 5.6 | 邮箱配置 + Settings API | P1 | Task 5.2 | 2h |
| 5.7 | 系统设置（改密码+系统信息） | P1 | Task 5.2 | 2h |
| 5.8 | 线索标记 + 员工绩效统计 | P1 | Task 5.2 | 3h |

---

## Task 5.1: 登录页 + Login API

### 任务描述
实现登录页面和JWT登录接口，Token存localStorage，未登录重定向。

### 执行逻辑

#### 1. 触发
| 项目 | 内容 |
|------|------|
| 触发页面 | `/admin/login` |
| 触发事件 | 用户输入账号密码点击"登录" |

#### 2. 路由
| 项目 | 内容 |
|------|------|
| 页面路由 | GET `/admin/login` → pages.py → login.html |
| 登录API | POST `/admin/api/login` → admin.py |

#### 3. 逻辑处理
```
1. 用户提交 {"username":"admin","password":"admin123"}
2. 后端查询 settings 表中 admin_username 和 admin_password(哈希)
3. verify_password(输入密码, 存储哈希)
4. 成功 → create_token(username) → 返回 {"code":0,"token":"xxx"}
5. 失败 → 返回 {"code":401,"message":"账号或密码错误"}
6. 前端存 localStorage.setItem('admin_token', token)
7. 跳转 /admin/deals
```

#### 4. 数据库
| 项目 | 内容 |
|------|------|
| 涉及表 | settings |
| 查询键 | admin_username, admin_password |

#### 5. 响应
| 场景 | 响应 |
|------|------|
| 登录成功 | `{"code":0,"token":"eyJ..."}` |
| 密码错误 | `{"code":401,"message":"账号或密码错误"}` |

### 伪代码

**后端 — admin.py：**
```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession
from database import get_db
from models import Setting
from auth import verify_password, create_token, get_current_admin
from pydantic import BaseModel

router = APIRouter()

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/login")
def login(req: LoginRequest, db: DBSession = Depends(get_db)):
    stored_username = db.query(Setting).filter(Setting.key == "admin_username").first()
    stored_password = db.query(Setting).filter(Setting.key == "admin_password").first()
    
    if not stored_username or req.username != stored_username.value:
        raise HTTPException(401, detail="账号或密码错误")
    if not verify_password(req.password, stored_password.value):
        raise HTTPException(401, detail="账号或密码错误")
    
    token = create_token(req.username)
    return {"code": 0, "token": token}
```

**前端 — login.html：**
```html
{% extends "admin/base_login.html" %}  <!-- 登录页无侧边栏 -->
{% block content %}
<div x-data="loginApp()" class="min-h-screen flex items-center justify-center">
    <div class="bg-white p-8 rounded-lg shadow-md w-96">
        <h2 class="text-xl font-bold mb-6 text-center">后台管理登录</h2>
        <div class="mb-4">
            <input x-model="username" placeholder="账号" class="w-full border rounded px-3 py-2">
        </div>
        <div class="mb-4">
            <input x-model="password" type="password" placeholder="密码" class="w-full border rounded px-3 py-2">
        </div>
        <p x-show="error" x-text="error" class="text-red-500 text-sm mb-4"></p>
        <button @click="doLogin()" class="w-full bg-blue-600 text-white py-2 rounded hover:bg-blue-700">登 录</button>
    </div>
</div>
<script>
function loginApp() {
    return {
        username: '', password: '', error: '',
        async doLogin() {
            const resp = await fetch('/admin/api/login', {
                method: 'POST',
                headers: {'Content-Type':'application/json'},
                body: JSON.stringify({username:this.username, password:this.password})
            });
            const data = await resp.json();
            if (data.code === 0) {
                localStorage.setItem('admin_token', data.token);
                location.href = '/admin/deals';
            } else {
                this.error = data.detail || '登录失败';
            }
        }
    };
}
</script>
{% endblock %}
```

**前端 — JWT请求拦截（app.js中）：**
```javascript
// 后台API请求统一添加Token
async function adminFetch(url, options = {}) {
    const token = localStorage.getItem('admin_token');
    if (!token) { location.href = '/admin/login'; return; }
    options.headers = { ...options.headers, 'Authorization': `Bearer ${token}` };
    const resp = await fetch(url, options);
    if (resp.status === 401) { localStorage.removeItem('admin_token'); location.href = '/admin/login'; }
    return resp;
}
```

### 验收条件
- [ ] 登录页面正确显示
- [ ] admin/admin123 登录成功，返回token
- [ ] 错误密码返回401
- [ ] Token存入localStorage
- [ ] 登录成功后跳转 /admin/deals
- [ ] 未登录访问后台页面重定向到登录页

---

## Task 5.2: 后台布局 admin/base.html

### 任务描述
创建后台基础布局，含侧边栏导航（6个菜单项）和内容区域。

### 伪代码

```html
<!-- server/templates/admin/base.html -->
{% extends "base.html" %}
{% block content %}
<div class="flex min-h-[calc(100vh-4rem)]">
    <!-- 侧边栏 -->
    <aside class="w-56 bg-gray-800 text-white p-4">
        <nav class="space-y-2">
            <a href="/admin/deals" class="sidebar-link" :class="active==='deals'?'bg-gray-700':''">成单管理</a>
            <a href="/admin/anchors" class="sidebar-link">主播配置</a>
            <a href="/admin/ai" class="sidebar-link">AI配置</a>
            <a href="/admin/email" class="sidebar-link">邮箱配置</a>
            <a href="/admin/settings" class="sidebar-link">系统设置</a>
        </nav>
        <div class="mt-auto pt-4 border-t border-gray-700">
            <button @click="logout()" class="text-gray-400 hover:text-white">退出登录</button>
        </div>
    </aside>
    <!-- 内容区 -->
    <main class="flex-1 p-6 bg-gray-50">
        {% block admin_content %}{% endblock %}
    </main>
</div>
{% endblock %}
```

### 验收条件
- [ ] 侧边栏显示5个菜单+退出按钮
- [ ] 当前菜单高亮
- [ ] 退出按钮清除Token并跳转登录页
- [ ] 内容区自适应宽度

---

## Task 5.3: 成单管理 + CRUD API

### 任务描述
实现成单列表、新增弹窗（含场次/线索关联选择）、编辑/删除。

### 执行逻辑

#### 1. 路由
| 项目 | 内容 |
|------|------|
| 页面路由 | GET `/admin/deals` |
| API | GET `/admin/api/deals` — 成单列表 |
| API | POST `/admin/api/deals` — 新增成单 |
| API | PUT `/admin/api/deals/{id}` — 编辑成单 |
| API | DELETE `/admin/api/deals/{id}` — 删除成单 |

#### 2. 新增成单弹窗字段（来自界面交互文档4.3）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| 关联场次 | 下拉选择 | 否 | 搜索框支持按日期筛选 |
| 关联线索 | 下拉选择 | 否 | 仅显示所选场次下的线索 |
| 客户姓名 | 文本输入 | 是 | 最长50字符 |
| 成交金额 | 数字输入 | 是 | 单位元，保留2位小数 |
| 成交时间 | 日期选择器 | 是 | 默认今天 |
| 负责员工 | 文本输入 | 否 | |
| 备注 | 多行文本 | 否 | 最长200字符 |

**交互逻辑：**
- 选择"关联场次"后，"关联线索"下拉才可用
- 保存后自动更新 leads 表对应记录的 is_deal=true
- 删除需二次确认

#### 3. 伪代码

**后端 — admin.py（成单CRUD）：**
```python
class DealCreate(BaseModel):
    session_id: Optional[int] = None
    lead_id: Optional[int] = None
    customer_name: str
    amount: float
    deal_time: str
    employee: Optional[str] = None
    notes: Optional[str] = None

@router.get("/deals")
def list_deals(page: int = 1, size: int = 20, admin=Depends(get_current_admin), db=Depends(get_db)):
    query = db.query(Deal).order_by(Deal.created_at.desc())
    total = query.count()
    items = query.offset((page-1)*size).limit(size).all()
    return {"code":0, "data":{"items":[deal_to_dict(d) for d in items], "total":total}}

@router.post("/deals")
def create_deal(data: DealCreate, admin=Depends(get_current_admin), db=Depends(get_db)):
    deal = Deal(**data.dict())
    db.add(deal)
    # 自动标记线索为已成单
    if data.lead_id:
        lead = db.query(Lead).get(data.lead_id)
        if lead:
            lead.is_deal = True
    db.commit()
    return {"code":0, "message":"success", "deal_id": deal.id}

@router.put("/deals/{id}")
def update_deal(id: int, data: DealCreate, admin=Depends(get_current_admin), db=Depends(get_db)):
    deal = db.query(Deal).get(id)
    if not deal: raise HTTPException(404)
    for key, value in data.dict().items():
        setattr(deal, key, value)
    db.commit()
    return {"code":0}

@router.delete("/deals/{id}")
def delete_deal(id: int, admin=Depends(get_current_admin), db=Depends(get_db)):
    deal = db.query(Deal).get(id)
    if not deal: raise HTTPException(404)
    # 5.1 取消线索成单标记（先检查是否还有其他关联该线索的成单）
    if deal.lead_id:
        other_deals = db.query(Deal).filter(
            Deal.lead_id == deal.lead_id, Deal.id != id
        ).count()
        if other_deals == 0:
            lead = db.query(Lead).get(deal.lead_id)
            if lead: lead.is_deal = False  # 确认无其他成单才重置
    db.delete(deal)
    db.commit()
    return {"code":0}
```

### 验收条件
- [ ] 成单列表正确展示
- [ ] 新增弹窗7个字段全部可输入
- [ ] 场次下拉可搜索
- [ ] 选择场次后线索下拉联动
- [ ] 保存后leads表is_deal自动更新
- [ ] 编辑/删除正常（删除需二次确认）
- [ ] 所有API需JWT认证

---

## Task 5.4: 主播配置 + CRUD API

### 任务描述
实现主播列表、新增/删除主播、场次关联主播。

### 执行逻辑

#### 1. 路由
| API | 说明 |
|-----|------|
| GET /admin/api/anchors | 主播列表 |
| POST /admin/api/anchors | 新增主播 `{"name":"张三"}` |
| DELETE /admin/api/anchors/{id} | 删除主播 |
| POST /admin/api/sessions/{id}/anchors | 关联主播 `{"anchor_ids":[1,2]}` |

#### 2. 关联逻辑
- 一场直播可关联多个主播（session_anchors表多对多）
- 关联操作：先删除该场次旧关联，再批量插入新关联

### 伪代码

```python
@router.post("/sessions/{session_id}/anchors")
def bind_anchors(session_id: int, data: dict, admin=Depends(get_current_admin), db=Depends(get_db)):
    anchor_ids = data.get("anchor_ids", [])
    # 清除旧关联
    db.query(SessionAnchor).filter(SessionAnchor.session_id == session_id).delete()
    # 新建关联
    for aid in anchor_ids:
        db.add(SessionAnchor(session_id=session_id, anchor_id=aid))
    db.commit()
    return {"code":0}
```

### 验收条件
- [ ] 主播列表展示
- [ ] 新增主播（name唯一约束生效）
- [ ] 删除主播（级联删除session_anchors关联）
- [ ] 场次关联主播（多选）

---

## Task 5.5: AI配置 + Settings API

### 任务描述
实现AI配置页面（API Key/URL/Model/提示词），保存到settings表。

### 执行逻辑

#### 1. 路由
| API | 说明 |
|-----|------|
| GET /admin/api/settings | 获取所有配置 |
| PUT /admin/api/settings | 批量更新配置 |

#### 2. 配置键
`ai_api_key`, `ai_base_url`, `ai_model`, `ai_system_prompt`, `ai_user_prompt_template`

#### 3. 伪代码

```python
@router.get("/settings")
def get_settings(admin=Depends(get_current_admin), db=Depends(get_db)):
    settings = db.query(Setting).all()
    result = {s.key: s.value for s in settings}
    # 5.2 隐藏敏感字段（AI密镰+邮符1密码均脱敏）
    sensitive_keys = ['ai_api_key', 'email_password']
    for key in sensitive_keys:
        if key in result and result[key]:
            result[key] = result[key][:4] + '****'
    return {"code":0, "data": result}

@router.put("/settings")
def update_settings(data: dict, admin=Depends(get_current_admin), db=Depends(get_db)):
    for key, value in data.items():
        setting = db.query(Setting).filter(Setting.key == key).first()
        if setting:
            setting.value = value
            setting.updated_at = datetime.now().isoformat()
        else:
            db.add(Setting(key=key, value=value))
    db.commit()
    return {"code":0}
```

### 验收条件
- [ ] AI配置页面5个字段显示正确
- [ ] API Key显示为部分隐藏（前8位+****）
- [ ] 保存成功更新settings表
- [ ] 测试连接按钮（调用AI API验证可用性）

---

## Task 5.6: 邮箱配置 + Settings API

### 任务描述
实现邮箱配置页面（SMTP信息+收件人列表），测试发送按钮。

### 配置键
`email_smtp_host`, `email_smtp_port`, `email_sender`, `email_password`, `email_receivers`

### 特殊交互
- 收件人列表：动态添加/删除邮箱（email_receivers存为JSON数组）
- 测试邮件：POST /admin/api/email/test → 调用email_service发送测试邮件

### 伪代码

```python
@router.post("/email/test")
def test_email(admin=Depends(get_current_admin), db=Depends(get_db)):
    # 读取当前邮箱配置
    config = {s.key: s.value for s in db.query(Setting).filter(Setting.key.like("email_%")).all()}
    receivers = json.loads(config.get("email_receivers", "[]"))
    if not receivers:
        return {"code":400, "message":"请先配置收件人"}
    # 发送测试邮件
    try:
        send_email(
            subject="【测试】直播数据系统邮件测试",
            html="<h1>测试邮件</h1><p>如果您收到此邮件，说明邮箱配置正确。</p>",
            config=config,
            receivers=receivers
        )
        return {"code":0, "message":"测试邮件已发送"}
    except Exception as e:
        return {"code":500, "message": f"发送失败: {str(e)}"}
```

### 验收条件
- [ ] SMTP配置4字段可编辑保存
- [ ] 收件人列表动态添加/删除
- [ ] 测试邮件发送成功
- [ ] 配置错误时返回明确错误信息

---

## Task 5.7: 系统设置

### 任务描述
实现修改管理员密码、显示系统信息。

### 执行逻辑

#### 修改密码
```python
@router.put("/settings/password")
def change_password(data: dict, admin=Depends(get_current_admin), db=Depends(get_db)):
    old_pwd = data.get("old_password")
    new_pwd = data.get("new_password")
    stored = db.query(Setting).filter(Setting.key == "admin_password").first()
    if not verify_password(old_pwd, stored.value):
        return {"code":400, "message":"原密码错误"}
    stored.value = hash_password(new_pwd)
    db.commit()
    return {"code":0, "message":"密码修改成功"}
```

#### 系统信息
- 数据库文件大小：`os.path.getsize("data.db")`
- 最近同步时间：`sessions表最新created_at`
- 场次总数、线索总数

### 验收条件
- [ ] 修改密码：旧密码验证+新密码更新
- [ ] 系统信息正确显示

---

## Task 5.8: 线索标记 + 员工绩效统计

### 任务描述
实现线索有效性单条/批量标记、员工绩效统计API。

### 路由

| API | 说明 |
|-----|------|
| PUT /admin/api/leads/{id} | 单条标记 `{"is_valid":true}` |
| POST /admin/api/leads/batch | 批量标记 `{"lead_ids":[1,2,3],"is_valid":true}` |
| GET /admin/api/employee/stats | 员工绩效 |

### 员工绩效统计

```python
@router.get("/employee/stats")
def employee_stats(date_from: str = None, date_to: str = None, admin=Depends(get_current_admin), db=Depends(get_db)):
    query = db.query(
        Deal.employee,
        func.count(Deal.id).label('deal_count'),
        func.sum(Deal.amount).label('total_amount'),
        func.avg(Deal.amount).label('avg_amount')
    ).group_by(Deal.employee)
    
    if date_from:
        query = query.filter(Deal.deal_time >= date_from)
    if date_to:
        query = query.filter(Deal.deal_time <= date_to)
    
    results = query.all()
    return {"code":0, "data":[
        {"employee":r.employee, "deal_count":r.deal_count, "total_amount":float(r.total_amount or 0), "avg_amount":float(r.avg_amount or 0)}
        for r in results
    ]}
```

### 验收条件
- [ ] 单条线索标记有效/无效/未验证
- [ ] 批量标记线索
- [ ] 员工绩效统计按日期范围筛选
- [ ] 所有API需JWT认证

---

## Phase 5 整体验收清单

- [ ] 登录页面正常（admin/admin123）
- [ ] 未登录访问后台重定向到登录页
- [ ] JWT Token过期处理（7天后重新登录）
- [ ] 后台侧边栏5个菜单全部可用
- [ ] 成单CRUD全流程（新增/编辑/删除/列表）
- [ ] 成单关联场次和线索联动
- [ ] 主播CRUD + 场次关联主播
- [ ] AI配置保存+测试连接
- [ ] 邮箱配置保存+测试发送
- [ ] 修改密码正常
- [ ] 线索单条/批量标记
- [ ] 员工绩效统计正确
