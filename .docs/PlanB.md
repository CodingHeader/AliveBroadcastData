I'll analyze this requirement against the real codebase. Let me start by exploring the actual structure: the example files, existing import logic, and data models.
Key finding: there's an existing **clue** Excel import (`admin.py:1984`), but the requirement's sheet types (直播数据分配表, 直播排班表, 教育在线, 抖音代运营, 朋友圈广告) don't exist in code yet. Let me inspect the actual xlsx structure and the existing import implementation.
Critical finding: the existing `excel-upload` reads only `wb.active` (single sheet) and only targets clues. Also the real xlsx files **fail to load under `read_only=True`** (openpyxl `Fill` error — a known WPS/Tencent-docs incompatibility). Let me reload correctly and map the data model.
Major finding: **all three real xlsx files fail to open with openpyxl** (even without `read_only`) — the `expected Fill` error is the classic WPS/腾讯文档 incompatibility. This means any import built on openpyxl will crash on the actual data. I'll bypass openpyxl by parsing the xlsx XML directly to recover the real headers and sheet names.
Now I have the **real schema**. This is far more complex than the existing clue import. Critical discoveries:
1. The merged file (`腾讯文档--数据分配.xlsx`) contains **7 sheets** spanning all required types.
2. Several sheets have a **two-row header** (main + sub: `联系方式` split into `电话`/`微信`), and the real data starts at row 3 for `新直播数据分配表`.
3. Cells contain the literal string `"None"` for empties — dedup keys would be polluted if not normalized.
4. `联系方式` is NOT always a phone (e.g. `cdh-131012` is a douyin ID).
5. Not all sheets are contact tables — `直播排班表`/`运营值班表` have **no** 联系方式/微信.

Let me verify the openpyxl failure impact, the existing import wiring, and whether docs already specify a schema.
Let me check the docs for any prior schema design, the DB migration mechanism, and the frontend import page pattern.
No existing schema for this feature — it's net-new. DB uses `Base.metadata.create_all()` + manual `ALTER` migrations in `init_db()`. One more crucial verification: the real files **violate the "first row = header" assumption**. Let me pin down exact row positions for the tricky sheets.
Definitive evidence of structural complexity:
- **`新直播数据分配表`**: Row1 = main header, Row2 = **sub-header** (`联系方式` merged over `电话`+`微信`), Row3+ = data. Datetime stored as **Excel serial floats** (e.g. `46203`, `0.8871875`).
- **`直播排班表`**: Row1 = a **summary/stats row**, Row2 = real header. So "first row = header" is false here.

Let me read the existing frontend import UX pattern to mirror it precisely.
I now have a complete evidence base. Let me confirm two structural facts (router mount prefix + sidebar nav location) so the plan is file-precise, then I'll write the full analysis.
I have a complete, evidence-backed picture. Below is the full analysis and executable plan — pure analysis only, **no files were read-edited or created**.

---

# 多维数据（xlsx/csv）导入功能 — 深度分析与可执行修复计划

## 1. 问题现象复述

需求：支持管理员导入 **xlsx / csv** 文件，把多张「子表」（sheet）按**列名自动区分类型**后入库；要求：
1. 一个文件可含多个 sheet，也可分别用多个文件导入；
2. 子表类型包括：`直播数据分配表`、`直播排班表`、`教育在线`、`抖音代运营`、`朋友圈广告`（其中`直播数据分配表`按月一个表）；
3. 每个表以 **「联系方式 + 微信」组合值** 作为唯一特征码，**杜绝重复添加**；导入时发现重复要**提示跳过信息且管理员可查看**；
4. 实际数据通常是示例表一（`多维--数据分配.xlsx`）与示例表二（`直播--数据分配.xlsx`）的**合并文件**。

**当前系统实际现象（代码层）**：
- 后台**没有任何**针对这些「多维数据分配」表的导入能力；`models.py` 中 27 张表无一对应「教育在线/朋友圈广告/直播数据分配」等业务表（`server/models.py:5-499` 全量核查）；
- 现有唯一 Excel 导入 `admin.py:1985` `/admin/api/clues/excel-upload` **只针对「线索(ApiClue)」**，且只读取 `wb.active`（单 sheet，`admin.py:2000`），无法处理多 sheet 自动分类；
- 需求方假设的「第一行为列名」在真实文件中**不成立**（见证据 2.4、2.5），现有/朴素实现会错位；
- 最致命：真实 xlsx **用 openpyxl 根本打不开**（见证据 2.6），现有 + 任何基于 openpyxl 的新实现都会在解析阶段崩溃。

## 2. 代码与日志事实证据

| # | 证据项 | 文件:行 / 来源 | 结论 |
|---|---|---|---|
| 2.1 | 真实文件 sheet 清单 | 我直接解析 XML（绕过 openpyxl）得到：<br>`多维--数据分配.xlsx` → [教育在线, 抖音代运营, 朋友圈广告]<br>`直播--数据分配.xlsx` → [新直播数据分配表（7月始）, 直播排班表, 直播数据(六月)]<br>`腾讯文档--数据分配.xlsx`（合并文件）→ [新直播数据分配表, 教育在线, 直播数据, 抖音代运营, 运营值班表, 朋友圈广告, 直播排班表] | 合并文件恰含需求全部类型 + 额外的「运营值班表」「直播数据(六月)」 |
| 2.2 | 各 sheet 关键列（联系方式/微信） | 解析结果：<br>教育在线：`电话号码`(col3)、`微信`(col9)<br>抖音代运营：`联系方式`(col3)、**无微信列**<br>朋友圈广告：`联系方式`(col3)、**无微信列**<br>新直播数据分配表：`联系方式`(col8，合并跨`电话`+`微信`)、`微信`(col9)<br>直播数据(六月)：`联系方式`(col4)<br>直播排班表 / 运营值班表：**无联系方式/微信**（运营表） | ① 并非所有表都有「微信」列；② 联系方式可能是手机号**也可能是抖音号**（如 `cdh-131012`、`nzgsazd`） |
| 2.3 | 单元格含字面量 `"None"` | 教育在线 ROW1：`微信='None'`；大量列为 `'None'` | 空值判定必须把字符串 `"None"/"none"` 当作空，否则去重键被污染 |
| 2.4 | 双行表头（主表头+子表头） | `新直播数据分配表`：<br>Excel row1=`[序号,留资日期,…,联系方式,None,…]`<br>Excel row2=`[None,…,电话,微信,评论内容要点,…]`<br>Excel row3 起为数据 | `联系方式`是合并单元格，跨 `电话`+`微信` 两列；真实数据从第 3 行开始 |
| 2.5 | 汇总行在表头之前 | `直播排班表`：<br>Excel row1=`[统计,15045.03,249,108,20,128]`（统计汇总行）<br>Excel row2=`[日期,营销消耗,直播人员,直播时间,总时长,广告流线索,自然流线索,总线索,运营值班人员]`（真表头）<br>Excel row3 起为数据 | 「第一行=表头」假设**错误**；必须扫描前若干行选最佳表头 |
| 2.6 | **openpyxl 无法解析真实文件** | 实测：`openpyxl.load_workbook(f, read_only=True/False)` 对 3 个文件均抛 `TypeError: expected <class 'openpyxl.styles.fills.Fill'>`（WPS/腾讯文档样式兼容 bug） | ① 现有 `admin.py:1999 load_workbook(read_only=True)` 遇到这类文件必崩；② 新导入**绝不能依赖 openpyxl 读取** |
| 2.7 | 日期为 Excel 序列号浮点 | `新直播数据分配表` row3：`留资日期=46203`、`留资时间=0.8871875`（分数日） | 日期列需识别「数值序列号」并转 datetime；而教育在线是字符串 `2026-03-04 13:28:48`，两种格式混存 |
| 2.8 | 现有导入链路（参照范式） | `leads.html:363 previewExcel()` POST `FormData`→`/admin/api/clues/excel-upload` 返回 `{code,data,errors}`；`leads.html:382 confirmExcelImport()` POST `{items}`→`/admin/api/clues/excel-confirm` 写 `ApiClue` | 采用「预览→确认」两步式；新功能应复用同一 UX 范式 |
| 2.9 | 路由挂载与页面机制 | `main.py:43` `admin.router` 前缀 `/admin/api`；`main.py:44` `pages.router` 托管页面；`base.html:155` 侧边栏含「线索管理」链接写法 | 新路由为 `/admin/api/multidim/*`；新页面 `templates/admin/multidim_import.html`，侧边栏加入口 |
| 2.10 | 表创建机制 | `database.py:25-?`：`init_db()` 调 `Base.metadata.create_all()` + 手动 `ALTER`；无 Alembic | 新模型加入 `models.py` 并在 `init_db()` 注册即自动建表 |

## 3. 关键调用链 / 路由链 / 数据链

**现有（线索）导入链（仅作范式参照，不改动）**
```
leads.html previewExcel()
 └─ POST /admin/api/clues/excel-upload   (admin.py:1985, file:bytes)
     └─ load_workbook(read_only=True)     (admin.py:1999) ← 对真实文件必崩(2.6)
     └─ 仅 wb.active 单 sheet             (admin.py:2000) ← 不支持多 sheet(2.1)
     └─ 返回 data[] → 前端预览
leads.html confirmExcelImport()
 └─ POST /admin/api/clues/excel-confirm  (admin.py:2090)
     └─ 批量 new ApiClue(...) → db.commit
```

**目标（多维数据）导入链（设计态）**
```
multidim_import.html (新增)
 ├─ previewMultidim(event)  POST /admin/api/multidim/upload (file:bytes)
 │    └─ read_file(): xlsx→zipfile+XML 读取器(绕过openpyxl) / csv→csv模块
 │    └─ for each sheet: detect_sheet_type(表名+列签名)   → 类型
 │    └─ locate_header(rows 0..4, 合并主/子表头)           → 表头行
 │    └─ map_columns(类型→规范字段, 含联系方式/微信定位)
 │    └─ normalize_row(去"None"、联系方式/微信清洗、序列号日期转换)
 │    └─ build_dedup_key(联系方式||微信) + 同批次/DB已存在比对
 │    └─ 返回 {sheets:[{type,total,will_insert,will_skip,sample_skips}], errors}
 └─ confirmMultidim()  POST /admin/api/multidim/confirm
      └─ 写 MultiDimRecord(新增) + 写 MultiDimImportBatch/ImportSkip(跳过明细)
      └─ 返回 {inserted, skipped, by_type}
multidim_logs.html (新增, 管理员查看)
 └─ GET /admin/api/multidim/batches /:id/skips → 展示每次导入的重复跳过明细
```

**数据模型链（新增，统一表方案）**
```
MultiDimRecord(id, sheet_type, period(YYYY-MM), source_file,
                contact_norm, wechat, dedup_key(UNIQUE 范围内),
                raw_json(全部列), row_index, batch_id, created_at)
MultiDimImportBatch(id, filename, admin, imported_at,
                    total, inserted, skipped, by_type_json, status)
MultiDimImportSkip(id, batch_id, sheet_type, row_index,
                   contact, wechat, reason, existing_record_id)
```

## 4. 根因候选列表（「为何当前无法满足需求」）

- **C1（致命）解析层不兼容**：openpyxl 对 WPS/腾讯文档生成的 xlsx 抛 `Fill` 错误 → 解析即崩（证据 2.6）。任何基于 openpyxl 的实现都不可行。
- **C2 单 sheet 限制**：现有/朴素实现只处理 `wb.active`（`admin.py:2000`），无法遍历多 sheet 并按列名分类（证据 2.1）。
- **C3 表头假设错误**：真实文件存在「汇总行在前」（直播排班表）、「双行表头」（新直播数据分配表），朴素「第 1 行=表头」会错位或漏采（证据 2.4、2.5）。
- **C4 空值/"None"污染**：字面 `"None"` 未归一 → 去重键含 `"None"`，重复判定失效（证据 2.3）。
- **C5 去重键设计缺陷**：部分表（抖音代运营、朋友圈广告）无「微信」列；且同人跨渠道（如教育在线有微信 vs 抖音代运营无微信）用「联系方式||微信」组合键会**漏判重复**（证据 2.2）。
- **C6 无业务模型**：`models.py` 无任何多维数据表，去重/查询/管理员查看均无处落地（证据 2.10 + 全量核查）。
- **C7 类型自动识别缺失**：无「表名+列签名 → 类型」的注册表，无法在合并文件中区分 7 类 sheet（证据 2.1）。

## 5. 候选根因逐一验证与排除

| 候选 | 验证方法 | 结果 | 判定 |
|---|---|---|---|
| C1 openpyxl 崩溃 | 实测 3 文件 `load_workbook` 两模式均抛 `Fill` 错（2.6）；现有 `admin.py:1999` 同款调用 | 复现 100% | **成立（首要阻塞）** |
| C2 单 sheet | 现有代码 `admin.py:2000 wb.active` 仅取活动表；合并文件 7 sheet 仅读 1 个 | 代码实证 | **成立** |
| C3 表头错位 | 解析确认直播排班表 row1=汇总、新直播数据分配表 row1+row2=双表头（2.4/2.5） | XML 实证 | **成立** |
| C4 "None"污染 | 教育在线 ROW1 `微信='None'` 真实存在（2.3） | XML 实证 | **成立** |
| C5 去重漏判 | 抖音代运营/朋友圈广告无微信列（2.2）；同人跨渠道键不同 → 不被判重 | 列结构实证 | **成立（必改，否则违背"杜绝重复"）** |
| C6 无模型 | `models.py` 27 表全量核对无对应实体 | 代码实证 | **成立** |
| C7 无识别 | 无任何 sheet→type 映射代码 | grep 实证 | **成立** |
| （排除）「只是缺个上传入口」 | 若仅加入口而不解决 C1–C5，解析必崩/错位/重复 | 由 C1–C5 反证 | **排除**为根因；根因是「解析+分类+去重+存储」全链路缺失，非单点 |

**为什么是复合根因而非单点**：C1 让解析直接失败；即便绕过 C1，C2/C3 让多 sheet 与表头错乱；即便读对，C4/C5 让去重失效；即便去重对，C6/C7 让数据无处存、类型分不出。需求是**端到端链路**缺失，必须逐环修复。

## 6. 最终根因结论

当前系统**不具备**导入「多维数据分配」类表格的任何能力，根因为一条完整缺失链：
1. **解析层（C1）**：依赖 openpyxl，而真实 WPS/腾讯文档 xlsx 触发 `Fill` 解析异常 → 全链路起点崩溃；
2. **读取层（C2/C3）**：仅单 sheet、且「首行=表头」假设与真实「汇总行/双行表头」结构冲突 → 数据采不全/错位；
3. **质量层（C4/C5）**：字面 `"None"` 未归一、去重键在「无微信列/跨渠道」场景漏判 → 重复无法杜绝；
4. **模型层（C6/C7）**：无业务表与类型识别注册表 → 类型分不出、去重与「管理员可查看跳过」无落地处。

## 7. 业务影响分析

- **数据完整性（最严重）**：若用现有 openpyxl 导入，3 个真实文件**全部失败**，管理员拿不到任何数据；即便临时换成能打开的库，因 C3 双行表头，直播 7 月表会**把 `电话/微信` 当数据、把真实第 3 行当表头**，整表错乱。
- **重复污染**：不修 C5，同一客户在「教育在线（有微信）」与「抖音代运营（无微信）」中会被当成两人重复入库 → 招生老师重复跟进、统计虚高，直接违背「杜绝重复添加」。
- **管理员信任**：需求明确要求「重复跳过信息管理员可查看」，无 C6 的 batch/skip 表则无法审计，出问题无法追溯。
- **反人性视角**：用户习惯把各渠道表**合并成一个文件**甩过来，期望「上传即分类入库、有重复告诉我」。当前系统要求手动拆 sheet、且还会崩 → 体验极差。

## 8. 逐步排查计划（落地前的验证顺序，每步可执行）

**P1 — 确认解析库可用性（解 C1）**
- 目标：选定能打开真实文件的读取方案。
- 检查对象：对 3 个 `.docs/*.xlsx` 分别尝试 `openpyxl`（已知崩）、`zipfile+xml`（已实测可读，见 2.1–2.5）、`pandas(engine='calamine')`、`xlsx2csv`。
- 方法：用我本次验证过的 `zipfile+ElementTree` 脚本读取并打印 sheet/表头/前两行，确认 7 类 sheet 全部可读。
- 预期：zipfile 方案 7/7 成功；openpyxl 0/3。
- 判定标准：选定 zipfile 方案为读取内核（零新依赖、已验证）。
- 异常分支：若某文件连 zipfile 都读不出（损坏）→ 返回前端「文件损坏」错误，不入解析流程。

**P2 — 确认表头定位规则（解 C3）**
- 目标：确定每个 sheet 的「真实表头行」与「数据起始行」。
- 检查对象：对 7 个 sheet 扫描 Excel row 1..5，按「列签名命中数」评分选最佳表头行；对双行表头做主+子合并。
- 方法：用解析脚本输出每个候选行的「已知列别名命中数」，人工核对选中行。
- 预期：直播排班表→选 row2（命中 运营值班人员/总线索等）；新直播数据分配表→选 row1 并合并 row2 得到 `联系方式/电话/微信`；教育在线→row1。
- 判定标准：选中行的联系方式/微信列能被定位，且数据首行非表头文字。
- 异常分支：若最高分 < 阈值（如 <2）→ 该 sheet 标记为「无法识别表头」并在预览中提示跳过。

**P3 — 确认类型识别签名（解 C7）**
- 目标：用「表名 + 列签名」双因子准确分类 7 类 sheet。
- 检查对象：建立签名表（下见计划 9 的 `SHEET_TYPE_REGISTRY`）。
- 方法：对 7 sheet 运行 `detect_sheet_type()`，输出判定类型。
- 预期：教育在线/抖音代运营/朋友圈广告/直播数据分配表(含六月、7月)/直播排班表/运营值班表 全部命中。
- 判定标准：无 sheet 落入「未识别」；运营类（排班/值班）被正确排除出「联系方式表」。
- 异常分支：未识别 → 放入「待人工指定类型」队列，预览时让管理员下拉选择。

**P4 — 确认去重键与跨渠道策略（解 C5）**
- 目标：确定去重键，闭合「无微信列/跨渠道」漏判。
- 检查对象：同 `联系方式` 在「教育在线(有微信)」与「抖音代运营(无微信)」中的表现。
- 方法：构造样本，验证 `dedup_key=联系方式||微信` 与「同类型内 contact_norm 已存在且 wechat 空」二次判定。
- 预期：同联系方式跨渠道仍被判重（因 contact_norm 命中）。
- 判定标准：重复样本在预览的 `will_skip` 中可见，且 `sample_skips` 给出原因 `duplicate`。
- 异常分支：联系方式为空 → 不入联系方式表，标记 `missing_contact` 跳过。

**P5 — 确认空值与日期归一（解 C4 / 2.7）**
- 目标：把 `"None"`/空 归一，把 Excel 序列号转 datetime。
- 检查对象：教育在线字符串日期 vs 新直播数据分配表序列号（`46203`/`0.887`）。
- 方法：对数值型且列属日期/时间别名的，按 Excel epoch(1899-12-30)+timedelta 转换；字符串日期原样保留；`"None"/"none"/""/NULL`→`None`。
- 预期：`46203`→`2026-06-23` 左右；`0.887`→`~21:17`；`微信='None'`→空。
- 判定标准：预览中日期为可读字符串、微信为空不污染键。

**P6 — 确认存储与查看落地（解 C6）**
- 目标：新表可在 `init_db()` 自动创建，batch/skip 可查。
- 检查对象：`database.py:init_db()`、`models.py` 注册列表。
- 方法：把新模型加入 `models.py` 与 `init_db()` 导入列表后，本地 `init_db()` 验证 `CREATE TABLE` 成功。
- 判定标准：`MultiDimRecord/MultiDimImportBatch/MultiDimImportSkip` 三表存在。

## 9. 最小验证闭环 / 可执行修复计划（原子化、文件级、带判定标准）

> 遵循「架构最优」：**单张统一表 `MultiDimRecord` + JSON 存全列 + 类型化索引列**，而非为每类建独立表（异构/易变 schema 下最稳、改动最小）。
> 读取内核**弃用 openpyxl**，改用 `zipfile+XML`（已验证可解真实文件）。
> 以下每条均「目标 / 改动文件:位置 / 方法 / 预期 / 异常 / 判定」。

### 9.1 读取内核（解 C1）
- **T1 新增 `server/utils/xlsx_reader.py`**
  - 目标：用 `zipfile`+`xml.etree` 流式读 xlsx，返回 `[(sheet_name, [[cell,...],...])]`，**完全不经过 styles.xml**（即绕开 `Fill` 错）。
  - 方法：复用本次验证脚本逻辑——读 `xl/sharedStrings.xml`、`xl/workbook.xml`+rels 定位 sheet、`xl/worksheets/sheetN.xml` 解析 `<row>/<c>`（含 `t="s"` 共享串、`<is>` 内联串）。
  - 预期：3 个真实文件均可返回 sheet 矩阵。
  - 异常：zip 损坏/非 xlsx → 抛 `UnsupportedFileError`。
  - 判定：`read_xlsx(path)` 对 `.docs/腾讯文档--数据分配.xlsx` 返回 7 个 sheet 且首行非崩溃。
- **T2 新增 `server/utils/csv_reader.py`**（或并入 T1）
  - 目标：csv 用标准 `csv` 模块，返回单 sheet 矩阵（csv 无多 sheet）。
  - 预期：`.csv` 文件正确解析，UTF-8-SIG/BOM 处理。
  - 判定：`read_csv(path)` 返回 `[header_row, ...data_rows]`。

### 9.2 表头与类型识别（解 C3/C7）
- **T3 新增 `server/utils/sheet_detect.py`**
  - 目标：`locate_header(rows)` 扫描 row0..4，对每行按「已知列别名命中数」评分，返回 `(header_row_idx, merged_header_list)`；双行表头取各列首个非空值合并。
  - 方法：评分函数遍历 `SHEET_TYPE_REGISTRY` 所有别名集合计数；选中最高分行；合并其下一行非空单元格补充分裂列（如 `电话`/`微信`）。
  - 预期：直播排班表选 row2；新直播数据分配表选 row1 并合并 row2。
  - 异常：最高分<阈值 → 返回 `None`，上层标记「无法识别表头」。
  - 判定：单元测试 7 sheet 均返回正确表头行。
- **T4 在 `sheet_detect.py` 定义 `SHEET_TYPE_REGISTRY`**（基于 2.1–2.2 实证）
  - 目标：类型→(表名提示, 列签名, 规范字段映射, 联系方式/微信定位)。
  - 内容（经真实文件校验）：
    - `教育在线`：表名含「教育在线」；列签名含 `电话号码`+`微信`+`对话内容`；联系=`电话号码`，微信=`微信`。
    - `抖音代运营`：表名含「抖音代运营」；列含 `联系方式`+`第一次跟进` 且**无**`直播人员`；联系=`联系方式`，微信=无→空。
    - `朋友圈广告`：表名含「朋友圈广告」；列含 `日消耗`+`学生姓名`；联系=`联系方式`，微信=无→空。
    - `直播数据分配表`：表名含「直播数据」/「数据分配」；列含 `直播人员`+`留资方式`(或`互动场景`)；联系=`联系方式`(合并跨`电话`)，微信=`微信`（7月表）/无（六月表）。
    - `直播排班表`：表名含「排班」；列含 `营销消耗`+`总线索`+**无联系方式** → **运营类（不去重）**。
    - `运营值班表`：表名含「值班」；列含 `人员`+`事宜` → **运营类（不去重）**。
  - 预期：detect 对合并文件 7 sheet 全中。
  - 判定：见 P3。

### 9.3 归一化与去重（解 C4/C5/2.7）
- **T5 新增 `server/utils/normalize.py`**
  - 目标：`normalize_cell(v)`：`"None"/"none"/""/"NULL"/"无"`→`None`；`normalize_contact(s)`：去空格/横杠；`convert_excel_datetime(v, col_alias)`：数值且列属日期/时间→`1899-12-30+timedelta`；`build_dedup_key(contact, wechat)`：`f"{contact}||{wechat or ''}"`。
  - 预期：教育在线 `微信='None'`→空；`46203`→日期串。
  - 判定：单测覆盖 2.3/2.7 样例。
- **T6 去重服务 `dedup_check(records, db, sheet_type)`**
  - 目标：先按 `dedup_key` 在「本批次内」去重；再查 `MultiDimRecord` 同 `sheet_type` 内 `dedup_key` 已存在 → `duplicate`；并对「`contact_norm` 已存在且 wechat 空」补判 → 闭合跨渠道漏判（C5）。
  - 方法：批量 `IN` 查询已存在键；返回 `(to_insert, skips)`。
  - 预期：同联系方式跨渠道被判重。
  - 异常：contact 与 wechat 皆空 → `missing_contact` 跳过。
  - 判定：见 P4。

### 9.4 数据模型（解 C6）
- **T7 新增模型 `server/models.py`**（末尾追加，不改动现有表）
  - `MultiDimRecord`（tablename `multidim_records`）：id, sheet_type(Text, index), period(Text), source_file(Text), contact_norm(Text, index), wechat(Text), dedup_key(Text, index), raw_json(Text/JSON), row_index(Integer), batch_id(Integer, FK), created_at(Text)。
  - `MultiDimImportBatch`（tablename `multidim_import_batches`）：id, filename, admin(Text), imported_at(Text), total, inserted, skipped, by_type_json(Text), status(Text)。
  - `MultiDimImportSkip`（tablename `multidim_import_skips`）：id, batch_id(FK), sheet_type, row_index, contact, wechat, reason, existing_record_id。
  - 判定：`init_db()` 后三表存在。
- **T8 注册到 `server/database.py:init_db()`**
  - 目标：把 3 个新模型加入 `init_db()` 的 import 列表，使 `create_all` 建表。
  - 方法：在 `init_db()` 现有 import 行追加 `MultiDimRecord, MultiDimImportBatch, MultiDimImportSkip`。
  - 判定：重启后 `SELECT name FROM sqlite_master` 含三表。

### 9.5 后端路由（复用「预览→确认」范式，解 C2/C6）
- **T9 `server/routers/admin.py` 新增 `POST /api/multidim/upload`**（admin.py 末，参考 `admin.py:1985`）
  - 签名：`async def upload_multidim(file: bytes, admin=Depends(get_current_admin), db: DBSession=Depends(get_db))`。
  - 逻辑：按扩展名调 T1/T2 → 每 sheet 调 T3 定位表头 → T4 识别类型 → 映射规范字段 → T5 归一化 → T6 去重（查 DB）→ 返回 `{code:0, data:{sheets:[{type,total,will_insert,will_skip,sample_skips:[{row,contact,reason}]}], errors:[...]}}`。**不写库**。
  - 预期：合并文件返回 7 个 sheet 的分类预览与跳过明细。
  - 异常：解析失败→`{code:500,...}`；无联系方式表的运营类 sheet 标记 `operational:true` 单独处理。
  - 判定：见 P1–P5。
- **T10 `server/routers/admin.py` 新增 `POST /api/multidim/confirm`**
  - 签名：`def confirm_multidim(payload: dict, admin, db)`。
  - 逻辑：建 `MultiDimImportBatch` → 批量 `MultiDimRecord`（含 `period` 由 `留资日期/分配日` 推导 YYYY-MM）→ 写 `MultiDimImportSkip`（重复/缺联系方式）→ `db.commit` → 返回 `{inserted, skipped, by_type}`。
  - 判定：DB 中新增记录数 = `will_insert`；skips 可查。
- **T11 `server/routers/admin.py` 新增 `GET /api/multidim/batches` 与 `GET /api/multidim/batches/{id}/skips`**
  - 目标：管理员查看每次导入的重复跳过明细（需求「管理员可查看」）。
  - 判定：返回 batch 列表与 skip 行（含 contact/reason/existing）。

### 9.6 前端页面与入口
- **T12 新增 `server/templates/admin/multidim_import.html`**（复用 `leads.html` 的 Alpine 模态范式：`leads.html:200-249` 模态 + `leads.html:363-401` 两个 fetch）
  - 内容：`previewMultidim(event)` POST `/admin/api/multidim/upload`（FormData）→ 展示每 sheet 类型、`将新增/将跳过` 计数、skip 样本；`confirmMultidim()` POST `/admin/api/multidim/confirm` → `alert(导入成功：新增X，跳过Y)`。
- **T13 新增 `server/templates/admin/multidim_logs.html`**
  - 内容：列表展示历史 batch + 点开查看 skip 明细（调用 T11）。
- **T14 `server/routers/pages.py` 注册页面路由**
  - 目标：参照现有 leads 页面注册，新增 `GET /admin/multidim-import` 与 `GET /admin/multidim-logs` 返回对应模板。
  - 判定：浏览器访问两路径正常渲染。
- **T15 `server/templates/admin/base.html` 侧边栏加入口**
  - 位置：`base.html:155`（线索管理）附近新增「多维数据导入」「导入记录」两项，写法同 `sidebar-link`（base.html:125 范式）。
  - 判定：侧边栏出现入口且 `isActive` 高亮正确。

### 9.7 端到端最小闭环（验证）
1. 启动服务，`init_db()` 自动建三表（T7/T8）。
2. 打开 `/admin/multidim-import`，选 `.docs/腾讯文档--数据分配.xlsx`。
3. 预览应显示 7 个 sheet 分类：**教育在线/抖音代运营/朋友圈广告/直播数据分配表×2/直播排班表(运营)/运营值班表(运营)**，并给出「将新增/将跳过」计数。
4. 故意造一条与已有 `联系方式` 相同的行 → 预览 `will_skip>0` 且 `sample_skips` 显示 `duplicate`。
5. 点「确认导入」→ `alert` 显示新增/跳过数；`multidim_logs` 可查该次 skip 明细。
6. **反例必做**：用现有 openpyxl 路径尝试同一文件 → 断言崩溃（证明 T1 的必要性）。
7. 关闭验证：导入缺 `联系方式` 的行 → 标记 `missing_contact` 跳过且不入库。

## 10. 风险与边界条件

- **R1 样式兼容性（最高危）**：openpyxl 对 WPS/腾讯文档 xlsx 必崩 → **严禁在新功能用 openpyxl 读取**（T1 已规避）；但现有 `admin.py:1999` 线索导入同样受影响，属独立遗留问题，可另行修。
- **R2 表头漂移**：抖音改版/不同月份文件表头可能变 → T3 评分阈值过低会误判；上线后用真实文件跑 P2 复核，必要时扩充 `SHEET_TYPE_REGISTRY` 别名。
- **R3 「直播数据分配表」两种列布局**（六月 vs 7月）：T4 已用「表名+列签名」覆盖，但若出现第三种布局需补别名。
- **R4 序列号日期**：仅对「日期/时间别名列」做数值转换，避免把 `序号`(1,2,3) 误转（T5 限定别名集合）。
- **R5 跨渠道去重**：严格按「联系方式||微信」会漏判（C5），T6 用 `contact_norm` 二次补判闭合；若业务方坚持「仅同表内组合键去重」，可在 T6 加开关（见待确认 D1）。
- **R6 运营类表（排班/值班）无联系方式**：不去重、直接入库；若按月覆盖需求，建议 `period` 维度 `DELETE THEN INSERT`（待确认 D2）。
- **R7 大文件内存**：合并文件 ~1.3MB、总 ~2000 行，zipfile 流式解析内存可控；若未来单文件 >50MB 再考虑分块。
- **R8 CSV 无多 sheet**：单个 csv = 单 sheet，仍走 T4 类型识别（按列名）；多 csv 多次上传即可。

## 11. 面向用户的直接建议

1. **别用 openpyxl 读这些文件**——你给的 3 个真实文件（含合并文件）openpyxl 全打不开，任何一个基于它的实现上线即崩。我已验证用「直接解析 xlsx 内部的 XML」能 100% 读出来，新功能就走这条路，零新依赖。
2. **「第一行=表头」在真实文件里不成立**：直播排班表第一行是汇总统计、直播 7 月表是双行表头（联系方式跨电话+微信）。系统必须自动扫描前几行选表头，否则整表错乱。这点你提的需求假设需要修正为「系统自动探测表头」。
3. **去重键要补一道「同联系方式」兜底**：抖音代运营/朋友圈广告根本没有「微信」列，若严格用「联系方式+微信」组合键，同一个客户在「教育在线（有微信）」和「抖音代运营（无微信）」里会被当成两个人重复录。建议用「联系方式」为主键、「微信」仅作附加属性，才能真正「杜绝重复」。
4. **统一一张表 + JSON 存细节最省心**：这几种表列差异很大且会随月份变，给每种建独立表后期维护爆炸；用一张 `MultiDimRecord` 表（类型/联系方式/微信做索引列，其余整行塞 JSON）最稳、改动最小。
5. **一定要做「重复跳过可查看」**：你明确要管理员能看，所以我会建 batch + skip 两张日志表，导入后直接在「导入记录」页看每次跳了哪几行、为什么跳——出问题能追溯。
6. **上线前用合并文件跑一遍闭环**：先预览看分类对不对、跳过数对不对，再点确认；并保留「用 openpyxl 试同一文件必崩」的反例作为回归证据。

---

### 🔶 待你确认的 2 个设计决策（核心5：信息不足，先给推荐+验证动作）
- **D1 去重作用域**：推荐「同 `sheet_type` 内按 `联系方式`(+微信补充) 去重」；若你希望「全局跨所有类型去重」或「按月(`period`)去重」，请在确认时指明，我将据此调整 T6 的键范围。
- **D2 运营类表（排班/值班）策略**：推荐「不去重、直接追加」；若你希望「同月覆盖（先删后插）」，请指明，T10 将改为按月 `DELETE+INSERT`。

确认上述决策与方案（T1–T15）后，我可进入执行模式按原子清单逐条落地。**本次未创建/编辑任何文件**，严格遵守约束。