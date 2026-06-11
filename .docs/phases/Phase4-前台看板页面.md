# Phase 4: 前台看板页面 — 三级原子化执行方案

## Milestone 上下文

| 项 | 内容 |
|---|------|
| 所属Milestone | AliveBroadcastData 抖音直播数据分析系统 |
| 业务目标 | 提供公开访问的数据看板，运营人员可查看直播数据、趋势、报告 |
| 在整体中的位置 | **第4个Phase**，依赖Phase 1（数据库），可与Phase 3并行 |
| 被依赖方 | Phase 9（端到端测试） |

## Phase 概要

| 项 | 内容 |
|---|------|
| 工期 | 3天 |
| 前置依赖 | Phase 1（数据库层+FastAPI入口）、Phase 2（部分API复用） |
| 产出文件 | 12个新建/修改文件 |
| 涉及模块 | 前端模板（Jinja2+TailwindCSS+Alpine.js+ECharts）、后端API |
| 页面数 | 5个前台页面 |

## 产出文件总览

| 文件路径 | 类型 | 用途 |
|----------|------|------|
| `server/templates/base.html` | 新建 | 前台基础布局（导航栏+CDN引入） |
| `server/templates/dashboard.html` | 新建 | 数据看板首页 |
| `server/templates/session_detail.html` | 新建 | 场次详情页 |
| `server/templates/reports.html` | 新建 | 报告中心 |
| `server/templates/trends.html` | 新建 | 趋势分析 |
| `server/templates/leads.html` | 新建 | 线索总览 |
| `server/static/css/custom.css` | 新建 | 自定义补充样式 |
| `server/static/js/app.js` | 新建 | 前端交互逻辑（Alpine.js组件） |
| `server/routers/pages.py` | 修改 | 前台页面路由（从占位→实现） |
| `server/routers/api.py` | 修改 | 新增前台查询API |

---

## Task 列表总览

| # | Task | 优先级 | 依赖 | 预估 |
|---|------|--------|------|------|
| 4.1 | 基础模板 base.html | P0 | Phase 1 | 2h |
| 4.2 | 数据看板首页 + Dashboard API | P0 | Task 4.1 | 4h |
| 4.3 | 场次详情页 + Detail API | P0 | Task 4.1 | 4h |
| 4.4 | 报告中心 + Reports API | P1 | Task 4.1 | 3h |
| 4.5 | 趋势分析 + Trends API | P1 | Task 4.1 | 3h |
| 4.6 | 线索总览 + Leads API | P1 | Task 4.1 | 3h |
| 4.7 | 导出功能（Excel） | P1 | Task 4.6 | 2h |
| 4.8 | 漏斗图 + 异常告警 + 环比 + 主播统计 | P1 | Task 4.2/4.3 | 3h |

---

## Task 4.1: 基础模板 base.html

### 任务描述
创建前台公共布局模板，引入TailwindCSS CDN、ECharts CDN、Alpine.js CDN，定义导航栏和内容区域。

### 执行逻辑

#### 1. 触发
| 项目 | 内容 |
|------|------|
| 触发页面 | 所有前台页面继承此模板 |
| 渲染方式 | Jinja2服务端渲染 |

#### 2. 路由
无独立路由，作为被继承的基础模板。

### 文件操作

**新建：**

| 路径 | 用途 |
|------|------|
| `server/templates/base.html` | 基础布局 |
| `server/static/css/custom.css` | 自定义样式 |
| `server/static/js/app.js` | 前端逻辑 |

### 伪代码

**`server/templates/base.html`：**
```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}抖音直播数据分析{% endblock %}</title>
    <!-- TailwindCSS CDN -->
    <script src="https://cdn.tailwindcss.com"></script>
    <!-- ECharts CDN -->
    <script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
    <!-- Alpine.js CDN -->
    <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3/dist/cdn.min.js"></script>
    <link rel="stylesheet" href="/static/css/custom.css">
</head>
<body class="bg-gray-50 min-h-screen">
    <!-- 导航栏 -->
    <nav class="bg-white shadow-sm border-b">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="flex justify-between h-16 items-center">
                <a href="/" class="text-xl font-bold text-gray-900">抖音直播数据分析</a>
                <div class="hidden md:flex space-x-8">
                    <a href="/" class="nav-link">看板</a>
                    <a href="/reports" class="nav-link">报告</a>
                    <a href="/trends" class="nav-link">趋势</a>
                    <a href="/leads" class="nav-link">线索</a>
                </div>
                <!-- 移动端菜单按钮 -->
                <div class="md:hidden">...</div>
            </div>
        </div>
    </nav>

    <!-- 内容区 -->
    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {% block content %}{% endblock %}
    </main>

    <script src="/static/js/app.js"></script>
    {% block scripts %}{% endblock %}
</body>
</html>
```

### 响应式断点设计（来自界面交互文档4.4）

| 断点 | 布局调整 |
|------|----------|
| ≥1024px (lg:) | 完整桌面布局 |
| 768-1023px (md:) | 看板卡片2列、导航保持 |
| <768px (sm:) | 单列布局、导航变为底部Tab、图表100%宽、表格横向滚动 |

### 验收条件
- [ ] CDN资源正常加载（TailwindCSS/ECharts/Alpine.js）
- [ ] 导航栏包含4个链接（看板/报告/趋势/线索）
- [ ] 响应式布局（手机/平板/桌面三断点）
- [ ] 子模板可通过 `{% extends "base.html" %}` 继承

---

## Task 4.2: 数据看板首页 + Dashboard API

### 任务描述
实现首页KPI卡片（含环比）、线索趋势折线图、最近场次列表、时间范围切换、异常告警条。

### 执行逻辑

#### 1. 触发
| 项目 | 内容 |
|------|------|
| 触发页面 | `server/templates/dashboard.html` |
| 触发事件 | 用户访问 `/` 或切换时间范围 |
| 交互框架 | Alpine.js x-data + fetch |

#### 2. 路由
| 项目 | 内容 |
|------|------|
| 页面路由 | GET `/` → `pages.py` → 返回 dashboard.html |
| 数据API | GET `/api/dashboard?range=week` → `api.py` |

#### 3. 逻辑处理 — Dashboard API

**`GET /api/dashboard` 参数：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| range | string | "week" | day/week/month |

**处理流程：**
```
1. 根据range计算当前周期和上一周期的日期范围
   - week: 近7天 vs 前7天
   - month: 近30天 vs 前30天
   - day: 今天 vs 昨天
2. 查询 sessions + session_metrics 聚合:
   - current: {leads, spend, lead_cost, sessions}
   - previous: 同结构
   - change: 计算各指标环比变化率
3. 查询趋势数据: 按日分组 (date, leads, spend)
4. 查询最近10个场次: (id, start_time, duration, leads, spend)
5. 异常检测:
   - 近7天平均线索成本
   - 最新场次成本 > 均值×1.5 → warning
   - 零留资 → warning
6. 漏斗数据:
   - 聚合 exposure → view → watch_gt_1min → interaction → leads
```

#### 4. 数据库
| 项目 | 内容 |
|------|------|
| 涉及表 | sessions, session_metrics, leads |
| 操作类型 | 聚合查询（SUM/AVG/COUNT/GROUP BY） |

#### 5. 响应
```json
{
  "code": 0,
  "data": {
    "current": {"leads": 48, "spend": 8520, "lead_cost": 177.5, "sessions": 12},
    "previous": {"leads": 36, "spend": 9000, "lead_cost": 250, "sessions": 9},
    "change": {"leads": "+33.3%", "spend": "-5.3%", "lead_cost": "-29%", "sessions": "+33.3%"},
    "trend": [{"date": "2026-05-20", "leads": 6, "spend": 980}],
    "recent_sessions": [{"id": 1, "start_time": "...", "duration": 248, "leads": 4, "spend": 1062}],
    "alerts": [{"type": "warning", "message": "05-21场次线索成本¥265，高于近7天均值50%"}],
    "funnel": {"exposure": 34180, "view": 1258, "watch_gt_1min": 46, "interaction": 24, "leads": 4}
  }
}
```

### 文件操作

**新建：**
| 路径 | 用途 |
|------|------|
| `server/templates/dashboard.html` | 看板首页模板 |

**修改：**
| 路径 | 修改点 |
|------|--------|
| `server/routers/api.py` | 新增 GET /api/dashboard |
| `server/routers/pages.py` | 新增 GET / 页面路由 |

### 前端交互伪代码

```html
<!-- dashboard.html -->
{% extends "base.html" %}
{% block content %}
<div x-data="dashboardApp()" x-init="loadData()">
    <!-- 异常告警条 -->
    <template x-if="alerts.length > 0">
        <div class="bg-yellow-50 border-l-4 border-yellow-400 p-4 mb-4">
            <template x-for="alert in alerts">
                <p x-text="alert.message" class="text-yellow-700"></p>
            </template>
        </div>
    </template>

    <!-- 时间范围切换 -->
    <div class="flex justify-end mb-4 space-x-2">
        <button @click="range='day'; loadData()" :class="range==='day'?'active':''">日</button>
        <button @click="range='week'; loadData()" :class="range==='week'?'active':''">周</button>
        <button @click="range='month'; loadData()" :class="range==='month'?'active':''">月</button>
    </div>

    <!-- KPI卡片 4列（含环比） -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <template x-for="kpi in kpiCards">
            <div class="bg-white rounded-lg shadow p-4">
                <p class="text-sm text-gray-500" x-text="kpi.label"></p>
                <p class="text-2xl font-bold" x-text="kpi.value"></p>
                <p :class="kpi.changeColor" x-text="kpi.change"></p>
            </div>
        </template>
    </div>

    <!-- 趋势折线图 -->
    <div class="bg-white rounded-lg shadow p-4 mb-6">
        <div id="trendChart" style="height:300px;"></div>
    </div>

    <!-- 最近场次列表 -->
    <div class="bg-white rounded-lg shadow overflow-x-auto">
        <table class="min-w-full">
            <thead><tr>
                <th>日期</th><th>时段</th><th>时长</th><th>线索</th><th>消耗</th>
            </tr></thead>
            <tbody>
                <template x-for="s in recentSessions">
                    <tr @click="location.href='/session/'+s.id" class="cursor-pointer hover:bg-gray-50">
                        <td x-text="s.date"></td>
                        <td x-text="s.time_range"></td>
                        <td x-text="s.duration_text"></td>
                        <td x-text="s.leads"></td>
                        <td x-text="'¥'+s.spend"></td>
                    </tr>
                </template>
            </tbody>
        </table>
    </div>
</div>
{% endblock %}

{% block scripts %}
<script>
function dashboardApp() {
    return {
        range: 'week',
        kpiCards: [],
        alerts: [],
        recentSessions: [],
        async loadData() {
            const resp = await fetch(`/api/dashboard?range=${this.range}`);
            const json = await resp.json();
            const d = json.data;
            this.alerts = d.alerts;
            this.kpiCards = [
                {label:'总场次', value:d.current.sessions, change:d.change.sessions, changeColor:...},
                {label:'总线索', value:d.current.leads, change:d.change.leads, changeColor:...},
                {label:'总消耗', value:'¥'+d.current.spend, change:d.change.spend, changeColor:...},
                {label:'线索成本', value:'¥'+d.current.lead_cost, change:d.change.lead_cost, changeColor:...},
            ];
            this.recentSessions = d.recent_sessions;
            this.renderTrendChart(d.trend);
        },
        renderTrendChart(data) {
            const chart = echarts.init(document.getElementById('trendChart'));
            chart.setOption({
                xAxis: { type: 'category', data: data.map(d => d.date) },
                yAxis: [{ type: 'value', name: '线索数' }, { type: 'value', name: '消耗' }],
                series: [
                    { name: '线索', type: 'line', data: data.map(d => d.leads) },
                    { name: '消耗', type: 'line', yAxisIndex: 1, data: data.map(d => d.spend) },
                ],
                tooltip: { trigger: 'axis' },
                legend: {}
            });
        }
    };
}
</script>
{% endblock %}
```

### 验收条件
- [ ] 访问 `/` 显示完整看板页面
- [ ] 4个KPI卡片正确显示数值+环比变化
- [ ] 环比变化率计算正确（正数绿色↑，负数红色↓）
- [ ] 趋势折线图正确渲染（双Y轴：线索+消耗）
- [ ] 最近场次列表可点击进入详情
- [ ] 时间范围切换（日/周/月）刷新数据
- [ ] 异常告警条显示（线索成本偏高等）
- [ ] 移动端响应式（卡片2列→1列）

---

## Task 4.3: 场次详情页 + Detail API

### 任务描述
实现场次详情页，包含基础信息卡片+8个Tab（流量/互动/转化/线索/评论/高意向/漏斗/AI分析）。

### 执行逻辑

#### 1. 路由
| 项目 | 内容 |
|------|------|
| 页面路由 | GET `/session/{id}` → pages.py |
| 数据API | GET `/api/sessions/{id}` → api.py |

#### 2. API响应结构
```json
{
  "code": 0,
  "data": {
    "session": {"id":1, "start_time":"...", "end_time":"...", "duration_minutes":248},
    "metrics": {全部44字段},
    "leads": [{lead_time, nickname, ...}],
    "comments": [{nickname, has_lead, content, comment_time}],
    "high_intent_users": [{nickname, avatar_url, comment_count, stay_duration, status}],
    "report": {"content": "AI分析Markdown内容", "generated_at": "..."},
    "anchors": [{"id":1, "name":"张三"}],
    "funnel": {"exposure":34180, "view":1258, "watch_gt_1min":46, "interaction":24, "leads":4}
  }
}
```

#### 3. Tab切换（Alpine.js）
```
activeTab: 'traffic'
tabs: ['traffic','interaction','conversion','leads','comments','high_intent','funnel','ai_report']
每个Tab对应不同数据展示区域
```

### 文件操作

**新建：**
| 路径 | 用途 |
|------|------|
| `server/templates/session_detail.html` | 场次详情模板 |

**修改：**
| 路径 | 修改点 |
|------|--------|
| `server/routers/api.py` | 新增 GET /api/sessions/{id} |
| `server/routers/api.py` | 新增 GET /api/sessions（列表分页） |
| `server/routers/pages.py` | 新增 GET /session/{id} 页面路由 |

### 验收条件
- [ ] 8个Tab全部可切换
- [ ] 流量/互动/转化Tab展示指标表格
- [ ] 线索Tab展示线索明细列表
- [ ] 评论Tab展示评论列表（标记已留资）
- [ ] 高意向Tab展示用户卡片（含头像）
- [ ] 漏斗Tab展示ECharts漏斗图
- [ ] AI分析Tab展示Markdown报告（rendered HTML）
- [ ] 基础信息卡片显示时长/消耗/线索数/成本
- [ ] 关联主播名称显示

---

## Task 4.4: 报告中心 + Reports API

### 任务描述
实现报告列表页，支持按类型/日期/主播筛选，预览弹窗，下载。

### 执行逻辑

#### 1. 路由
| 项目 | 内容 |
|------|------|
| 页面路由 | GET `/reports` → pages.py |
| 列表API | GET `/api/reports?type=&page=&size=` |
| 下载API | GET `/api/reports/{id}/download` |

#### 2. API — GET /api/reports
```python
@router.get("/reports")
def list_reports(
    type: Optional[str] = None,  # session/daily/weekly/monthly
    page: int = 1,
    size: int = 20,
    db: DBSession = Depends(get_db)
):
    query = db.query(Report)
    if type:
        query = query.filter(Report.report_type == type)
    total = query.count()
    items = query.order_by(Report.generated_at.desc()).offset((page-1)*size).limit(size).all()
    return {"code":0, "data":{"items":[...], "total":total, "page":page, "size":size}}
```

#### 3. 下载 — GET /api/reports/{id}/download
```python
from fastapi.responses import StreamingResponse

@router.get("/reports/{id}/download")
def download_report(id: int, db: DBSession = Depends(get_db)):
    report = db.query(Report).get(id)
    if not report:
        raise HTTPException(404)
    content = report.content.encode('utf-8')
    filename = f"{report.report_type}_{report.period}.md"
    return StreamingResponse(
        io.BytesIO(content),
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
```

### 文件操作

**新建：**
| 路径 | 用途 |
|------|------|
| `server/templates/reports.html` | 报告中心模板 |

**修改：**
| 路径 | 修改点 |
|------|--------|
| `server/routers/api.py` | 新增 GET /api/reports 和 /api/reports/{id}/download |
| `server/routers/pages.py` | 新增 GET /reports 页面路由 |

### 验收条件
- [ ] 筛选栏正常工作（类型/日期/主播）
- [ ] 报告列表分页正确
- [ ] 预览弹窗正确渲染Markdown内容
- [ ] 下载返回 .md 文件

---

## Task 4.5: 趋势分析 + Trends API

### 任务描述
实现趋势分析页，多指标折线图+主播对比柱状图+时段热力图。

### 执行逻辑

#### 1. 路由
| 项目 | 内容 |
|------|------|
| 页面路由 | GET `/trends` → pages.py |
| 数据API | GET `/api/trends?date_from=&date_to=&anchor_id=&metric=&group_by=` |
| 主播统计 | GET `/api/anchors/stats?date_from=&date_to=` |

#### 2. API — GET /api/trends
**参数：**
| 参数 | 说明 |
|------|------|
| date_from/date_to | 日期范围 |
| anchor_id | 按主播筛选（可选） |
| metric | 指标选择（leads/spend/lead_cost/views/interaction_rate） |
| group_by | 分组方式（date/hour/weekday） |

**响应（group_by=date）：**
```json
{"code":0, "data":[{"date":"2026-05-20","leads":6,"spend":980,"lead_cost":163}]}
```

**响应（group_by=hour，用于热力图）：**
```json
{"code":0, "data":[{"weekday":1,"hour":9,"avg_leads":3.5}]}
```

#### 3. 时段热力图（界面交互文档4.2）
- X轴：星期一~日
- Y轴：0~23时
- 颜色深度：场均线索数
- ECharts heatmap组件

### 文件操作

**新建：**
| 路径 | 用途 |
|------|------|
| `server/templates/trends.html` | 趋势分析模板 |

**修改：**
| 路径 | 修改点 |
|------|--------|
| `server/routers/api.py` | 新增 GET /api/trends、GET /api/anchors/stats |
| `server/routers/pages.py` | 新增 GET /trends 页面路由 |

### 验收条件
- [ ] 多指标趋势折线图正确渲染
- [ ] 主播对比柱状图正确
- [ ] 时段热力图（按小时×星期）正确渲染
- [ ] 筛选栏联动（时间范围/主播/指标）
- [ ] 导出Excel按钮（调用Task 4.7）

---

## Task 4.6: 线索总览 + Leads API

### 任务描述
实现线索总览页，含筛选、列表、分页、饼图。

### 执行逻辑

#### 1. 路由
| 项目 | 内容 |
|------|------|
| 页面路由 | GET `/leads` → pages.py |
| 数据API | GET `/api/leads?keyword=&city=&date_from=&date_to=&is_deal=&is_valid=&page=&size=` |

#### 2. 线索质量分布图（界面交互文档4.1）
- **饼图1**：线索来源分布（付费 vs 自然）
  - 规则：ad_account不为空且不为"--" → 付费，否则自然
- **饼图2**：城市TOP10
- 点击饼图扇区联动筛选下方列表

#### 3. API — GET /api/leads
```python
@router.get("/leads")
def list_leads(
    keyword: Optional[str] = None,
    city: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    is_deal: Optional[bool] = None,
    is_valid: Optional[bool] = None,
    page: int = 1,
    size: int = 20,
    db: DBSession = Depends(get_db)
):
    query = db.query(Lead).join(Session)
    if keyword:
        query = query.filter(Lead.nickname.contains(keyword))
    if city:
        query = query.filter(Lead.city == city)
    if date_from:
        query = query.filter(Session.start_time >= date_from)
    if date_to:
        query = query.filter(Session.start_time <= date_to + " 23:59:59")
    if is_deal is not None:
        query = query.filter(Lead.is_deal == is_deal)
    if is_valid is not None:
        query = query.filter(Lead.is_valid == is_valid)
    
    total = query.count()
    items = query.order_by(Lead.created_at.desc()).offset((page-1)*size).limit(size).all()
    
    # 饼图统计
    all_leads = db.query(Lead).join(Session)  # 同筛选条件
    paid = all_leads.filter(Lead.ad_account != None, Lead.ad_account != '--').count()
    organic = total - paid
    city_stats = db.query(Lead.city, func.count()).group_by(Lead.city).order_by(func.count().desc()).limit(10).all()
    
    return {"code":0, "data":{
        "items":[...], "total":total, "page":page, "size":size,
        "charts": {
            "source": {"paid": paid, "organic": organic},
            "city_top10": [{"city":"重庆","count":25}]
        }
    }}
```

### 文件操作

**新建：**
| 路径 | 用途 |
|------|------|
| `server/templates/leads.html` | 线索总览模板 |

**修改：**
| 路径 | 修改点 |
|------|--------|
| `server/routers/api.py` | 新增 GET /api/leads |
| `server/routers/pages.py` | 新增 GET /leads 页面路由 |

### 验收条件
- [ ] 筛选栏全部功能正常（关键词/城市/日期/成单/有效性）
- [ ] 列表分页正确
- [ ] 付费/自然饼图数据正确（ad_account判断规则）
- [ ] 城市TOP10饼图正确
- [ ] 点击饼图扇区联动筛选列表

---

## Task 4.7: 导出功能（Excel）

### 任务描述
实现场次导出和线索导出的Excel功能。

### 执行逻辑

#### 1. 路由
| 项目 | 内容 |
|------|------|
| API | GET `/api/export/sessions?date_from=&date_to=&format=xlsx` |
| API | GET `/api/export/leads?date_from=&date_to=&format=xlsx` |

#### 2. 伪代码
```python
from openpyxl import Workbook
from fastapi.responses import StreamingResponse
import io

@router.get("/export/sessions")
def export_sessions(date_from: str = None, date_to: str = None, db: DBSession = Depends(get_db)):
    # 查询场次+指标
    sessions = db.query(Session, SessionMetric).join(SessionMetric)...
    
    wb = Workbook()
    ws = wb.active
    ws.title = "场次数据"
    # 写入表头
    ws.append(["开播时间","结束时间","时长(分)","线索数","消耗","线索成本",...])
    # 写入数据行
    for s, m in sessions:
        ws.append([s.start_time, s.end_time, s.duration_minutes, m.total_leads, m.ad_spend, ...])
    
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=sessions.xlsx"})
```

### 验收条件
- [ ] 场次Excel包含核心指标列
- [ ] 线索Excel包含全部9字段
- [ ] 日期范围筛选正确
- [ ] 文件下载正常（浏览器触发下载）

---

## Task 4.8: 漏斗图 + 异常告警 + 环比 + 主播统计

### 任务描述
补充Dashboard环比展示、异常告警条、场次详情漏斗Tab、主播聚合统计API。

### 执行逻辑

#### 1. 漏斗图（ECharts funnel）
```javascript
// 场次详情页漏斗Tab
option = {
    series: [{
        type: 'funnel',
        label: {
            formatter: function(p) {
                const prev = p.dataIndex === 0 ? p.value : p.seriesName[p.dataIndex - 1].value;
                const rate = prev > 0 ? ((p.value / prev) * 100).toFixed(1) + '%' : '-';
                return p.name + '\n' + p.value + ' (' + rate + ')';
            }
        },
        data: [
            {value: funnel.exposure, name: '曝光'},
            {value: funnel.view, name: '观看'},
            {value: funnel.watch_gt_1min, name: '>1分钟'},
            {value: funnel.interaction, name: '互动'},
            {value: funnel.leads, name: '留资'},
        ]
    }]
};
```

#### 2. 异常检测逻辑
```python
def detect_alerts(db, date_range):
    alerts = []
    # 近7天平均线索成本
    avg_cost = db.query(func.avg(SessionMetric.ad_spend / SessionMetric.total_leads))...
    # 最新场次成本
    latest = db.query(SessionMetric).order_by(SessionMetric.id.desc()).first()
    if latest and latest.total_leads > 0:
        cost = latest.ad_spend / latest.total_leads
        if cost > avg_cost * 1.5:
            alerts.append({"type":"warning","message":f"线索成本¥{cost:.0f}，高于均值50%"})
    # 零留资
    if latest and latest.total_leads == 0:
        alerts.append({"type":"warning","message":"最新场次零留资"})
    return alerts
```

#### 3. 主播聚合统计 — GET /api/anchors/stats
```python
@router.get("/anchors/stats")
def anchor_stats(date_from: str = None, date_to: str = None, db: DBSession = Depends(get_db)):
    # JOIN session_anchors + sessions + session_metrics
    # GROUP BY anchor_id
    # 计算: session_count, avg_leads, avg_spend, avg_lead_cost, total_leads, total_spend
    return {"code":0, "data":[{...}]}
```

### 验收条件
- [ ] 漏斗图5层正确（曝光→观看→深度→互动→留资）
- [ ] KPI环比变化显示正确（↑↓符号+百分比+颜色）
- [ ] 异常告警条在顶部显示
- [ ] 主播统计返回正确聚合数据

---

## Phase 4 整体验收清单

- [ ] 5个前台页面全部可访问（看板/场次详情/报告/趋势/线索）
- [ ] TailwindCSS+ECharts+Alpine.js CDN正常加载
- [ ] 响应式布局（桌面/平板/手机三断点）
- [ ] Dashboard KPI+环比+趋势+场次列表+告警全部正常
- [ ] 场次详情8个Tab全部可用
- [ ] 报告中心筛选+预览+下载正常
- [ ] 趋势分析折线图+柱状图+热力图正常
- [ ] 线索总览筛选+列表+饼图+联动正常
- [ ] Excel导出（场次+线索）正常
- [ ] 漏斗图渲染正确
- [ ] 主播统计API数据正确
