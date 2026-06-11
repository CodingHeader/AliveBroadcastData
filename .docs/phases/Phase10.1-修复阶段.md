# Milestone: AliveBroadcastData 系统优化 — 核心价值提升

## 目标
修复AI分析数据不足、油猴采集不完整、邮件/报告功能缺失等问题，使系统从"能跑通"提升到"真正产生业务价值"。

## 验收标准
- [ ] AI分析报告包含线索/评论/高意向用户数据，输出有具体建议
- [ ] 油猴脚本44字段完整率100%，评论/高意向数据精确
- [ ] 邮件包含AI摘要和异常红色标注
- [ ] 周报包含AI周度分析章节
- [ ] 后台邮件测试按钮真正发送邮件
- [ ] 趋势分析支持时段热力图

## 周期
开始: 2026-05-23 | 结束: 2026-05-28

## 包含的Phase
- Phase-1: AI分析服务完善（F-1, F-14）
- Phase-2: 油猴脚本数据完整性（F-2, F-3, F-8, F-9, F-13）
- Phase-3: 邮件与报告增强（F-4, F-5, F-6）
- Phase-4: 前台功能补全（F-7, F-11, F-12）
- Phase-5: 后台功能补全（F-10, F-15）
- Phase-6: 部署与文档收尾（F-16~F-20）

---

## 方案对比

| 维度 | 方案A：按优先级串行 | 方案B：按模块并行 | 方案C：按数据流端到端 |
|------|-------------------|-------------------|---------------------|
| 执行顺序 | P0全部→P1全部→P2全部 | 油猴/服务端/前端三线并行 | 油猴采集→API接收→AI分析→报告→邮件→展示 |
| 优点 | 最高价值问题最先解决 | 总工期最短 | 每完成一段就能端到端验证 |
| 缺点 | 跨模块跳跃，上下文切换多 | 需要提前定义接口契约 | 前期只能验证部分功能 |
| 用户视角 | 最快看到AI分析质量提升 | 同时看到多处改善 | 逐步看到完整链路打通 |
| 管理者视角 | 风险最低，每步可验证 | 并行风险高，集成可能出问题 | 可渐进式交付 |
| 可用性评分 | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |

**最终选择：方案C（按数据流端到端）**

理由：本系统的核心价值链是 `采集→存储→分析→报告→推送→展示`。按数据流顺序修复，每完成一个环节都能立即验证上下游是否正确衔接，避免"修了AI但油猴数据不全导致AI仍然无用"的问题。

---

# Phase-1: AI分析服务完善

## 关联Milestone
- Milestone: AliveBroadcastData 系统优化

## 功能描述
使AI分析从"只看5个指标"提升为"看全量数据（44指标+线索+评论+高意向）"，输出真正有价值的分析报告。

## 包含的Task

| 序号 | Task | 优先级 | 依赖 |
|------|------|--------|------|
| 1 | FIELD_LABELS补全44字段中文映射 | P0 | - |
| 2 | 构建全量提示词（metrics+leads+comments+hiu） | P0 | Task-1 |
| 3 | 使用settings中的用户提示词模板 | P0 | Task-2 |
| 4 | AI调用增加重试机制 | P1 | Task-3 |

## 资源
- 后端文件: `server/services/ai_service.py`
- 数据库: settings表（读取提示词配置）、sessions/metrics/leads/comments/high_intent_users表（读取数据）
- 外部依赖: OpenAI兼容API

---

### Task 1-1: FIELD_LABELS补全44字段中文映射

#### 任务描述
将ai_service.py中的FIELD_LABELS从5个扩展到44个，覆盖session_metrics表全部字段。

#### 所属Phase
- Phase-1: AI分析服务完善

#### 优先级
P0

---

#### 一、执行逻辑

##### 1. 触发
| 项目 | 内容 |
|------|------|
| 触发场景 | analyze_session()被调用时 |
| 触发来源 | scheduler定时任务 / 后台手动触发 |

##### 2. 路由
无新增路由，内部服务函数。

##### 3. 逻辑处理
| 项目 | 内容 |
|------|------|
| 处理目录 | server/services/ |
| 处理文件 | ai_service.py |
| 处理位置 | FIELD_LABELS字典定义处（当前第19行） |
| 处理逻辑 | 将字典从5项扩展为44项，key为模型字段名，value为中文标签 |

##### 4. 数据映射来源
参照 `功能设计文档.md` 第三章 3.2节 session_metrics 表定义，以及 `.data/20260521_1336/复盘表-时间指标单位为秒.csv` 中的中文标签。

映射规则：
```
exposure_count → 曝光人数
cumulative_viewers → 累计观看人数
exposure_entry_rate → 曝光进入率
gmv → 直播间成交金额
order_count → 订单人数
marketing_orders → 营销订单数
phone_submits → 填手机号
ad_spend → 营销消耗(元)
total_leads → 全场景留资人数
order_cost → 订单成本
lead_cost → 线索成本
new_followers → 涨粉量
comment_count → 评论次数
comment_users → 评论人数
watch_gt_1min → >1分钟观看次数
avg_watch_duration → 人均观看时长
fan_stay_duration → 粉丝停留时长
max_online → 最高在线人数
interaction_count → 互动次数
interaction_users → 互动人数
interaction_rate → 互动率
fan_club_joins → 加粉丝团人数
fan_club_rate → 加团率
component_clicks → 风车房子点击次数
click_rate → 点击率
gift_amount → 打赏金额
gift_count → 打赏次数
comment_rate → 评论率
lead_conversion_rate → 线索转化率
like_rate → 点赞率
like_users → 点赞人数
like_count → 点赞次数
product_exposure → 商品曝光次数
product_clicks → 商品点击次数
product_click_rate → 商品点击率
follow_rate → 关注率
share_count → 分享次数
share_users → 分享人数
gmv_per_mille → 千次观看GMV
fan_ratio → 粉丝占比
exposure_times → 曝光次数
view_count → 直播间观看次数
avg_online → 平均在线人数
realtime_online → 实时在线人数
```

##### 5. 数据库
无数据库操作（纯代码映射）。

##### 6. 响应
无直接响应，影响AI提示词中的指标可读性。

---

#### 二、文件操作

##### 修改

| 路径 | 修改点 |
|------|--------|
| `server/services/ai_service.py` | 将第19行 `FIELD_LABELS = {...5项...}` 扩展为44项完整映射字典 |

---

#### 三、验收条件
- [ ] FIELD_LABELS包含44个key-value对
- [ ] key与models.py中SessionMetric的列名完全一致
- [ ] value为用户可理解的中文标签
- [ ] AI提示词中指标显示为"- 曝光人数: 34180"而非"- exposure_count: 34180"

---

### Task 1-2: 构建全量提示词（metrics+leads+comments+hiu）

#### 任务描述
重构analyze_session()，使AI提示词包含完整的场次数据：44个指标 + 前15条线索摘要 + 前30条评论 + 全部高意向用户。

#### 所属Phase
- Phase-1: AI分析服务完善

#### 优先级
P0

---

#### 一、执行逻辑

##### 1. 触发
| 项目 | 内容 |
|------|------|
| 触发场景 | analyze_session(db, session_id)被调用 |
| 触发来源 | scheduler / admin API |

##### 2. 逻辑处理
| 项目 | 内容 |
|------|------|
| 处理文件 | server/services/ai_service.py |
| 处理函数 | analyze_session() — 重构数据构建部分 |
| 核心变更 | 在构建user_prompt时，追加leads_text、comments_text、high_intent_text |

##### 3. 数据构建逻辑

```
1. 查询 session（基础信息：时间/时长）
2. 查询 session_metrics（44字段，用FIELD_LABELS转中文）
3. 查询 leads（该场所有线索，取前15条）
   → 格式："- {昵称} | {城市} | {留资路径} | {特征标签} | 来源:{ad_account或'自然'}"
4. 查询 comments（该场所有评论，取前30条）
   → 格式："- {昵称}{'[已留资]' if has_lead}: {内容} ({时间})"
5. 查询 high_intent_users（该场全部）
   → 格式："- {昵称} | 评论{N}次 | 停留{时长} | {状态}"
6. 拼接为完整user_prompt
```

##### 4. 数据库
| 项目 | 内容 |
|------|------|
| 数据库 | SQLite (data.db) |
| 涉及表 | sessions, session_metrics, leads, comments, high_intent_users |
| 操作类型 | 查询（5张表） |

##### 5. 提示词结构（最终发送给AI的user message）

```
请分析以下直播数据：

## 基础信息
- 直播时间：{start_time} ~ {end_time}
- 直播时长：{duration_minutes}分钟
- 营销消耗：¥{ad_spend}

## 核心指标（44项）
- 曝光人数: 34180
- 累计观看人数: 1258
- ...（全部44项，跳过None值）

## 线索列表（共{N}条，展示前15条）
- 四月雪 | 重庆 | 进房->商品详情页 | 短停留 | 来源:ID:1853819759992010
- ...

## 评论明细（共{N}条，展示前30条）
- 知远[已留资]: 初中学历考大专需要多久 (11:39)
- 辐射橙: 我们有哪些学校选择？ (11:14)
- ...

## 高意向用户（共{N}个）
- 光伏打孔 | 评论5次 | 停留20.7分钟 | 未留资
- ...

请给出完整分析报告。
```

---

#### 二、文件操作

##### 修改

| 路径 | 修改点 |
|------|--------|
| `server/services/ai_service.py` | 重构analyze_session()中prompt构建部分：增加leads/comments/hiu查询和文本构建 |

---

#### 三、验收条件
- [ ] AI收到的prompt包含基础信息+44指标+线索+评论+高意向5个章节
- [ ] 线索展示前15条（超过15条时标注"展示前15条"）
- [ ] 评论展示前30条
- [ ] None值字段不出现在prompt中
- [ ] AI返回的报告中能提及具体线索城市、评论内容等细节

---

### Task 1-3: 使用settings中的用户提示词模板

#### 任务描述
从settings表读取ai_user_prompt_template，用`.replace()`渲染变量，而非硬编码prompt。

#### 所属Phase
- Phase-1: AI分析服务完善

#### 优先级
P0

---

#### 一、执行逻辑

##### 1. 逻辑处理
| 项目 | 内容 |
|------|------|
| 处理文件 | server/services/ai_service.py |
| 处理函数 | analyze_session() |
| 核心变更 | 读取config["ai_user_prompt_template"]，用.replace()替换{{变量}} |

##### 2. 变量替换映射

| 模板变量 | 替换值来源 |
|----------|-----------|
| `{{start_time}}` | session.start_time |
| `{{end_time}}` | session.end_time |
| `{{duration_minutes}}` | str(session.duration_minutes) |
| `{{ad_spend}}` | str(metrics.ad_spend) |
| `{{metrics_text}}` | Task 1-2构建的指标文本 |
| `{{leads_count}}` | str(len(leads)) |
| `{{leads_text}}` | Task 1-2构建的线索文本 |
| `{{comments_count}}` | str(len(comments)) |
| `{{comments_text}}` | Task 1-2构建的评论文本 |
| `{{high_intent_count}}` | str(len(hiu)) |
| `{{high_intent_text}}` | Task 1-2构建的高意向文本 |

##### 3. 回退逻辑
如果settings中`ai_user_prompt_template`为空或不含任何`{{}}`变量，则使用Task 1-2中的硬编码格式作为默认值。

---

#### 二、文件操作

##### 修改

| 路径 | 修改点 |
|------|--------|
| `server/services/ai_service.py` | analyze_session()中：读取template → replace变量 → 作为user message |

---

#### 三、验收条件
- [ ] 后台修改用户提示词模板后，AI分析使用新模板
- [ ] 模板为空时使用默认格式（不报错）
- [ ] 所有{{变量}}正确替换为实际数据

---

### Task 1-4: AI调用增加重试机制

#### 任务描述
analyze_session()中OpenAI API调用增加3次重试，间隔5秒，全部失败后抛出明确异常。

#### 所属Phase
- Phase-1: AI分析服务完善

#### 优先级
P1

---

#### 一、执行逻辑

##### 1. 逻辑处理
| 项目 | 内容 |
|------|------|
| 处理文件 | server/services/ai_service.py |
| 处理函数 | analyze_session() — API调用部分 |
| 核心变更 | 将`client.chat.completions.create()`包裹在`for attempt in range(3)`循环中 |

##### 2. 重试逻辑

```
for attempt in range(3):
    try:
        response = client.chat.completions.create(...)
        break  # 成功则跳出
    except (openai.APITimeoutError, openai.APIConnectionError, openai.RateLimitError) as e:
        if attempt < 2:
            time.sleep(5)
            continue
        else:
            raise Exception(f"AI API调用3次均失败: {e}")
    except openai.AuthenticationError as e:
        raise Exception(f"AI API Key无效: {e}")  # 认证错误不重试
```

##### 3. scheduler中的失败处理
在`scheduler.py`的`analyze_job`中，当`analyze_session`抛出异常时，记录该session_id到一个失败计数（可用session.analyzed_at字段标记"FAILED"），超过3次不再重试该场次。

---

#### 二、文件操作

##### 修改

| 路径 | 修改点 |
|------|--------|
| `server/services/ai_service.py` | API调用处增加for循环+异常捕获+sleep重试 |
| `server/services/scheduler.py` | analyze_job中增加失败计数逻辑（检查analyzed_at是否为"FAILED_N"） |

---

#### 三、验收条件
- [ ] 网络超时时自动重试（最多3次）
- [ ] 认证错误（Key无效）不重试，直接报错
- [ ] 同一场次失败3次后不再重试
- [ ] 日志记录每次重试和最终结果

---

# Phase-2: 油猴脚本数据完整性

## 关联Milestone
- Milestone: AliveBroadcastData 系统优化

## 功能描述
确保油猴脚本采集的数据完整、准确，44字段无遗漏，评论/高意向数据精确提取。

## 包含的Task

| 序号 | Task | 优先级 | 依赖 |
|------|------|--------|------|
| 1 | FIELD_MAP补全9个缺失字段 | P0 | - |
| 2 | 评论采集逻辑重构 | P0 | - |
| 3 | 高意向用户数据精确提取 | P1 | - |
| 4 | 数据完整性自检函数 | P1 | Task-1 |
| 5 | _version字段添加 | P2 | - |

## 资源
- 脚本文件: `tampermonkey/alive-broadcast-sync.user.js`
- 参考DOM: `.data/20260521_1336/评论.txt`、`.data/20260521_1336/高意向.txt`

---

### Task 2-1: FIELD_MAP补全9个缺失字段

#### 任务描述
在油猴脚本的FIELD_MAP中补充缺失的9个字段映射（DOM标签文本→JSON字段名）。

#### 所属Phase
- Phase-2: 油猴脚本数据完整性

#### 优先级
P0

---

#### 一、执行逻辑

##### 1. 触发
| 项目 | 内容 |
|------|------|
| 触发场景 | collectMetrics()执行时 |
| 触发位置 | user.js FIELD_MAP字典 |

##### 2. 逻辑处理
| 项目 | 内容 |
|------|------|
| 处理文件 | tampermonkey/alive-broadcast-sync.user.js |
| 处理位置 | FIELD_MAP对象定义处（约第136-158行） |
| 核心变更 | 增加9个缺失的key-value映射 |

##### 3. 缺失字段映射

| DOM标签文本 | JSON字段名 | 说明 |
|-------------|-----------|------|
| 线索成本 | lead_cost | 复盘表中有此字段 |
| 平均在线人数 | avg_online | 线索大屏有此指标 |
| 实时在线人数 | realtime_online | 线索大屏有此指标 |
| 千次观看GMV | gmv_per_mille | 复盘表中有 |
| 商品曝光次数 | product_exposure | 复盘表中有 |
| 分享率 | share_rate | 线索大屏有（注意与share_count区分） |
| 表单提交人数 | form_submits | 线索大屏有 |
| 看过 | exposure_views | 线索大屏"看过"字段 |
| 粉丝 | fan_count | 线索大屏"粉丝"字段 |

注意：部分字段在页面上可能显示为不同文本（如"看过"对应exposure_views），需在真实DOM中确认。

---

#### 二、文件操作

##### 修改

| 路径 | 修改点 |
|------|--------|
| `tampermonkey/alive-broadcast-sync.user.js` | FIELD_MAP对象中追加9个字段映射 |

---

#### 三、验收条件
- [ ] FIELD_MAP包含44个（或更多）映射项
- [ ] 与models.py中SessionMetric的列名对应
- [ ] 在真实页面上验证每个DOM标签文本能被getValueByLabel找到

---

### Task 2-2: 评论采集逻辑重构

#### 任务描述
重构collectComments()，从粗糙的text.split(':')改为精确的DOM结构定位。

#### 所属Phase
- Phase-2: 油猴脚本数据完整性

#### 优先级
P0

---

#### 一、执行逻辑

##### 1. 触发
| 项目 | 内容 |
|------|------|
| 触发场景 | collectComments()被startCollection调用 |
| 前置操作 | 点击"评论"Tab（data-log-name="评论"），等待500ms |

##### 2. DOM结构分析（基于.data/20260521_1336/评论.txt实际结构）

从实际HTML可知评论列表结构为：
```
每行评论 = div.V7dU-BUK2r0g7B（虚拟列表行）
  ├── div[width=160px] → 昵称
  ├── div[width=120px] → 是否留资（span文本"已留资"/"未留资"）
  ├── div[width=600px] → 评论内容（p标签）
  ├── div[width=150px] → 评论时间
  └── div[width=160px] → 操作按钮（忽略）
```

##### 3. 采集逻辑

```
1. 点击评论Tab → 等待500ms
2. 找到评论列表容器（通过"昵称"列头文本定位父容器）
3. 虚拟滚动采集：
   a. 记录已采集的评论（用"昵称+时间"作为唯一标识去重）
   b. 每次滚动300px → 等待300ms → 提取当前可见行
   c. 直到scrollTop不再变化
4. 每行提取：
   - 昵称：第1个子div内的文本
   - is_lead：第2个子div内span的文本是否包含"已留资"
   - content：第3个子div内p标签的文本
   - comment_time：第4个子div的文本
```

##### 4. 关键点
- 不使用动态class名（V7dU-xxx）定位，使用width样式或子元素顺序
- 虚拟列表只渲染可视区域，必须边滚动边采集+去重

---

#### 二、文件操作

##### 修改

| 路径 | 修改点 |
|------|--------|
| `tampermonkey/alive-broadcast-sync.user.js` | 重写collectComments()函数，替换text.split逻辑为精确DOM定位 |

---

#### 三、验收条件
- [ ] 评论数量与页面显示的总数一致
- [ ] 昵称、内容、时间三字段无错位
- [ ] is_lead正确区分"已留资"和"未留资"
- [ ] 虚拟滚动场景下不遗漏数据

---

### Task 2-3: 高意向用户数据精确提取

#### 任务描述
重构collectHighIntentUsers()，精确提取评论数和停留时长。

#### 所属Phase
- Phase-2: 油猴脚本数据完整性

#### 优先级
P1

---

#### 一、执行逻辑

##### 1. DOM结构分析（基于.data/20260521_1336/高意向.txt）

高意向用户卡片结构：
```
每个用户 = div[role="listitem"]
  ├── div.头像区 → img.src（头像URL）+ p（昵称）
  ├── div.操作区 → "忽略"按钮 + "私信"按钮
  └── div.数据区
       ├── div → p"评论数" + p"2条"（提取数字）
       └── div → p"停留时长" + p"20.7分钟"（原文保留）
```

##### 2. 采集逻辑

```
1. 点击"高意向"Tab → 等待500ms
2. 找到"共 N 个高意向用户"文本，提取总数N
3. 找到rc-virtual-list容器
4. 遍历所有[role="listitem"]：
   - nickname：img标签的alt属性（如"光伏打孔 avatar"→去掉" avatar"）或相邻p标签文本
   - avatar_url：img.src
   - comment_count：找到"评论数"文本的相邻元素，提取数字（"2条"→2）
   - stay_duration：找到"停留时长"文本的相邻元素，保留原文（"20.7分钟"）
   - status：检查卡片内是否有绿色标签"已留资"或红色"未留资"
```

---

#### 二、文件操作

##### 修改

| 路径 | 修改点 |
|------|--------|
| `tampermonkey/alive-broadcast-sync.user.js` | 重写collectHighIntentUsers()，精确定位评论数/停留时长/状态 |

---

#### 三、验收条件
- [ ] comment_count为实际数字（非固定0）
- [ ] stay_duration为实际文本（如"20.7分钟"，非空）
- [ ] 头像URL完整（https://开头）
- [ ] 用户数量与页面"共N个"一致

---

### Task 2-4: 数据完整性自检函数

#### 任务描述
在发送数据前增加validateMetrics()自检，统计空值比例并输出日志。

#### 所属Phase
- Phase-2: 油猴脚本数据完整性

#### 优先级
P1

---

#### 一、执行逻辑

##### 1. 逻辑处理
| 项目 | 内容 |
|------|------|
| 处理文件 | tampermonkey/alive-broadcast-sync.user.js |
| 插入位置 | sendToServer()调用前 |
| 核心逻辑 | 统计metrics中"--"/null/undefined的比例 |

##### 2. 自检规则

| 完整率 | 行为 |
|--------|------|
| ≥70% | 正常发送，日志输出"指标完整率: XX%" |
| 50%~70% | 发送但输出警告"⚠️ 完整率偏低，可能DOM结构已变化" |
| <50% | 跳过该场，输出错误"❌ 完整率过低，跳过该场次" |

---

#### 二、文件操作

##### 修改

| 路径 | 修改点 |
|------|--------|
| `tampermonkey/alive-broadcast-sync.user.js` | 新增validateMetrics(metrics)函数；在collectCurrentSession返回前调用 |

---

#### 三、验收条件
- [ ] 控制台输出"指标完整率: XX%"
- [ ] 完整率<50%时跳过该场（不发送垃圾数据）
- [ ] 完整率50-70%时发送但有警告

---


### Task 2-5: _version字段添加（续）

#### 优先级
P2

---

#### 一、执行逻辑

##### 1. 触发
| 项目 | 内容 |
|------|------|
| 触发场景 | 油猴脚本POST数据时 / 服务端接收数据时 |
| 涉及两端 | 油猴脚本（发送端）+ 服务端（接收端） |

##### 2. 油猴脚本端
| 项目 | 内容 |
|------|------|
| 处理文件 | tampermonkey/alive-broadcast-sync.user.js |
| 处理位置 | collectCurrentSession()返回值构造处 |
| 核心变更 | 返回对象顶层增加 `_version: "1.0"` |

##### 3. 服务端
| 项目 | 内容 |
|------|------|
| 处理文件 | server/routers/api.py |
| 处理位置 | SessionData Pydantic模型 + receive_session()函数开头 |
| 核心变更 | 模型增加 `_version: str = "1.0"`；函数开头增加版本校验 |

##### 4. 校验逻辑

```
SUPPORTED_VERSIONS = ["1.0"]

def receive_session(data):
    version = getattr(data, '_version', '1.0')
    if version not in SUPPORTED_VERSIONS:
        return {"code": 400, "message": f"不支持的数据版本: {version}，请更新油猴脚本"}
    # 继续正常处理...
```

---

#### 二、文件操作

##### 修改

| 路径 | 修改点 |
|------|--------|
| `tampermonkey/alive-broadcast-sync.user.js` | collectCurrentSession()返回对象增加`_version: "1.0"` |
| `server/routers/api.py` | SessionData模型增加`_version`字段；receive_session开头增加版本校验 |

---

#### 三、验收条件
- [ ] 油猴脚本发送的JSON包含`_version: "1.0"`
- [ ] 服务端正常接收`_version=1.0`的数据
- [ ] 发送`_version=2.0`时返回400错误
- [ ] 不发送`_version`时默认为"1.0"（向后兼容）

---

# Phase-3: 邮件与报告增强

## 关联Milestone
- Milestone: AliveBroadcastData 系统优化

## 功能描述
使邮件推送包含AI分析摘要和异常标注，周报包含AI周度分析，邮件测试按钮真正发送。

## 包含的Task

| 序号 | Task | 优先级 | 依赖 |
|------|------|--------|------|
| 1 | 邮件测试接口真正发送 | P0 | - |
| 2 | 周报增加AI周度分析调用 | P0 | Phase-1完成 |
| 3 | 日报邮件增加AI摘要+异常标注 | P0 | Phase-1完成 |

## 资源
- 后端文件: `server/routers/admin.py`, `server/services/report_service.py`, `server/services/email_service.py`, `server/templates/email/daily_report.html`
- 数据库: reports表（读取AI分析结果）

---

### Task 3-1: 邮件测试接口真正发送

#### 任务描述
将`/admin/api/email/test`从空实现改为真正调用email_service发送测试邮件。

#### 所属Phase
- Phase-3: 邮件与报告增强

#### 优先级
P0

---

#### 一、执行逻辑

##### 1. 触发
| 项目 | 内容 |
|------|------|
| 触发页面 | /admin/email（邮箱配置页） |
| 触发按钮 | "发送测试邮件" |
| 触发事件 | onClick → fetch POST /admin/api/email/test |

##### 2. 路由
| 项目 | 内容 |
|------|------|
| 后端API | POST /admin/api/email/test |
| 认证 | JWT Token（get_current_admin） |

##### 3. 逻辑处理
| 项目 | 内容 |
|------|------|
| 处理文件 | server/routers/admin.py |
| 处理函数 | test_email() — 当前第85-87行 |
| 核心变更 | 从settings读取邮箱配置 → 调用email_service.send_email() → 返回结果 |

##### 4. 处理流程

```
1. 从settings表读取 email_smtp_host/port/sender/password/receivers
2. 校验配置完整性（sender和password不能为空，receivers不能为空数组）
3. 调用 send_email(
     subject="【AliveBroadcastData】邮件配置测试",
     html="<h2>✅ 邮件配置成功</h2><p>如果您收到此邮件，说明SMTP配置正确。</p><p>发送时间: {now}</p>",
     config=config,
     receivers=receivers
   )
4. 成功 → {"code": 0, "message": "测试邮件已发送"}
5. 失败 → {"code": 500, "message": f"发送失败: {具体错误}"}
```

##### 5. 数据库
| 项目 | 内容 |
|------|------|
| 数据库 | SQLite |
| 数据表 | settings |
| 操作类型 | 查询（读取邮箱配置） |

##### 6. 响应
| 场景 | 响应 |
|------|------|
| 成功 | `{"code": 0, "message": "测试邮件已发送"}` |
| 配置不完整 | `{"code": 400, "message": "请先完善邮箱配置"}` |
| SMTP连接失败 | `{"code": 500, "message": "SMTP连接失败: Connection refused"}` |
| 认证失败 | `{"code": 500, "message": "SMTP认证失败: 授权码错误"}` |

---

#### 二、文件操作

##### 修改

| 路径 | 修改点 |
|------|--------|
| `server/routers/admin.py` | 重写test_email()函数，从空返回改为真正调用email_service |

---

#### 三、验收条件
- [ ] 点击"发送测试邮件"后，收件人实际收到邮件
- [ ] 配置错误时返回具体错误信息（非通用500）
- [ ] 收件人列表为空时返回400提示

---

### Task 3-2: 周报增加AI周度分析调用

#### 任务描述
在generate_weekly_report()末尾，将整周汇总数据发送给AI，获取周度分析并追加到周报中。

#### 所属Phase
- Phase-3: 邮件与报告增强

#### 优先级
P0

---

#### 一、执行逻辑

##### 1. 触发
| 项目 | 内容 |
|------|------|
| 触发场景 | weekly_report_job定时任务（每周一02:00） |
| 触发位置 | report_service.py generate_weekly_report()末尾 |

##### 2. 逻辑处理
| 项目 | 内容 |
|------|------|
| 处理文件 | server/services/report_service.py |
| 处理函数 | generate_weekly_report() |
| 插入位置 | Markdown生成完毕、存入reports表之前 |
| 核心变更 | 调用AI分析整周数据，追加"## AI周度分析"章节 |

##### 3. AI调用逻辑

```
1. 已生成的周报Markdown（含总览+环比+每日+主播数据）作为上下文
2. 构建prompt: "请基于以下一周直播数据汇总，给出周度趋势分析和下周优化建议：\n\n{md}"
3. 从settings读取AI配置
4. 调用OpenAI API（system_prompt + weekly_prompt）
5. 成功 → md += "\n## 五、AI周度分析\n\n{ai_response}\n"
6. 失败 → md += "\n## 五、AI周度分析\n\n（生成失败，请手动触发）\n"
7. 不阻塞周报存储（try-except包裹）
```

##### 4. 数据库
| 项目 | 内容 |
|------|------|
| 读取表 | settings（AI配置） |
| 写入表 | reports（周报内容含AI分析） |

---

#### 二、文件操作

##### 修改

| 路径 | 修改点 |
|------|--------|
| `server/services/report_service.py` | generate_weekly_report()末尾增加AI调用逻辑（try-except包裹） |

---

#### 三、验收条件
- [ ] 周报Markdown末尾包含"## 五、AI周度分析"章节
- [ ] AI分析内容基于整周数据（非单场）
- [ ] AI调用失败不影响周报存储（降级为"生成失败"文本）
- [ ] 报告中心下载的周报包含AI分析

---

### Task 3-3: 日报邮件增加AI摘要+异常标注

#### 任务描述
日报邮件模板中每场数据下方展示AI分析摘要，线索成本异常时数字标红。

#### 所属Phase
- Phase-3: 邮件与报告增强

#### 优先级
P0

---

#### 一、执行逻辑

##### 1. 触发
| 项目 | 内容 |
|------|------|
| 触发场景 | email_job定时任务（每天01:30） |
| 触发位置 | email_service.py send_daily_report() |

##### 2. 数据准备变更（email_service.py）
| 项目 | 内容 |
|------|------|
| 处理文件 | server/services/email_service.py |
| 处理函数 | send_daily_report() |
| 核心变更 | 每场数据中增加ai_summary字段；计算avg_cost传入模板 |

```
对每场session：
1. 查询 reports 表（type="session", session_id=s.id）
2. 如果有报告 → ai_summary = report.content[:200] + "..."
3. 如果没有 → ai_summary = None

计算动态阈值：
avg_cost = total_spend / total_leads（全天平均）
cost_threshold = avg_cost * 1.5

传入模板：sessions列表中每项增加ai_summary字段；传入cost_threshold
```

##### 3. 模板变更（daily_report.html）
| 项目 | 内容 |
|------|------|
| 处理文件 | server/templates/email/daily_report.html |
| 核心变更 | 1. 每场卡片下方增加AI摘要区域；2. 成本数字增加条件红色样式 |

模板增加内容：
```html
<!-- 每场卡片内，数据表格之后 -->
{% if s.ai_summary %}
<div style="background: #f0f7ff; border-left: 3px solid #1890ff; padding: 10px 12px; margin-top: 10px; border-radius: 4px;">
    <strong style="color: #1890ff;">AI分析：</strong>
    <span style="color: #555;">{{ s.ai_summary }}</span>
</div>
{% endif %}

<!-- 成本数字的条件红色 -->
<strong style="color: {% if s.lead_cost > cost_threshold %}#ff4d4f{% else %}#333{% endif %};">
    ¥{{ s.lead_cost }}
</strong>
```

---

#### 二、文件操作

##### 修改

| 路径 | 修改点 |
|------|--------|
| `server/services/email_service.py` | send_daily_report()中查询每场AI报告，计算cost_threshold，传入模板 |
| `server/templates/email/daily_report.html` | 增加AI摘要展示区域 + 成本条件红色样式 |

---

#### 三、验收条件
- [ ] 邮件中每场数据下方显示AI分析摘要（蓝色左边框区域）
- [ ] AI未完成的场次不显示摘要区域（不显示空白）
- [ ] 线索成本 > 全天均值×1.5 时数字为红色
- [ ] 线索成本正常时数字为黑色

---

# Phase-4: 前台功能补全

## 关联Milestone
- Milestone: AliveBroadcastData 系统优化

## 功能描述
补全趋势分析的时段分组、漏斗图转化率标注、线索有效性筛选。

## 包含的Task

| 序号 | Task | 优先级 | 依赖 |
|------|------|--------|------|
| 1 | 趋势API实现group_by分组 | P1 | - |
| 2 | 漏斗图增加转化率formatter | P1 | - |
| 3 | /api/leads增加is_valid筛选 | P1 | - |

## 资源
- 后端文件: `server/routers/api.py`
- 前端模板: `server/templates/session_detail.html`, `server/templates/trends.html`

---

### Task 4-1: 趋势API实现group_by分组

#### 任务描述
使`/api/trends`的`group_by`参数真正生效，支持按日期/小时/星期分组。

#### 所属Phase
- Phase-4: 前台功能补全

#### 优先级
P1

---

#### 一、执行逻辑

##### 1. 路由
| 项目 | 内容 |
|------|------|
| 后端API | GET /api/trends?group_by=date\|hour\|weekday |

##### 2. 逻辑处理
| 项目 | 内容 |
|------|------|
| 处理文件 | server/routers/api.py |
| 处理函数 | trends_api() |
| 核心变更 | 根据group_by值切换SQL分组逻辑 |

##### 3. 分组逻辑

```
if group_by == "date":
    # 当前已有逻辑：按 start_time[:10] 分组
    group_expr = func.substr(Session.start_time, 1, 10)
    
elif group_by == "hour":
    # 按开播小时分组（0-23）
    group_expr = func.cast(func.substr(Session.start_time, 12, 2), Integer)
    # 返回格式: [{"hour": 9, "avg_leads": 3.5, "avg_spend": 1050, "session_count": 5}]
    
elif group_by == "weekday":
    # 按星期几分组（0=周日, 1=周一, ..., 6=周六）
    # SQLite: strftime('%w', start_time)
    group_expr = func.strftime('%w', Session.start_time)
    # 返回格式: [{"weekday": 1, "avg_leads": 4.2, "avg_spend": 980, "session_count": 8}]
```

##### 4. 响应格式

**group_by=hour:**
```json
{"code": 0, "data": [
    {"hour": 9, "avg_leads": 3.5, "avg_spend": 1050, "session_count": 5},
    {"hour": 14, "avg_leads": 4.2, "avg_spend": 980, "session_count": 8}
]}
```

**group_by=weekday:**
```json
{"code": 0, "data": [
    {"weekday": "1", "weekday_name": "周一", "avg_leads": 4.0, "session_count": 6},
    {"weekday": "5", "weekday_name": "周五", "avg_leads": 3.2, "session_count": 4}
]}
```

---

#### 二、文件操作

##### 修改

| 路径 | 修改点 |
|------|--------|
| `server/routers/api.py` | trends_api()中增加if/elif分支，按group_by值切换分组查询 |
| `server/templates/trends.html` | 增加"时段分析"区域，调用group_by=hour渲染柱状图 |

---

#### 三、验收条件
- [ ] `/api/trends?group_by=hour` 返回24小时分组数据
- [ ] `/api/trends?group_by=weekday` 返回7天分组数据
- [ ] 趋势分析页面可切换"按日期/按时段/按星期"视图
- [ ] 时段柱状图正确渲染

---

### Task 4-2: 漏斗图增加转化率formatter

#### 任务描述
场次详情页漏斗图每个环节显示转化率百分比。

#### 所属Phase
- Phase-4: 前台功能补全

#### 优先级
P1

---

#### 一、执行逻辑

##### 1. 触发
| 项目 | 内容 |
|------|------|
| 触发页面 | /session/{id}（场次详情页） |
| 触发Tab | "漏斗"Tab |

##### 2. 逻辑处理
| 项目 | 内容 |
|------|------|
| 处理文件 | server/templates/session_detail.html |
| 处理位置 | renderFunnel()函数中ECharts配置 |
| 核心变更 | series.label.formatter增加转化率计算 |

##### 3. formatter逻辑

```javascript
label: {
    show: true,
    formatter: function(params) {
        const funnelData = [曝光, 观看, 深度观看, 互动, 留资]; // 从外部传入
        const idx = params.dataIndex;
        if (idx === 0) return params.name + '\n' + params.value;
        const prevValue = funnelData[idx - 1];
        const rate = prevValue > 0 ? ((params.value / prevValue) * 100).toFixed(1) : 0;
        return params.name + '\n' + params.value + '\n(' + rate + '%)';
    }
}
```

---

#### 二、文件操作

##### 修改

| 路径 | 修改点 |
|------|--------|
| `server/templates/session_detail.html` | renderFunnel()中ECharts series配置增加label.formatter |

---

#### 三、验收条件
- [ ] 漏斗图每层显示"名称\n数值\n(转化率%)"
- [ ] 第一层（曝光）只显示名称和数值（无上一层）
- [ ] 转化率计算正确（当前层/上一层×100）

---

### Task 4-3: /api/leads增加is_valid筛选

#### 任务描述
前台线索总览API增加有效性筛选参数。

#### 所属Phase
- Phase-4: 前台功能补全

#### 优先级
P1

---

#### 一、执行逻辑

##### 1. 路由
| 项目 | 内容 |
|------|------|
| 后端API | GET /api/leads?is_valid=true\|false\|null |

##### 2. 逻辑处理
| 项目 | 内容 |
|------|------|
| 处理文件 | server/routers/api.py |
| 处理函数 | list_leads() |
| 核心变更 | 增加is_valid参数和对应filter |

##### 3. 筛选逻辑

```python
# 参数定义
is_valid: Optional[str] = None  # "true" / "false" / "null"（未验证）

# 筛选逻辑
if is_valid == "true":
    query = query.filter(Lead.is_valid == True)
elif is_valid == "false":
    query = query.filter(Lead.is_valid == False)
elif is_valid == "null":
    query = query.filter(Lead.is_valid == None)
```

注意：用字符串而非bool，因为需要区分"未传参"和"筛选未验证(null)"。

---

#### 二、文件操作

##### 修改

| 路径 | 修改点 |
|------|--------|
| `server/routers/api.py` | list_leads()增加is_valid参数和filter逻辑 |
| `server/templates/leads.html` | 筛选栏增加"有效性"下拉（全部/有效/无效/未验证） |

---

#### 三、验收条件
- [ ] `/api/leads?is_valid=true` 只返回有效线索
- [ ] `/api/leads?is_valid=null` 只返回未验证线索
- [ ] 不传is_valid时返回全部
- [ ] 前端下拉筛选联动正确

---

# Phase-5: 后台功能补全

## 关联Milestone
- Milestone: AliveBroadcastData 系统优化

## 包含的Task

| 序号 | Task | 优先级 | 依赖 |
|------|------|--------|------|
| 1 | 后台线索管理页面 | P2 | - |
| 2 | 成单弹窗增加场次/线索关联 | P2 | - |

---

### Task 5-1: 后台线索管理页面

#### 任务描述
新建admin/leads.html，管理员可查看全部线索并标记有效性。

#### 所属Phase
- Phase-5: 后台功能补全

#### 优先级
P2

---

#### 一、执行逻辑

##### 1. 触发
| 项目 | 内容 |
|------|------|
| 触发页面 | /admin/leads |
| 触发入口 | 后台侧边栏"线索管理"菜单 |

##### 2. 路由
| 项目 | 内容 |
|------|------|
| 页面路由 | GET /admin/leads → pages.py → admin/leads.html |
| 数据API | GET /admin/api/leads（已有） |
| 标记API | PUT /admin/api/leads/{id}（已有） |
| 批量API | POST /admin/api/leads/batch（已有） |

##### 3. 页面功能
- 线索列表（分页，每页20条）
- 筛选：按场次日期、城市、有效性
- 单条标记：每行有"有效/无效/未验证"下拉
- 批量标记：勾选多条 → 顶部"批量标记为有效/无效"按钮
- 显示字段：昵称、城市、留资时间、路径、标签、有效性、成单状态

---

#### 二、文件操作

##### 新建

| 路径 | 用途 |
|------|------|
| `server/templates/admin/leads.html` | 后台线索管理页面 |

##### 修改

| 路径 | 修改点 |
|------|--------|
| `server/templates/admin/base.html` | 侧边栏增加"线索管理"链接 |
| `server/routers/pages.py` | 增加 GET /admin/leads 页面路由 |

---

#### 三、验收条件
- [ ] 后台侧边栏出现"线索管理"入口
- [ ] 线索列表正确展示（分页）
- [ ] 单条标记有效性后刷新列表
- [ ] 批量标记功能正常
- [ ] 需JWT认证（未登录重定向）

---

### Task 5-2: 成单弹窗增加场次/线索关联

#### 任务描述
成单新增弹窗中增加"关联场次"和"关联线索"下拉选择。

#### 所属Phase
- Phase-5: 后台功能补全

#### 优先级
P2

---

#### 一、执行逻辑

##### 1. 触发
| 项目 | 内容 |
|------|------|
| 触发页面 | /admin/deals |
| 触发按钮 | "新增成单" |
| 触发事件 | 弹窗打开时加载场次列表 |

##### 2. 交互逻辑

```
1. 弹窗打开 → fetch GET /api/sessions（获取最近30场）→ 填充"关联场次"下拉
2. 用户选择场次 → fetch GET /admin/api/leads?session_id={id}（获取该场线索）→ 填充"关联线索"下拉
3. "关联线索"下拉默认disabled，选择场次后enabled
4. 提交时 session_id 和 lead_id 一起POST
```

##### 3. 下拉选项格式
- 场次下拉：`{id} | {start_time[:16]}（{duration}分钟，{leads}条线索）`
- 线索下拉：`{id} | {nickname} | {city} | {lead_time}`

---

#### 二、文件操作

##### 修改

| 路径 | 修改点 |
|------|--------|
| `server/templates/admin/deals.html` | 新增弹窗增加两个select元素 + Alpine.js联动逻辑 |

---

#### 三、验收条件
- [ ] 场次下拉显示最近30场
- [ ] 选择场次后线索下拉自动加载
- [ ] 提交后session_id和lead_id正确关联
- [ ] 不选场次时线索下拉disabled

---

# Phase-6: 部署与文档收尾

## 关联Milestone
- Milestone: AliveBroadcastData 系统优化

## 包含的Task

| 序号 | Task | 优先级 | 依赖 |
|------|------|--------|------|
| 1 | start.bat增加端口检查 | P3 | - |
| 2 | README增加FAQ | P3 | - |
| 3 | 敏感信息移到环境变量 | P2 | - |
| 4 | 创建.gitignore | P2 | - |
| 5 | 定时任务时间线调整 | P1 | Phase-1完成 |

---

### Task 6-1: 定时任务时间线调整

#### 任务描述
将daily_report_job从01:00改为01:20，确保AI分析（01:05触发）完成后再生成日报。

#### 所属Phase
- Phase-6: 部署与文档收尾

#### 优先级
P1

---

#### 一、执行逻辑

##### 1. 问题分析
当前时间线：01:00日报生成 → 01:05 AI分析 → 01:30邮件推送
问题：日报在AI分析之前生成，日报中不含AI摘要。

##### 2. 修正后时间线
```
00:00 - 油猴脚本采集
01:05 - AI自动分析（analyze_job）
01:20 - 日报生成（daily_report_job）← 改为01:20
01:30 - 邮件推送（email_job）
02:00 - 周报（周一）
03:00 - 月报（1号）
04:00 - 备份
```

##### 3. 逻辑处理
| 项目 | 内容 |
|------|------|
| 处理文件 | server/services/scheduler.py |
| 处理位置 | init_scheduler()中daily_report_job的CronTrigger |
| 核心变更 | `CronTrigger(hour=1, minute=0)` → `CronTrigger(hour=1, minute=20)` |

---

#### 二、文件操作

##### 修改

| 路径 | 修改点 |
|------|--------|
| `server/services/scheduler.py` | daily_report_job的minute从0改为20 |

---


#### 三、验收条件
- [ ] 日报在01:20生成（AI分析01:05后已完成）
- [ ] 日报中包含AI分析摘要（因为AI已在01:05~01:15完成）
- [ ] 邮件01:30推送时日报内容完整
- [ ] 时间线无冲突

---

### Task 6-2: 敏感信息移到环境变量

#### 任务描述
将database.py中硬编码的AI Key和邮箱授权码改为从环境变量读取。

#### 所属Phase
- Phase-6: 部署与文档收尾

#### 优先级
P2

---

#### 一、执行逻辑

##### 1. 逻辑处理
| 项目 | 内容 |
|------|------|
| 处理文件 | server/database.py |
| 处理位置 | init_db()中default_settings列表 |
| 核心变更 | 将硬编码值改为`os.getenv("ENV_KEY", "")`读取 |

##### 2. 环境变量映射

| 当前硬编码 | 环境变量名 | 默认值 |
|-----------|-----------|--------|
| `github_pat_11BRQSPZA0...` | `AI_API_KEY` | `""`（空） |
| `https://models.github.ai/inference` | `AI_BASE_URL` | `"https://api.openai.com/v1"` |
| `meta/Llama-3.2-90B-Vision-Instruct` | `AI_MODEL` | `"gpt-4o"` |
| `PMFHEFUVASHUISBQ` | `EMAIL_PASSWORD` | `""`（空） |
| `buchang_123@163.com` | `EMAIL_SENDER` | `""`（空） |
| `["164093410@qq.com"]` | `EMAIL_RECEIVERS` | `"[]"` |

##### 3. 实现方式

```python
# database.py init_db() 中
import os

default_settings = [
    ("admin_username", DEFAULT_ADMIN_USERNAME),
    ("admin_password", hash_password(DEFAULT_ADMIN_PASSWORD)),
    ("ai_api_key", os.getenv("AI_API_KEY", "")),
    ("ai_base_url", os.getenv("AI_BASE_URL", "https://api.openai.com/v1")),
    ("ai_model", os.getenv("AI_MODEL", "gpt-4o")),
    # ...其余同理
]
```

##### 4. 配套：创建 `.env.example` 文件

```
# AI配置
AI_API_KEY=your_api_key_here
AI_BASE_URL=https://models.github.ai/inference
AI_MODEL=meta/Llama-3.2-90B-Vision-Instruct

# 邮箱配置
EMAIL_SENDER=your_email@163.com
EMAIL_PASSWORD=your_smtp_password
EMAIL_RECEIVERS=["receiver@qq.com"]
```

---

#### 二、文件操作

##### 新建

| 路径 | 用途 |
|------|------|
| `.env.example` | 环境变量模板（不含真实值） |

##### 修改

| 路径 | 修改点 |
|------|--------|
| `server/database.py` | init_db()中敏感默认值改为os.getenv()读取 |
| `README.md` | 增加"配置环境变量"说明 |

---

#### 三、验收条件
- [ ] 代码中不再包含任何真实API Key或密码
- [ ] `.env.example`包含所有需要配置的环境变量
- [ ] 不设置环境变量时系统仍能启动（默认值为空，后台配置后生效）
- [ ] 已有data.db中的settings不受影响（init_db只在key不存在时插入）

---

### Task 6-3: 创建.gitignore

#### 任务描述
创建.gitignore排除敏感文件和临时文件。

#### 所属Phase
- Phase-6: 部署与文档收尾

#### 优先级
P2

---

#### 一、执行逻辑

##### 1. 文件内容

```gitignore
# 数据库
server/data.db
server/data.db-shm
server/data.db-wal

# 备份
server/backups/

# Python
__pycache__/
*.pyc
*.pyo
venv/
.venv/

# 环境变量
.env

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db
```

---

#### 二、文件操作

##### 新建

| 路径 | 用途 |
|------|------|
| `.gitignore` | Git忽略规则 |

---

#### 三、验收条件
- [ ] `git status`不显示data.db、__pycache__、.env
- [ ] `.env.example`不被忽略（可提交）

---

### Task 6-4: start.bat增加端口检查

#### 任务描述
Windows启动脚本开头检查8000端口是否被占用。

#### 所属Phase
- Phase-6: 部署与文档收尾

#### 优先级
P3

---

#### 一、执行逻辑

##### 1. 逻辑处理
| 项目 | 内容 |
|------|------|
| 处理文件 | start.bat |
| 插入位置 | Python检查之前 |
| 核心逻辑 | `netstat -ano \| findstr ":8000"` 检测端口占用 |

##### 2. 检测逻辑

```batch
REM 检查端口占用
netstat -ano | findstr ":8000 " >nul 2>&1
if not errorlevel 1 (
    echo [警告] 端口8000已被占用
    echo 请关闭占用进程后重试，或修改config.py中的PORT
    pause
    exit /b 1
)
```

---

#### 二、文件操作

##### 修改

| 路径 | 修改点 |
|------|--------|
| `start.bat` | 开头增加端口检查逻辑（Python检查之前） |

---

#### 三、验收条件
- [ ] 端口空闲时正常启动
- [ ] 端口被占用时给出明确提示并退出

---

### Task 6-5: README增加FAQ

#### 任务描述
README末尾增加常见问题解答章节。

#### 所属Phase
- Phase-6: 部署与文档收尾

#### 优先级
P3

---

#### 一、执行逻辑

##### 1. FAQ内容

```markdown
## 常见问题

**Q: 油猴脚本安装后不触发采集？**
A: 确认浏览器保持打开life.douyin.com页面，检查控制台是否有"[直播同步] 脚本已加载"日志。如果没有，检查@match规则是否匹配当前URL。

**Q: 邮件发送失败？**
A: 163邮箱需要开启SMTP服务并获取授权码（非登录密码）。在163邮箱设置→POP3/SMTP中开启，获取授权码填入后台配置。

**Q: AI分析返回空或报错？**
A: 检查后台AI配置的API Key是否有效、base_url是否正确。可点击"测试连接"验证。Github Models的base_url为 https://models.github.ai/inference。

**Q: 数据库报"database is locked"？**
A: 系统已配置WAL模式，正常情况不会出现。如仍出现，重启服务即可。避免同时运行多个服务实例。

**Q: 端口8000被占用？**
A: 修改server/config.py中的PORT为其他端口（如8001），同时更新油猴脚本中的SERVER_URL。
```

---

#### 二、文件操作

##### 修改

| 路径 | 修改点 |
|------|--------|
| `readme.md` | 末尾增加"## 常见问题"章节（5个Q&A） |

---

#### 三、验收条件
- [ ] README包含5个常见问题及解答
- [ ] 每个Q&A有具体可操作的解决步骤

---

# 执行顺序总览

```
Phase-1（AI分析完善）
  Task 1-1: FIELD_LABELS补全 ─────────────────┐
  Task 1-2: 全量提示词构建 ──── 依赖1-1 ──────┤
  Task 1-3: 使用settings模板 ── 依赖1-2 ──────┤
  Task 1-4: 重试机制 ────────── 依赖1-3 ──────┘
                                               │
Phase-2（油猴脚本完整性）                       │ 可并行
  Task 2-1: FIELD_MAP补全 ─────────────────────┤
  Task 2-2: 评论采集重构 ──────────────────────┤
  Task 2-3: 高意向精确提取 ────────────────────┤
  Task 2-4: 完整性自检 ──── 依赖2-1 ───────────┤
  Task 2-5: _version字段 ─────────────────────┘
                                               │
Phase-3（邮件与报告）────── 依赖Phase-1完成 ────┘
  Task 3-1: 邮件测试真发送
  Task 3-2: 周报AI分析
  Task 3-3: 邮件AI摘要+异常标注

Phase-4（前台补全）
  Task 4-1: trends group_by
  Task 4-2: 漏斗图转化率
  Task 4-3: is_valid筛选

Phase-5（后台补全）
  Task 5-1: 线索管理页面
  Task 5-2: 成单弹窗关联

Phase-6（收尾）
  Task 6-1: 定时任务时间线 ── 依赖Phase-1
  Task 6-2: 敏感信息环境变量
  Task 6-3: .gitignore
  Task 6-4: start.bat端口检查
  Task 6-5: README FAQ
```

---

# 整体验收标准

| # | 验收项 | 验证方式 |
|---|--------|----------|
| 1 | AI分析报告提及具体线索城市和评论内容 | 手动触发分析，检查报告内容 |
| 2 | 油猴脚本44字段完整率≥95% | 在真实页面采集后对比数据库 |
| 3 | 评论数据昵称/内容/时间无错位 | 对比页面显示和数据库记录 |
| 4 | 邮件包含AI摘要和红色异常标注 | 触发邮件推送，检查收到的邮件 |
| 5 | 周报末尾有"AI周度分析"章节 | 手动触发周报生成，下载检查 |
| 6 | 邮件测试按钮真正发送邮件 | 后台点击按钮，检查收件箱 |
| 7 | 趋势分析支持时段视图 | 前端切换group_by=hour，图表渲染 |
| 8 | 代码中无硬编码敏感信息 | grep搜索API Key和密码 |
| 9 | 日报生成时间在AI分析之后 | 检查scheduler配置和日志时间戳 |
| 10 | .gitignore正确排除data.db和__pycache__ | git status验证 |