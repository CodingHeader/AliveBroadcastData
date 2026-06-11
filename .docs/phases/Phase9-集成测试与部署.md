# Phase 9: 集成测试与部署 — 三级原子化执行方案

## Milestone 上下文

| 项 | 内容 |
|---|------|
| 所属Milestone | AliveBroadcastData 抖音直播数据分析系统 |
| 业务目标 | 验证全链路可用性，编写部署文档，交付可运行系统 |
| 在整体中的位置 | **第9个Phase（最终阶段）**，依赖所有前序Phase |
| 被依赖方 | 无（项目交付） |

## Phase 概要

| 项 | 内容 |
|---|------|
| 工期 | 1天 |
| 前置依赖 | Phase 1~8 全部完成 |
| 产出文件 | 3个新建 + 可能若干修改 |
| 涉及模块 | 端到端测试、部署脚本、文档 |

## 产出文件总览

| 文件路径 | 类型 | 用途 |
|----------|------|------|
| `start.bat` | 新建 | Windows启动脚本 |
| `start.sh` | 新建 | Linux启动脚本 |
| `README.md` | 修改 | 完整安装使用说明 |

---

## Task 列表总览

| # | Task | 优先级 | 依赖 | 预估 |
|---|------|--------|------|------|
| 9.1 | 端到端测试 | P0 | Phase 1~8 | 4h |
| 9.2 | 部署脚本+文档 | P0 | Task 9.1 | 2h |
| 9.3 | 油猴脚本安装验证 | P0 | Task 9.1 | 1h |

---

## Task 9.1: 端到端测试

### 任务描述
验证完整链路：油猴采集→API接收→数据入库→看板展示→AI分析→报告生成→邮件推送→后台管理。

### 执行逻辑

#### 测试链路1：数据采集→入库→展示

| 步骤 | 操作 | 验证点 |
|------|------|--------|
| 1 | 手动POST样本数据到 /api/session | 返回 code=0, session_id |
| 2 | GET /api/session/check | exists=true |
| 3 | 访问 / 看板首页 | KPI卡片显示数据 |
| 4 | 点击场次进入详情 | 8个Tab数据完整 |
| 5 | 再次POST相同数据 | 防重复返回 code=400 |

#### 测试链路2：AI分析→报告→邮件

| 步骤 | 操作 | 验证点 |
|------|------|--------|
| 1 | 后台配置AI API Key | 保存成功 |
| 2 | 手动触发分析 | 返回Markdown报告 |
| 3 | 查看报告中心 | 列表中出现session类型报告 |
| 4 | 下载报告 | .md文件正确 |
| 5 | 后台配置邮箱 | SMTP信息+收件人 |
| 6 | 发送测试邮件 | 收到HTML邮件 |

#### 测试链路3：后台管理

| 步骤 | 操作 | 验证点 |
|------|------|--------|
| 1 | 访问 /admin/login | 登录页显示 |
| 2 | admin/admin123 登录 | 跳转成单管理页 |
| 3 | 新增主播"张三" | 主播列表出现 |
| 4 | 场次关联主播 | 场次详情显示主播 |
| 5 | 新增成单 | 成单列表+线索is_deal更新 |
| 6 | 修改密码 | 旧密码登录失败，新密码成功 |
| 7 | 未登录访问后台 | 重定向到登录页 |
| 8 | Token过期 | 返回401 |

#### 测试链路4：前台全功能

| 步骤 | 操作 | 验证点 |
|------|------|--------|
| 1 | 看板时间切换（日/周/月） | 数据刷新正确 |
| 2 | 趋势分析筛选 | 折线图+柱状图+热力图 |
| 3 | 线索总览筛选 | 列表+饼图联动 |
| 4 | 导出场次Excel | 下载.xlsx文件 |
| 5 | 导出线索Excel | 下载.xlsx文件 |
| 6 | 移动端访问 | 响应式布局正常 |

#### 测试链路5：异常场景

| 步骤 | 操作 | 验证点 |
|------|------|--------|
| 1 | POST空数据 | 422校验错误 |
| 2 | AI API Key错误 | 返回明确错误信息 |
| 3 | SMTP配置错误 | 邮件发送失败有错误日志 |
| 4 | 大量数据POST | 无超时，事务正常 |
| 5 | 并发写入SQLite | WAL模式下不冲突 |

#### 测试链路6：定时任务验证

| 步骤 | 操作 | 验证点 |
|------|------|--------|
| 1 | 调用 `/admin/api/trigger/daily_report` | 日报立即生成 |
| 2 | 检查 `data/reports/` 目录 | Markdown文件已创建 |
| 3 | 调用 `/admin/api/trigger/analyze` | AI分析任务执行 |
| 4 | 等待5分钟后检查数据库 | `ai_summary` 字段已填充 |
| 5 | 检查 `backups/` 目录 | 昨日数据库备份存在 |

### 伪代码（自动化测试脚本，验证后删除）

```python
"""端到端测试脚本 — 验证完成后删除"""
import httpx
import json
import time

BASE = "http://localhost:8000"

def test_full_flow():
    # ===== 链路1：数据接收 =====
    print("=== 测试链路1：数据接收 ===")
    
    # 检查防重复（应不存在）
    resp = httpx.get(f"{BASE}/api/session/check", params={"start_time": "05-21 09：28"})
    assert resp.json()["exists"] == False, "防重复检查失败"
    
    # POST样本数据
    sample_data = {
        "start_time": "05-21 09：28",
        "end_time": "05-21 13：36",
        "metrics": {
            "exposure_count": "34,180",
            "cumulative_viewers": "1,258",
            "ad_spend": "1,061.58",
            "total_leads": "4",
            "max_online": "16",
            "avg_watch_duration": "30秒",
            # ... 其余字段
        },
        "leads": [
            {"lead_time":"05-21 13:17","nickname":"测试用户","city":"重庆","path":"表单","ad_account":"账户1"}
        ],
        "comments": [
            {"nickname":"评论用户","has_lead":False,"content":"怎么报名","comment_time":"13:20"}
        ],
        "high_intent_users": [
            {"nickname":"高意向A","comment_count":3,"stay_duration":"8分钟","status":"已留资"}
        ]
    }
    resp = httpx.post(f"{BASE}/api/session", json=sample_data)
    result = resp.json()
    assert result["code"] == 0, f"数据接收失败: {result}"
    session_id = result["session_id"]
    print(f"  ✓ 数据接收成功, session_id={session_id}")
    
    # 防重复
    resp = httpx.post(f"{BASE}/api/session", json=sample_data)
    assert resp.json()["code"] == 400, "防重复失败"
    print("  ✓ 防重复检查通过")
    
    # ===== 链路2：看板展示 =====
    print("\n=== 测试链路2：看板展示 ===")
    
    resp = httpx.get(f"{BASE}/api/dashboard?range=week")
    data = resp.json()["data"]
    assert data["current"]["sessions"] > 0, "看板无场次数据"
    print(f"  ✓ Dashboard API正常, 场次={data['current']['sessions']}")
    
    # 场次详情
    resp = httpx.get(f"{BASE}/api/sessions/{session_id}")
    detail = resp.json()["data"]
    assert detail["session"]["id"] == session_id
    assert len(detail["leads"]) > 0
    print(f"  ✓ 场次详情正常, leads={len(detail['leads'])}")
    
    # ===== 链路3：后台管理 =====
    print("\n=== 测试链路3：后台管理 ===")
    
    # 登录
    resp = httpx.post(f"{BASE}/admin/api/login", json={"username":"admin","password":"admin123"})
    assert resp.json()["code"] == 0
    token = resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("  ✓ 登录成功")
    
    # 新增主播
    resp = httpx.post(f"{BASE}/admin/api/anchors", json={"name":"测试主播"}, headers=headers)
    assert resp.json()["code"] == 0
    print("  ✓ 主播新增成功")
    
    # 新增成单
    resp = httpx.post(f"{BASE}/admin/api/deals", json={
        "session_id": session_id,
        "customer_name": "测试客户",
        "amount": 3980,
        "deal_time": "2026-05-21",
    }, headers=headers)
    assert resp.json()["code"] == 0
    print("  ✓ 成单新增成功")
    
    # 错误密码登录
    resp = httpx.post(f"{BASE}/admin/api/login", json={"username":"admin","password":"wrong"})
    assert resp.status_code == 401
    print("  ✓ 错误密码拒绝登录")
    
    # 无Token访问后台API
    resp = httpx.get(f"{BASE}/admin/api/deals")
    assert resp.status_code in [401, 403]
    print("  ✓ 无Token拒绝访问")
    
    print("\n===== 全部测试通过 =====")

if __name__ == "__main__":
    test_full_flow()
```

### 验收条件
- [ ] 6条测试链路全部通过
- [ ] 无控制台错误/500响应
- [ ] 数据一致性（入库数据=展示数据）
- [ ] 测试脚本执行后删除

---

## Task 9.2: 部署脚本+文档

### 任务描述
编写Windows/Linux启动脚本和完整README。

### 文件操作

**新建/修改：**

| 路径 | 用途 |
|------|------|
| `start.bat` | Windows一键启动 |
| `start.sh` | Linux一键启动 |
| `README.md` | 安装使用说明 |

### 伪代码

**`start.bat`：**
```batch
@echo off

REM 9.2 端口占用检查
netstat -ano | findstr ":8000" >nul 2>&1
if not errorlevel 1 (
    echo [警告] 端口8000已被占用，请先关闭占用进程
    pause
    exit /b 1
)
echo === AliveBroadcastData 启动 ===
cd /d %~dp0\server

REM 检查Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到Python，请先安装Python 3.11+
    pause
    exit /b 1
)

REM 安装依赖
if not exist "venv" (
    echo 创建虚拟环境...
    python -m venv venv
)
call venv\Scripts\activate
pip install -r requirements.txt -q

REM 启动服务
echo 启动服务 http://0.0.0.0:8000
python main.py
pause
```

**`start.sh`：**
```bash
#!/bin/bash
echo "=== AliveBroadcastData 启动 ==="
cd "$(dirname "$0")/server"

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未找到Python3"
    exit 1
fi

# 虚拟环境
if [ ! -d "venv" ]; then
    echo "创建虚拟环境..."
    python3 -m venv venv
fi
source venv/bin/activate
pip install -r requirements.txt -q

# 启动
echo "启动服务 http://0.0.0.0:8000"
python main.py
```

**`README.md` 结构：**
```markdown
# AliveBroadcastData — 抖音直播数据分析系统

## 功能
- 自动采集抖音来客线索大屏数据
- 数据看板（KPI+趋势+场次+漏斗）
- AI分析报告（自动+手动）
- 邮件推送（HTML日报）
- 后台管理（成单/主播/AI/邮箱/系统设置）

## 快速开始

### 1. 启动服务端
- Windows: 双击 `start.bat`
- Linux: `chmod +x start.sh && ./start.sh`

### 2. 安装油猴脚本
1. 安装 Tampermonkey 浏览器插件
2. 打开 `tampermonkey/alive-broadcast-sync.user.js`
3. 修改 `SERVER_URL` 为你的服务器地址
4. 安装脚本
5. 保持浏览器打开 life.douyin.com

### 3. 后台配置
1. 访问 http://YOUR_IP:8000/admin/login
2. 默认账号: admin / admin123
3. 配置AI（API Key + 模型）
4. 配置邮箱（SMTP + 收件人）

## 技术栈
Python 3.11+ | FastAPI | SQLite | Jinja2 | TailwindCSS | Alpine.js | ECharts

## 定时任务
| 任务 | 时间 | 说明 |
|------|------|------|
| AI分析 | 每小时:05 | 自动分析未分析场次 |
| 日报生成 | 每天01:00 | 聚合前日数据 |
| 邮件推送 | 每天01:30 | 发送日报邮件 |
| 周报 | 每周一02:00 | 聚合上周数据 |
| 月报 | 每月1号03:00 | 聚合上月数据 |

## 目录结构
（引用 .docs/目录结构文档.md）
```

### 验收条件
- [ ] Windows: `start.bat` 双击启动成功
- [ ] Linux: `start.sh` 执行启动成功
- [ ] README包含完整安装步骤
- [ ] README包含配置说明
- [ ] README包含定时任务说明

---

## Task 9.3: 油猴脚本安装验证

### 任务描述
验证油猴脚本在真实浏览器环境中的安装和运行。

### 测试步骤

| 步骤 | 操作 | 验证点 |
|------|------|--------|
| 1 | Chrome安装Tampermonkey | 插件激活 |
| 2 | 导入 alive-broadcast-sync.user.js | 脚本列表出现 |
| 3 | 修改 SERVER_URL | 指向本地或服务器 |
| 4 | 打开 life.douyin.com | 控制台输出"脚本已加载" |
| 5 | 手动触发采集（如果有数据） | 数据成功POST到服务端 |
| 6 | 查看看板 | 新数据出现 |

### 配置说明文档内容

```
油猴脚本安装说明：
1. 浏览器安装 Tampermonkey 扩展
2. 点击 Tampermonkey 图标 → 添加新脚本
3. 粘贴 alive-broadcast-sync.user.js 全部内容
4. 修改第一行 SERVER_URL 为实际服务器地址
5. 保存 (Ctrl+S)
6. 确保浏览器24小时保持打开 life.douyin.com 页面
7. 脚本每天0点自动采集前一天数据
```

### 验收条件
- [ ] 脚本安装无报错
- [ ] 页面加载后脚本自动运行
- [ ] SERVER_URL 配置生效
- [ ] 控制台日志清晰

---

## Phase 9 整体验收清单

- [ ] 端到端链路1：采集→入库→展示 通过
- [ ] 端到端链路2：AI分析→报告→邮件 通过
- [ ] 端到端链路3：后台管理全功能 通过
- [ ] 端到端链路4：前台全功能 通过
- [ ] 端到端链路5：异常场景 通过
- [ ] 端到端链路6：定时任务验证 通过
- [ ] Windows启动脚本正常
- [ ] Linux启动脚本正常
- [ ] 数据库备份任务正常
- [ ] README完整清晰
- [ ] 油猴脚本安装验证通过
- [ ] 所有测试脚本已删除
- [ ] 无残留调试代码

---

## FAQ 常见问题

**Q1: 油猴脚本提示"不支持的数据版本"**
- 原因：脚本 `_version` 与服务端 `SUPPORTED_VERSIONS` 不匹配
- 解决：同步更新两端版本号，或检查脚本是否最新

**Q2: 定时任务未执行**
- 排查：确认APScheduler `BackgroundScheduler` 已启动
- 检查：系统时间、时区配置、任务日志输出

**Q3: 邮件发送失败**
- 检查：`settings.email_password` 是否正确（非脱敏值）
- 验证：SMTP服务器地址和端口是否可连通

**Q4: 数据库文件损坏**
- 恢复：从 `backups/` 目录找到最近一天的 `.db` 备份
- 预防：确认 `backup_job` 在定时任务中已配置

**Q5: 端口8000被占用**
- 查看：`netstat -ano | findstr ":8000"`
- 处理：终止占用进程，或修改 `main.py` 启动端口

---

## 项目总体交付清单

| 类别 | 交付物 | 数量 |
|------|--------|------|
| 后端代码 | server/ 下全部 .py 文件 | ~15个 |
| 前端模板 | templates/ 下全部 .html 文件 | ~14个 |
| 静态资源 | static/ 下 CSS + JS | 2个 |
| 油猴脚本 | tampermonkey/*.user.js | 1个 |
| 启动脚本 | start.bat + start.sh | 2个 |
| 项目文档 | README.md | 1个 |
| 设计文档 | .docs/ 下全部 | 6个 |
| 执行方案 | .docs/phases/ 下全部 | 9个 |
| 数据库 | data.db（运行时生成） | 1个 |
