# Milestone: Phase 10.2 — 残余缺陷修复与健壮性加固

## 目标
修复Phase 10.1修复后仍存在的6个残余问题，确保系统在真实生产环境中稳定运行，消除所有已知的功能失效风险。

## 验收标准
- [ ] 油猴脚本发送`_version:"1.0"`时服务端正确解析（非始终默认值）
- [ ] 默认提示词模板包含全部11个变量，新部署即可获得完整AI分析
- [ ] AI认证错误精确捕获，不依赖字符串匹配
- [ ] 邮件模板cost_threshold变量正确传入
- [ ] README包含data.db重置说明
- [ ] 油猴评论采集增加列头验证

## 周期
开始: 2026-05-23 | 结束: 2026-05-24

## 包含的Phase
- Phase-1: Pydantic字段解析修复（OPT-R1）
- Phase-2: 提示词模板与AI异常处理（OPT-R2, OPT-R3）
- Phase-3: 邮件模板变量传递确认（OPT-R5）
- Phase-4: 油猴脚本防御性增强（OPT-R4）
- Phase-5: 文档补充（OPT-R6）

---

## 方案对比

| 维度 | 方案A：逐个修复 | 方案B：按风险分批 | 方案C：按文件聚合 |
|------|----------------|-------------------|-------------------|
| 执行顺序 | R1→R2→R3→R4→R5→R6 | 高风险(R1)→中(R3,R5)→低(R2,R4,R6) | api.py→ai_service.py→database.py→user.js→docs |
| 优点 | 逻辑清晰 | 最高风险最先消除 | 减少文件切换，效率最高 |
| 缺点 | 无优先级区分 | 跨文件跳跃 | 可能遗漏依赖关系 |
| 用户视角 | 无感知差异 | 最快消除功能失效 | 无感知差异 |
| 管理者视角 | 可追踪每个OPT | 风险管控最优 | 代码review最方便 |
| 可用性评分 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |

**最终选择：方案B（按风险分批）**

理由：OPT-R1是唯一可能导致功能完全失效的问题（_version字段在Pydantic V2中不被解析），必须最先修复。其余按影响范围排序。

---

# Phase-1: Pydantic字段解析修复

## 关联Milestone
- Milestone: Phase 10.2 残余缺陷修复

## 功能描述
修复`_version`字段在Pydantic V2中因下划线前缀被视为私有属性而无法从请求JSON中解析的问题。

## 包含的Task

| 序号 | Task | 优先级 | 依赖 |
|------|------|--------|------|
| 1 | 服务端SessionData模型字段修复 | P0 | - |
| 2 | 油猴脚本payload字段名同步 | P0 | Task-1 |

## 资源
- 后端文件: `server/routers/api.py`
- 油猴脚本: `tampermonkey/alive-broadcast-sync.user.js`

---

### Task 1-1: 服务端SessionData模型字段修复

#### 任务描述
将SessionData中的`_version`字段改为Pydantic可正确解析的形式，确保客户端传入的版本号能被服务端读取。

#### 所属Phase
- Phase-1: Pydantic字段解析修复

#### 优先级
P0

---

#### 一、执行逻辑

##### 1. 触发
| 项目 | 内容 |
|------|------|
| 触发场景 | 油猴脚本POST /api/session时 |
| 触发来源 | HTTP请求JSON body中的version字段 |

##### 2. 路由
| 项目 | 内容 |
|------|------|
| 后端API | POST /api/session |

##### 3. 逻辑处理
| 项目 | 内容 |
|------|------|
| 处理目录 | server/routers/ |
| 处理文件 | api.py |
| 处理位置 | SessionData类定义（第29行）+ receive_session函数（第45行） |
| 核心变更 | `_version` → `version`；校验逻辑中 `data._version` → `data.version` |

##### 4. 问题根因分析

Pydantic V2（FastAPI 0.100+使用）中：
- 以`_`开头的字段被视为私有属性（`PrivateAttr`）
- 不会从`model_validate()`或请求JSON中解析
- 始终保持默认值`"1.0"`

两种修复方案：
- **方案A（推荐）**：字段名改为`version`（无下划线），JSON中也用`version`
- **方案B**：使用`Field(alias="_version")`保持JSON中用`_version`但内部用`version`

选择方案A，因为更简洁，且`_version`这个命名本身不规范。

##### 5. 数据库
无数据库变更。

##### 6. 响应
| 场景 | 响应 |
|------|------|
| version="1.0" | 正常处理 |
| version="2.0" | `{"code": 400, "message": "不支持的数据版本: 2.0，请更新油猴脚本"}` |
| 不传version | 默认"1.0"，正常处理 |

---

#### 二、文件操作

##### 修改

| 路径 | 修改点 |
|------|--------|
| `server/routers/api.py` 第29行 | `_version: str = "1.0"` → `version: str = "1.0"` |
| `server/routers/api.py` 第45-46行 | `data._version` → `data.version`（2处） |

---

#### 三、验收条件
- [ ] POST body中`{"version":"1.0",...}`时服务端正确读取为"1.0"
- [ ] POST body中`{"version":"2.0",...}`时返回400错误
- [ ] POST body中不含`version`字段时默认为"1.0"正常处理
- [ ] 不再使用下划线前缀字段名

---

### Task 1-2: 油猴脚本payload字段名同步

#### 任务描述
将油猴脚本发送的JSON中`_version`改为`version`，与服务端保持一致。

#### 所属Phase
- Phase-1: Pydantic字段解析修复

#### 优先级
P0

---

#### 一、执行逻辑

##### 1. 触发
| 项目 | 内容 |
|------|------|
| 触发场景 | collectCurrentSession()构造返回对象时 |
| 触发位置 | user.js 约第435行 |

##### 2. 逻辑处理
| 项目 | 内容 |
|------|------|
| 处理文件 | tampermonkey/alive-broadcast-sync.user.js |
| 处理位置 | collectCurrentSession()返回对象中 |
| 核心变更 | `_version: "1.0"` → `version: "1.0"` |

---

#### 二、文件操作

##### 修改

| 路径 | 修改点 |
|------|--------|
| `tampermonkey/alive-broadcast-sync.user.js` 约第435行 | `_version: "1.0"` → `version: "1.0"` |

---

#### 三、验收条件
- [ ] 油猴脚本发送的JSON中字段名为`version`（非`_version`）
- [ ] 服务端正确解析该字段
- [ ] 端到端：油猴发送→服务端校验→正常入库

---

# Phase-2: 提示词模板与AI异常处理

## 关联Milestone
- Milestone: Phase 10.2 残余缺陷修复

## 功能描述
修复默认提示词模板不完整和AI异常捕获不精确的问题。

## 包含的Task

| 序号 | Task | 优先级 | 依赖 |
|------|------|--------|------|
| 1 | 默认提示词模板补全11个变量 | P0 | - |
| 2 | AI异常捕获改为精确类型 | P1 | - |

## 资源
- 后端文件: `server/database.py`, `server/services/ai_service.py`

---

### Task 2-1: 默认提示词模板补全11个变量

#### 任务描述
将database.py中预置的`ai_user_prompt_template`默认值从只含1个变量扩展为包含全部11个变量的完整模板。

#### 所属Phase
- Phase-2: 提示词模板与AI异常处理

#### 优先级
P0

---

#### 一、执行逻辑

##### 1. 触发
| 项目 | 内容 |
|------|------|
| 触发场景 | init_db()首次初始化时写入settings表 |
| 影响范围 | 新部署的系统（已有data.db不受影响） |

##### 2. 逻辑处理
| 项目 | 内容 |
|------|------|
| 处理文件 | server/database.py |
| 处理位置 | init_db()中default_settings列表，`ai_user_prompt_template`项 |
| 核心变更 | 将默认值从单行改为包含11个{{变量}}的完整模板 |

##### 3. 完整默认模板内容

```
请分析以下直播数据：

## 基础信息
- 直播时间：{{start_time}} ~ {{end_time}}
- 直播时长：{{duration_minutes}}分钟
- 营销消耗：¥{{ad_spend}}

## 核心指标
{{metrics_text}}

## 线索列表（共{{leads_count}}条）
{{leads_text}}

## 评论明细（共{{comments_count}}条）
{{comments_text}}

## 高意向用户（共{{high_intent_count}}个）
{{high_intent_text}}

请给出完整分析报告，包含：1)整体评价(1-10分) 2)各维度分析 3)3-5条优化建议。
```

##### 4. 数据库
| 项目 | 内容 |
|------|------|
| 数据库 | SQLite |
| 数据表 | settings |
| 操作类型 | 仅影响新初始化（existing检查逻辑不覆盖已有值） |

---

#### 二、文件操作

##### 修改

| 路径 | 修改点 |
|------|--------|
| `server/database.py` 第38行 | `ai_user_prompt_template`的默认值从单行改为完整多行模板 |

---

#### 三、验收条件
- [ ] 新建data.db后，settings表中`ai_user_prompt_template`包含11个{{变量}}
- [ ] ai_service.py的模板替换逻辑能正确处理该模板
- [ ] 已有data.db不受影响（不覆盖用户已配置的值）

---

### Task 2-2: AI异常捕获改为精确类型

#### 任务描述
将ai_service.py中的字符串匹配异常判断改为精确的异常类型捕获。

#### 所属Phase
- Phase-2: 提示词模板与AI异常处理

#### 优先级
P1

---

#### 一、执行逻辑

##### 1. 逻辑处理
| 项目 | 内容 |
|------|------|
| 处理文件 | server/services/ai_service.py |
| 处理位置 | analyze_session()中API调用的try-except块（约第82-95行） |
| 核心变更 | 将通用`except Exception`拆分为精确异常类型 |

##### 2. 修改前（当前代码）

```python
except Exception as e:
    last_error = e
    if "AuthenticationError" in str(type(e).__name__) or "401" in str(e):
        raise Exception(f"AI API Key无效: {e}")
```

##### 3. 修改后

```python
import openai

try:
    response = client.chat.completions.create(...)
    break
except openai.AuthenticationError as e:
    raise Exception(f"AI API Key无效: {e}")  # 不重试
except (openai.APITimeoutError, openai.APIConnectionError, openai.RateLimitError) as e:
    last_error = e
    if attempt < max_retries - 1:
        time.sleep(5); continue
except openai.APIError as e:
    last_error = e
    if attempt < max_retries - 1:
        time.sleep(5); continue
```

##### 4. 关键点
- `AuthenticationError`：API Key无效，立即失败不重试
- `APITimeoutError`/`APIConnectionError`：网络问题，重试
- `RateLimitError`：频率限制，重试（间隔5秒通常够）
- `APIError`：其他API错误，重试

---

#### 二、文件操作

##### 修改

| 路径 | 修改点 |
|------|--------|
| `server/services/ai_service.py` 第1行 | 增加 `import openai` |
| `server/services/ai_service.py` 第82-95行 | 重构except块为多个精确异常类型 |

---

#### 三、验收条件
- [ ] API Key无效时立即报错"AI API Key无效"，不重试
- [ ] 网络超时时重试3次
- [ ] 频率限制时重试3次
- [ ] 不再使用字符串匹配判断异常类型

---

# Phase-3: 邮件模板变量传递确认

## 关联Milestone
- Milestone: Phase 10.2 残余缺陷修复

## 包含的Task

| 序号 | Task | 优先级 | 依赖 |
|------|------|--------|------|
| 1 | 确认email_service传入cost_threshold | P1 | - |

---

### Task 3-1: 确认并修复email_service传入cost_threshold

#### 任务描述
确认send_daily_report()在渲染daily_report.html时传入了`cost_threshold`变量，如未传入则补充。

#### 所属Phase
- Phase-3: 邮件模板变量传递确认

#### 优先级
P1

---

#### 一、执行逻辑

##### 1. 触发
| 项目 | 内容 |
|------|------|
| 触发场景 | email_job定时任务（每天01:30） |
| 触发位置 | email_service.py send_daily_report() → template.render() |

##### 2. 逻辑处理
| 项目 | 内容 |
|------|------|
| 处理文件 | server/services/email_service.py |
| 处理函数 | send_daily_report() |
| 检查位置 | template.render()调用处 |
| 核心变更 | 确保render参数中包含`cost_threshold=avg_cost*1.5` |

##### 3. 需要确认的逻辑

```python
# 计算动态阈值
avg_cost = total_spend / total_leads if total_leads > 0 else 200
cost_threshold = avg_cost * 1.5

# 渲染模板时传入
html = template.render(
    date=date,
    sessions=session_data_list,
    total_leads=total_leads,
    total_spend=total_spend,
    avg_lead_cost=avg_cost,
    cost_threshold=cost_threshold,  # ← 确认此参数存在
    session_count=len(sessions),
)
```

如果`template.render()`中缺少`cost_threshold`参数，Jinja2会在渲染`{% if s.lead_cost > cost_threshold %}`时抛出`UndefinedError`，导致邮件发送失败。

---

#### 二、文件操作

##### 修改（如需）

| 路径 | 修改点 |
|------|--------|
| `server/services/email_service.py` | send_daily_report()中template.render()增加`cost_threshold`参数（如缺失） |

---

#### 三、验收条件
- [ ] template.render()调用中包含`cost_threshold`参数
- [ ] 邮件发送不因UndefinedError失败
- [ ] 成本>阈值时邮件中数字确实为红色

---

# Phase-4: 油猴脚本防御性增强

## 关联Milestone
- Milestone: Phase 10.2 残余缺陷修复

## 包含的Task

| 序号 | Task | 优先级 | 依赖 |
|------|------|--------|------|
| 1 | 评论采集增加列头验证 | P2 | - |

---

### Task 4-1: 评论采集增加列头验证

#### 任务描述
在collectComments()开始采集前，先读取表头行确认列顺序，避免抖音来客调整列序后数据错位。

#### 所属Phase
- Phase-4: 油猴脚本防御性增强

#### 优先级
P2

---

#### 一、执行逻辑

##### 1. 触发
| 项目 | 内容 |
|------|------|
| 触发场景 | collectComments()执行时，Tab切换后 |
| 触发位置 | 评论列表容器加载完成后、开始遍历行之前 |

##### 2. 逻辑处理
| 项目 | 内容 |
|------|------|
| 处理文件 | tampermonkey/alive-broadcast-sync.user.js |
| 处理函数 | collectComments() |
| 插入位置 | 找到列表容器后、遍历数据行之前 |
| 核心变更 | 读取表头行文本，确定各列实际位置 |

##### 3. 列头验证逻辑

```javascript
// 读取表头行
const headerRow = container.querySelector('[class*="header"], tr:first-child');
const headers = [...headerRow.querySelectorAll('div, th')].map(el => el.textContent.trim());

// 确定列索引
const EXPECTED_HEADERS = ['昵称', '是否留资', '评论内容', '评论时间'];
const columnMap = {};
for (const expected of EXPECTED_HEADERS) {
    const idx = headers.findIndex(h => h.includes(expected));
    if (idx === -1) {
        log(`警告: 未找到"${expected}"列，评论采集可能不准确`, 'warn');
    }
    columnMap[expected] = idx;
}

// 使用columnMap[列名]而非硬编码索引提取数据
```

##### 4. 降级策略
如果找不到表头行（DOM结构变化），回退到当前的顺序索引方式，并输出警告日志。

---

#### 二、文件操作

##### 修改

| 路径 | 修改点 |
|------|--------|
| `tampermonkey/alive-broadcast-sync.user.js` | collectComments()中增加列头读取和columnMap构建逻辑 |

---

#### 三、验收条件
- [ ] 正常情况下通过列头文本确定列位置
- [ ] 列顺序变化时仍能正确提取（通过列名匹配）
- [ ] 找不到表头时降级为顺序索引+输出警告
- [ ] 不影响采集性能（列头验证只执行一次）

---

# Phase-5: 文档补充

## 关联Milestone
- Milestone: Phase 10.2 残余缺陷修复

## 包含的Task

| 序号 | Task | 优先级 | 依赖 |
|------|------|--------|------|
| 1 | README增加data.db重置说明 | P3 | - |

---

### Task 5-1: README增加data.db重置说明

#### 任务描述
在README的FAQ或配置章节中说明：已有data.db中的settings不会被环境变量覆盖，如需使用环境变量需重置数据库。

#### 所属Phase
- Phase-5: 文档补充

#### 优先级
P3

---

#### 一、执行逻辑

##### 1. 逻辑处理
| 项目 | 内容 |
|------|------|
| 处理文件 | README.md（根目录readme.md） |
| 插入位置 | FAQ章节或"后台配置"章节 |

##### 2. 增加内容

```markdown
**Q: 修改了.env环境变量但配置没生效？**
A: 环境变量仅在首次初始化data.db时写入settings表。如果data.db已存在，需要：
- 方案1：在后台管理页面手动修改对应配置
- 方案2：删除`server/data.db`后重启服务（会丢失所有数据）
- 方案3：用SQLite工具直接修改settings表中对应key的value
```

---

#### 二、文件操作

##### 修改

| 路径 | 修改点 |
|------|--------|
| `readme.md` | FAQ章节增加data.db重置说明 |

---

#### 三、验收条件
- [ ] README中有明确的data.db与环境变量关系说明
- [ ] 提供3种解决方案供用户选择

---

# 执行顺序总览

```
Phase-1（Pydantic修复）—— 最高优先级，功能失效风险
  Task 1-1: api.py _version → version
  Task 1-2: user.js _version → version
      │
Phase-2（提示词+异常）
  Task 2-1: database.py 默认模板补全
  Task 2-2: ai_service.py 精确异常捕获
      │
Phase-3（邮件变量）
  Task 3-1: email_service.py 确认cost_threshold传入
      │
Phase-4（油猴防御）
  Task 4-1: user.js 评论列头验证
      │
Phase-5（文档）
  Task 5-1: README data.db说明
```

---

# 整体验收标准

| # | 验收项 | 验证方式 |
|---|--------|----------|
| 1 | `version`字段正确解析 | POST `{"version":"1.0",...}` 正常入库；POST `{"version":"2.0",...}` 返回400 |
| 2 | 新data.db默认模板完整 | 删除data.db→重启→查看settings表ai_user_prompt_template含11个变量 |
| 3 | AI认证错误不重试 | 配置错误Key→触发分析→日志显示"AI API Key无效"无重试 |
| 4 | 邮件成本红色标注生效 | 触发邮件→检查收到的邮件中高成本场次数字为红色 |
| 5 | 评论列头验证 | 控制台输出列头匹配结果日志 |
| 6 | README含data.db说明 | 文档中可找到重置说明 |