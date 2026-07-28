事实已完整。admin.py 路由前缀是 `/admin/api`,所以完整路由是 `/admin/api/clues/excel-upload` 和 `/admin/api/clues/excel-confirm`,与前端一致 —— 后端**已实现且路由连通**。

现在我已掌握全部事实,可以输出分析。关键发现总结:
1. **导入功能后端已存在**(admin.py:1985, 2090),前端 UI 也已存在(leads.html),但**只支持单 sheet、单一线索表**,完全不支持需求要求的"多 sheet 子表自动按列名区分 + 五种工作表类型 + 联系方式/微信组合唯一码去重 + 重复跳过提示 + 管理员查看"。
2. **openpyxl 版本有样式解析 bug**(Fill() takes no arguments),示例两个 xlsx **根本无法用 load_workbook 读取**——这是直接阻断因素。
3. 导入目标表是 `api_clues`,但 `excel-confirm` 只写入极少量字段(name/phone/weixin),**丢失了示例表里的省份/城市/学历/招生老师/跟进/标签/状态等全部业务维度**。
4. **没有"联系方式+微信"组合唯一约束**,`excel-confirm` 用随机 clue_id,每次导入都新增,不去重,**必然产生重复数据**。
5. 前端不传 session_id,且无法处理多 sheet。

下面是完整的分析与可执行计划。

---

# 需求分析：支持 xlsx/csv 多表多维度导入

## 1. 问题现象复述

需求目标：系统需支持从 **xlsx/csv 文件** 导入更多维度的数据，具体要求：
- 一个文件可有**多个 sheet 子表**，也可多个文件分别导入，系统**通过列名自动区分**子表类型；
- sheet 工作表类型包括：`直播数据分配表`、`直播排班表`、`教育在线`、`抖音代运营`、`朋友圈广告` 等（其中直播数据分配表每月一个表）；
- 每个表使用 **「联系方式 + 微信」组合值作为特征唯一码**，杜绝重复添加；导入发现重复值**提示重复跳过信息，管理员可查看**；
- 实际输入极可能是示例表一（`.docs/多维--数据分配.xlsx`）和示例表二（`.docs/直播--数据分配.xlsx`）的**合并文件**，每个文件默认第一行为列名。

**现象**：当前系统无法按上述方式导入。看似有"Excel导入"按钮，但实测无法满足任何一条核心需求（多 sheet 自动识别、五类工作表、联系方式+微信唯一码去重、重复跳过提示、管理员可见）。

## 2. 代码与日志事实证据

| # | 证据 | 来源 |
|---|------|------|
| E1 | 前端已有导入 UI，调用 `/admin/api/clues/excel-upload` 与 `/admin/api/clues/excel-confirm` | `server/templates/admin/leads.html:29,368,387` |
| E2 | 后端两路由已实现，前缀 `/admin/api`（main.py:43），故完整路径为 `/admin/api/clues/excel-upload` 和 `/admin/api/clues/excel-confirm` | `server/routers/admin.py:1985,2090`；`server/main.py:43` |
| E3 | `excel-upload` 仅读取 **`wb.active`（单一激活 sheet）**，用 `header_map` 匹配「手机号/姓名/微信号/私信时间/备注」5 列 | `server/routers/admin.py:2000,2008-2013` |
| E4 | `excel-confirm` 仅写 `ApiClue` 的 `name/phone_decrypted/weixin_manual/session_id/clue_source/raw_data` 6 个字段，其余业务维度（省份、城市、学历、招生老师、跟进、状态标签、留资时间、来源等）**全部丢弃** | `server/routers/admin.py:2109-2121` |
| E5 | `excel-confirm` 用随机 `clue_id=excel_{ts}_{rand}`，**无任何唯一约束/查重**，每次都新增 | `server/routers/admin.py:2107-2122` |
| E6 | `ApiClue` 表**没有「联系方式+微信」组合唯一索引**；`clue_id` 是唯一键（随机生成，永不冲突） | `server/models.py:320-321,380` |
| E7 | `Lead` 表有 `phone_masked`、`weixin` 字段，但**无唯一约束** | `server/models.py:80-99` |
| E8 | **openpyxl 当前版本无法解析示例文件**：`TypeError: Fill() takes no arguments`（样式解析崩溃），示例两个 xlsx 均无法用 `load_workbook` 打开 | 实测：`E:\Code\AliveBroadcastData\.docs\多维--数据分配.xlsx`、`直播--数据分配.xlsx` |
| E9 | 示例真实 sheet 与列名（用底层 zip 解析绕过样式 bug 得到）： | 实测输出（gbk 解码） |
| | 多维表：`教育在线`（来源/姓名/电话号码/目前学历/报考省份/报考学校/报考专业/报考层次/微信/所在省份/所在城市/所在区/数据替换/时间/备注/对话内容/分配日期/招生老师/数据状态与标签/提升形式/咨询反馈/一次跟进/二次跟进/三次跟进）、`抖音代运营`（分配月/留资时间/联系方式/招生老师/数据状态与标签/提升形式/咨询反馈/第一次跟进/第二次跟进）、`朋友圈广告`（分配月/日消耗/联系方式/学生姓名/招生老师/客户简单信息/咨询反馈/备注） | E9 |
| | 直播表：`新直播数据分配表(7月始)`（序号/留资日期/星期/留资时间/直播人员/留资方式/互动场景/联系方式[电话\|微信]/客户简单信息[评论\|私信\|所在城市]/招生老师反馈[老师\|状态标签\|提升形式\|跟进]/用户昵称/留资路径/投放账户/单元名称/单元ID…）、`直播排班表`（统计/日期/营销消耗/直播人员/直播时间/总时长/广告流线/自然流线/总线索/运营值班人员）、`直播数据(六月)`（分配月/直播人员/留资时间/联系方式/招生老师/客户简单信息/咨询反馈/提升形式/备注/留资方式） | E9 |
| E10 | 前端 `previewExcel` **不传 session_id**，且只把 `excel-upload` 返回的 `data` 直接 `confirmExcelImport` 发送，无法处理多 sheet/多类型 | `server/templates/admin/leads.html:363-400` |
| E11 | `clue_source` 字段已预留 `"excel"` 枚举值，说明设计上考虑过 Excel 导入，但实现仅覆盖"极简线索"场景 | `server/models.py:379` |

## 3. 关键调用链 / 路由链 / 数据链

**前端调用链**
```
leads.html 点击"📊 Excel导入"
  → handleExcelUpload() 取 file
  → previewExcel() → POST /admin/api/clues/excel-upload (FormData{file})   [leads.html:368]
  → 后端返回 {code,data:[{clue_id,name,phone,weixin,message_time,session_id,notes}]}
  → confirmExcelImport() → POST /admin/api/clues/excel-confirm ({items})  [leads.html:387]
  → 后端逐条 db.add(ApiClue(...)) → commit
```

**后端处理链（现状）**
```
admin.py:1985 upload_excel_clues
  → load_workbook(io.BytesIO(file), read_only=True)        # E8：示例文件此处崩溃
  → ws = wb.active                                    # E3：只取激活 sheet，多 sheet 丢失
  → header_map 仅识别 5 列                            # 其余列（省份/学历/招生老师/跟进…）丢弃
  → 逐行生成 results（随机 clue_id）                     # 无去重
admin.py:2090 confirm_excel_import
  → 逐条 ApiClue(随机clue_id, name, phone_decrypted, weixin_manual, ...)  # E4/E5：字段丢失+重复
```

**数据链（应落地的目标）**
```
文件(多sheet) → 按列名指纹识别工作表类型
  → 教育在线/抖音代运营/朋友圈广告/直播数据分配表 → 统一线索维度 → api_clues(补全所有业务字段)
  → 直播排班表 → 独立排班表(现有 SchedulePlan/ScheduleSlot 或新建)
  → 唯一码 = (联系方式, 微信) 组合 → 查重 → 重复则跳过并记录 → 管理员查看
```

## 4. 根因候选列表

- **候选 A**：openpyxl 版本 bug 导致示例 xlsx 完全无法解析（`Fill()` 崩溃）—— 直接阻断导入。
- **候选 B**：`excel-upload` 只读 `wb.active` 单 sheet，多 sheet/多类型工作表机制缺失。
- **候选 C**：列名识别只匹配 5 个固定中文列，无法"按列名指纹自动区分"五种工作表类型，且业务维度字段未映射。
- **候选 D**：`excel-confirm` 用随机 `clue_id`、无唯一约束、不查重 → 无法"杜绝重复添加"，不满足需求第 3 条。
- **候选 E**：无"联系方式+微信组合唯一码"模型，无重复跳过提示/管理员查看能力。
- **候选 F**：前端不支持多 sheet 选择/预览、不传类型上下文、无重复结果展示。

## 5. 候选根因逐一验证与排除

- **A 验证**：实测两个示例 xlsx 在 `load_workbook` 均抛 `TypeError: Fill() takes no arguments`（E8）。这是**真实现有阻断**，但它是"示例文件格式兼容性"问题，且只影响这两个文件；用 `read_only`+跳过样式可绕过。→ **是直接阻断因素（表层），非架构根因**，必须修但非唯一根因。
- **B 验证**：`admin.py:2000 ws = wb.active`，代码仅处理一个 sheet。多 sheet 子表（如直播表里 3 个 sheet）除激活外全部被忽略。→ **确证为根因之一**（功能缺失）。
- **C 验证**：`header_map` 仅 5 键（admin.py:2008-2013），示例表有 20+ 业务列，全部未映射；无任何"按列名识别工作表类型"的逻辑。→ **确证为根因之一**（架构缺失）。
- **D 验证**：`excel-confirm` 生成随机 `clue_id`（admin.py:2107），`api_clues` 唯一键是 `clue_id`（models.py:321），随机值永不冲突 → 必然重复入库。→ **确证为根因之一**（去重机制缺失）。
- **E 验证**：`ApiClue` 无 `(phone, weixin)` 组合唯一索引（models.py:317-381），无重复记录表/标记。→ **确证为根因之一**（数据模型缺失），是 D 的深层根因。
- **F 验证**：前端 `previewExcel/confirmExcelImport` 直接透传、无类型识别 UI、无重复反馈（leads.html:363-400）。→ **确证为根因之一**（交互缺失），是 B/C/E 在前端的镜像。

**排除"完全没做"的误判**：E1/E2 证明导入功能"部分已实现且路由连通"，所以根因不是"无导入功能"，而是"已实现的部分（极简单 sheet 线索导入）与需求（多 sheet 多类型 + 组合唯一码去重 + 管理员可见）在架构、数据模型、字段映射、去重、前端五个层面全部不匹配"。

## 6. 最终根因结论

**根本原因（多维并列，全部确证）：**
1. **架构层**：导入模块被设计为"单文件单 sheet 极简线索导入"，而非需求要求的"按列名指纹自动区分多工作表类型"的通用导入框架（B+C）。
2. **数据模型层**：`api_clues` 缺少「联系方式+微信」组合唯一约束与重复标记/记录机制，导致无法"杜绝重复添加"并"提示重复跳过、管理员查看"（D+E）。
3. **字段映射层**：列名识别仅 5 个硬编码中文列，示例表 20+ 业务维度（省份/学历/招生老师/跟进/状态标签/留资时间/来源/投放账户等）全部未映射、未落库（C+E4）。
4. **兼容性层**：openpyxl 样式解析 bug 使示例文件无法被 `load_workbook` 读取，直接阻断解析入口（A）。
5. **交互层**：前端无多 sheet 选择、无类型识别、无重复结果反馈（F）。

**为什么不是其他候选**：并非"路由没连通"（E1/E2 证明连通）；并非"数据库不支持"（已有 api_clues/api_clues 可承载，缺的是约束与映射）；并非" merely 缺一个去重函数"（根因是组合唯一码模型与查重流程整体缺失，单加函数不够）。

## 7. 业务影响分析

- **用户视角**：管理员收到合并的"多维+直播"xlsx，点导入 → 要么崩溃（A）、要么只导入一个 sheet 的极少字段（B/C）、要么重复线索无限增长且无法识别（D/E）、且不知道哪些被跳过了（F）。**业务完整性 0% 满足**，五类工作表数据全部丢失或错乱，招生跟进、学历、状态标签等核心维度无法进入系统。
- **架构视角**：现有实现不可扩展，每新增一种工作表类型都需改硬编码，违反 DRY/开闭原则。
- **性能视角**：单次全量导入无批处理/无事务边界，大文件逐行 `db.add` 无分批 commit，可能长事务锁表（单用户系统影响有限，但需避免）。

## 8. 逐步排查计划（从前端→路由→服务→数据层）

| 步 | 目标 | 检查对象 | 具体方法 | 预期结果 | 异常分支 | 判定标准 |
|---|------|----------|----------|----------|----------|----------|
| P1 | 确认文件可解析 | `server/routers/admin.py:1999` | 用示例两文件跑 `load_workbook`；若崩，改用 `read_only=True`+捕获样式，或换 `pandas.read_excel(engine='calamine')`/底层 zip 解析 | 能读出全部 sheet 与表头 | 仍崩 → 升级/降级 openpyxl 或换引擎 | 两示例文件均能在测试脚本中打印 sheet 名+首行列名 |
| P2 | 确认多 sheet 遍历 | `admin.py:2000` | 改 `ws=wb.active` 为遍历 `wb.sheetnames` 逐个 `wb[name]` | 所有 sheet 均被处理 | 某 sheet 空 → 跳过 | 示例"直播"文件 3 个 sheet、"多维"文件 3 个 sheet 全部进入处理流 |
| P3 | 确认工作表类型识别 | 新建 `server/services/excel_import_service.py` | 定义每类表的"列名指纹"（如含「直播人员」→直播数据分配表；含「报考专业」→教育在线；含「营销消耗+直播时间」→直播排班表；含「日消耗」→朋友圈广告；含「留资时间+招生老师+数据状态与标签」且无直播人员→抖音代运营），按指纹匹配 | 三类表正确归类 | 指纹冲突 → 加权重评分 | 示例 6 个 sheet 全部识别正确 |
| P4 | 确认字段映射 | `admin.py:2008-2013` 与 `models.py:317-381` | 建立每类表 → `ApiClue` 字段的映射表（电话号码→phone_decrypted；微信→weixin_manual；省份/城市→auto_province_name/city_name；学历→clue_intention；招生老师→raw/ext；状态标签→effective_state；跟进→raw_data；留资时间→create_time_detail/lead_time；来源→clue_source 细分；投放账户→advertiser_name 等） | 业务维度全落库 | 缺列 → 留空并记录 | 示例首行数据各业务字段非空值能写入对应列 |
| P5 | 确认组合唯一码去重 | `models.py:317-381` | 新增唯一约束/查重键 `(phone_decrypted, weixin_manual)` 或计算 `unique_key=联系方式+'\|\|'+微信`；导入前先查 `api_clues` 是否已存在该键 | 重复行被识别 | 键为空（无联系方式且无微信）→ 用姓名兜底或标记待审 | 同一联系方式+微信第二次导入返回"重复跳过" |
| P6 | 确认重复提示+管理员可见 | `admin.py:2090` 返回结构 + `leads.html` 展示 | `excel-confirm` 返回 `{imported:N, skipped:M, skipped_list:[...]}`；前端弹窗展示跳过明细；管理员后台线索列表可筛选 `source=excel` 并标"重复跳过" | 管理员能看到跳过清单 | 前端不展示 → 加模态框 | 导入后弹窗显示"成功N条，跳过M条（重复）"且列表可查 |
| P7 | 确认排班表独立处理 | 示例"直播排班表"sheet | 识别为排班类型后，不写 api_clues，而写现有 `SchedulePlan/ScheduleSlot` 或新建映射；直播数据分配表的"每月一个表"通过文件名/表内月份字段区分 | 排班数据进入排班模块 | 字段对不上 → 做最小映射 | 排班 sheet 数据进入排班查询可见 |
| P8 | 确认 CSV 支持 | `excel-upload` 入口 | 依扩展名分支：`*.csv` 用 `csv` 模块按表头解析（首行列名），复用同一指纹识别与映射 | CSV 与 xlsx 走同一逻辑 | 编码异常(GBK/UTF-8) → 尝试多编码 | 示例若转 CSV 可导入 |
| P9 | 确认前端多 sheet/类型 | `leads.html:200-246,354-400` | 改为：上传后后端返回"按 sheet 分组 + 类型识别 + 预览 + 重复预检"；前端逐 sheet 展示类型与可导入/将跳过数量 | 管理员导入前即知每 sheet 类型与重复数 | 后端未返回分组 → 改造返回结构 | 导入弹窗显示每个 sheet 的名称