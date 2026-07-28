完整分析与可执行修复计划

  ---
  一、问题现象复述

  用户诉求：系统当前只支持"线索（Lead）"类型的单一数据导入，无法处理多维度的业务数据。实际业务中，运营人员收到的是包含多  个工作表（Sheet）的合并Excel文件，每个Sheet对应不同的业务数据——直播数据分配表、直播排班表、教育在线招生数据、抖音代运
  营数据、朋友圈广告数据等。导入时需根据列名自动识别表类型，按"联系方式+微信"组合去重，重复数据需提示并记录。现有Excel导  入路由仅处理线索类型数据，无法识别新表结构。

  当前系统的实际行为（现象）：
  1. 前端 admin/leads.html 行29：<input type="file" accept=".xlsx,.xls" @change="handleExcelUpload($event)"> —
  只能通过线索管理页面上传
  2. 路由 POST /admin/api/clues/excel-upload（admin.py 第1985行）— 固定调用 wb.active（只读第一个活动Sheet）
  3. 路由 POST /admin/api/clues/excel-confirm（admin.py 第2090行）— 只创建 ApiClue 记录，无去重逻辑
  4. 数据库只有 Lead / ApiClue 两个线索表，无任何教育、代运营、朋友圈广告对应的数据表
  5. confirm_excel_import 循环逐条插入，不检查任何唯一约束

  ---
  二、代码与日志事实证据

  2.1 现有Excel导入链路（完整调用链）

  admin/leads.html:29       <input type="file" accept=".xlsx,.xls" @change="handleExcelUpload">
      ↓ handleExcelUpload() 预览弹窗
  admin/leads.html:363      previewExcel() → POST /admin/api/clues/excel-upload (FormData)
      ↓ admin.py:1985-2087   upload_excel_clues()
      ↓ openpyxl.load_workbook(io.BytesIO(file), read_only=True)
      ↓ wb.active              ← 只取第一个活动Sheet
      ↓ 解析固定列映射：手机号/姓名/微信号/私信时间/备注
      ↓ 返回预览数据 [{clue_id, name, phone, weixin, message_time, session_id, notes}]
      ↓ confirmExcelImport() → POST /admin/api/clues/excel-confirm (JSON)
      ↓ admin.py:2090-2127   confirm_excel_import()
      ↓ 循环逐条创建 ApiClue(clue_source="excel")
      ↓ db.add(); db.commit()  ← 无任何去重检查

  2.2 数据模型现状（models.py 完整模型清单）

  ┌───────────────────┬─────────┬───────────────┬────────────────────────────────┐
  │       表名        │  行号   │     用途      │      有无对应示例表Sheet       │
  ├───────────────────┼─────────┼───────────────┼────────────────────────────────┤
  │ sessions          │ 5-24    │ 直播场次      │ 直播数据分配表（间接关联）     │
  ├───────────────────┼─────────┼───────────────┼────────────────────────────────┤
  │ session_metrics   │ 26-78   │ 场次指标      │ 无直接对应                     │
  ├───────────────────┼─────────┼───────────────┼────────────────────────────────┤
  │ leads             │ 80-102  │ 油猴脚本线索  │ 直播数据分配表（部分字段映射） │
  ├───────────────────┼─────────┼───────────────┼────────────────────────────────┤
  │ api_clues         │ 317-384 │ 统一线索主表  │ 直播数据分配表（部分字段映射） │
  ├───────────────────┼─────────┼───────────────┼────────────────────────────────┤
  │ comments          │ 104-116 │ 评论          │ 无直接对应                     │
  ├───────────────────┼─────────┼───────────────┼────────────────────────────────┤
  │ anchors           │ 158-167 │ 主播          │ 直播人员                       │
  ├───────────────────┼─────────┼───────────────┼────────────────────────────────┤
  │ session_anchors   │ 169-180 │ 场次-主播关联 │ 直播人员                       │
  ├───────────────────┼─────────┼───────────────┼────────────────────────────────┤
  │ schedule_plans    │ 208-219 │ 排班方案      │ 直播排班表                     │
  ├───────────────────┼─────────┼───────────────┼────────────────────────────────┤
  │ schedule_slots    │ 224-234 │ 排班时段      │ 直播排班表                     │
  ├───────────────────┼─────────┼───────────────┼────────────────────────────────┤
  │ schedule_bindings │ 236-245 │ 排班日绑定    │ 直播排班表                     │
  ├───────────────────┼─────────┼───────────────┼────────────────────────────────┤
  │ ad_accounts       │ 261-269 │ 直播账户      │ 投放账户                       │
  ├───────────────────┼─────────┼───────────────┼────────────────────────────────┤
  │ ad_plans          │ 283-298 │ 投流计划      │ 部分对应                       │
  ├───────────────────┼─────────┼───────────────┼────────────────────────────────┤
  │ ad_plan_spends    │ 301-314 │ 投流花费      │ 部分对应                       │
  ├───────────────────┼─────────┼───────────────┼────────────────────────────────┤
  │ recruit_teams     │ 450-466 │ 招生团队      │ 招生老师                       │
  ├───────────────────┼─────────┼───────────────┼────────────────────────────────┤
  │ recruit_employees │ 469-481 │ 招生员工      │ 招生老师                       │
  ├───────────────────┼─────────┼───────────────┼────────────────────────────────┤
  │ clue_assignments  │ 484-501 │ 线索分配      │ 无直接对应                     │
  ├───────────────────┼─────────┼───────────────┼────────────────────────────────┤
  │ dashboard_tabs    │ 423-438 │ 看板Tab       │ 无                             │
  ├───────────────────┼─────────┼───────────────┼────────────────────────────────┤
  │ education_records │ 不存在  │ —             │ 教育在线Sheet                  │
  ├───────────────────┼─────────┼───────────────┼────────────────────────────────┤
  │ douyin_campaigns  │ 不存在  │ —             │ 抖音代运营Sheet                │
  ├───────────────────┼─────────┼───────────────┼────────────────────────────────┤
  │ moment_ads        │ 不存在  │ —             │ 朋友圈广告Sheet                │
  └───────────────────┴─────────┴───────────────┴────────────────────────────────┘

  2.3 示例文件Sheet结构（已验证）

  多维--数据分配.xlsx（3个Sheet）：
  - Sheet "教育在线"：1197行，24列（A-X）
    - 列A: 来源, B: 姓名, C: 电话号码, D: 目前学历, E: 报考省份, F: 报考学校, G: 报考专业, H: 报考层次
    - I: 微信, J: 所在省份, K: 所在城市, L: 所在区县, M: 数据替换, N: 时间, O: 备注, P: 对话内容
    - Q: 分配日期(Excel序列号), R: 招生老师, S: 数据状态与标签, T: 提升形式, U: 咨询反馈
    - V/W/X: 一次跟进/二次跟进/三次跟进
  - Sheet "抖音代运营"：201行，9列 — 分配日, 留资时间, 联系方式, 招生老师, 数据状态与标签, 提升形式, 咨询反馈,
  第一次跟进, 第二次跟进
  - Sheet "朋友圈广告"：206行，8列 — 分配日, 日消耗, 联系方式, 学生姓名, 招生老师, 客户简单信息, 咨询反馈, 备注

  直播--数据分配.xlsx（3个Sheet）：
  - Sheet "新直播数据分配表（7月始）"：399行，23列（A-W，两行表头）
    - 电话(H), 微信(I), 评论内容要点(J), 私信内容要点(K), 所在城市(L), 招生老师(M), 数据状态与标签(N)
    - 用户昵称(S), 留资路径(T), 投放账户(U), 单元名称(V), 单元ID(W)
    - 留资日期为Excel序列号（46203 = 2026-07-01），留资时间为小数（0.887 = 21:17）
  - Sheet "直播排班表"：106行 — 日期, 营销消耗, 直播人员, 直播时间, 总时长(h), 广告流线索, 自然流线索, 总线索,
  运营值班人员
  - Sheet "直播数据(六月)"：192行 — 分配日, 直播人员, 留资时间, 联系方式, 招生老师, 客户简单信息, 咨询反馈, 提升形式,
  备注, 留资方式

  2.4 现有去重逻辑（所有位置）

  仅有两处去重，且都不适用于Excel导入场景：

  1. API线索去重（clue_service.py 第216-226行）：
  existing_ids = {r[0] for r in db.query(ApiClue.clue_id).filter(ApiClue.clue_id.in_(clue_ids)).all()}
  new_clues = [c for c in clue_list if c.get("clue_id") and c["clue_id"] not in existing_ids]
  1. — 仅按 clue_id 去重，仅适用于API拉取的线索。
  2. TM→API反向桥接去重（clue_service.py 第252-293行）：
    - 当油猴脚本线索与API线索匹配时，更新已有记录而非新增。
  — 仅用于API与TM数据间的关联，不适用于Excel导入。
  3. Comment去重（api.py 第1404行）：
    - 数据库层面 UNIQUE(session_id, nickname, comment_time) 约束。
  — 仅对评论有效。

  结论：Excel导入（confirm_excel_import）和手动添加线索（create_manual_clue）均无任何去重机制。

  ---
  三、关键调用链/路由链/数据链

  3.1 当前Excel导入完整数据链

  [前端] leads.html handleExcelUpload()
    │
    ├─→ previewExcel()
    │     POST /admin/api/clues/excel-upload
    │     router: admin.py:1985 upload_excel_clue()
    │     ↓
    │     openpyxl.load_workbook(file, read_only=True)  ← 单Sheet
    │     ↓
    │     ws = wb.active  ← 只读第一个Sheet
    │     ↓
    │     列名映射: 手机号/姓名/微信号/私信时间/备注
    │     ↓
    │     逐行解析 → [{clue_id, name, phone, weixin, message_time, session_id, notes}]
    │     ↓
    │     返回 {code:0, data:results, total:N}
    │
    ├─→ confirmExcelImport()
    │     POST /admin/api/clues/excel-confirm
    │     router: admin.py:2090 confirm_excel_import()
    │     ↓
    │     for item in items:
    │       ApiClue(clue_id=item.clue_id, name=item.name, phone_decrypted=item.phone,
    │               weixin_manual=item.weixin, session_id=item.session_id,
    │               clue_source="excel", raw_data=...)
    │       db.add(new_clue)
    │     ↓
    │     db.commit()  ← 无去重、无冲突检测
    │     ↓
    │     返回 {code:0, message:"成功导入N条线索"}
    │
  [数据流终点] api_clues表 + (注：confirm不创建Lead记录，与create_manual_clue行为不一致)

  3.2 线索列表查询数据链（对比两条链的差异）

  admin.py:634 list_leads()
    ├─→ Lead表查询 → _lead_dto() → 合并到items
    └─→ ApiClue表查询 → _api_dto() → 合并到items
         ↓
         注意：Excel导入的ApiClue记录在admin线索页可查（source="excel"）
         但不会出现在Lead表中（confirm_excel_import不创建Lead）

  ---
  四、根因候选列表

  ┌─────┬─────────────────────────────────────────────────────────┬───────────────────────────────────────┐
  │  #  │                        候选根因                         │               影响范围                │
  ├─────┼─────────────────────────────────────────────────────────┼───────────────────────────────────────┤
  │ A   │ 数据库缺少教育/代运营/朋友圈广告对应的数据表            │ 无法存储非线索类数据                  │
  ├─────┼─────────────────────────────────────────────────────────┼───────────────────────────────────────┤
  │ B   │ Excel导入路由仅支持单Sheet（wb.active），只识别线索列名 │ 多Sheet文件仅处理第一个Sheet          │
  ├─────┼─────────────────────────────────────────────────────────┼───────────────────────────────────────┤
  │ C   │ Excel导入路由无去重逻辑（confirm_excel_import）         │ 重复导入导致数据重复                  │
  ├─────┼─────────────────────────────────────────────────────────┼───────────────────────────────────────┤
  │ D   │ 无CSV导入支持                                           │ 无法处理CSV格式文件                   │
  ├─────┼─────────────────────────────────────────────────────────┼───────────────────────────────────────┤
  │ E   │ 前端仅线索管理页有上传按钮，无独立的多维数据导入入口    │ 用户体验局限                          │
  ├─────┼─────────────────────────────────────────────────────────┼───────────────────────────────────────┤
  │ F   │ openpyxl版本兼容性问题                                  │ 某些xlsx文件无法解析（已修复在3.1.2） │
  └─────┴─────────────────────────────────────────────────────────┴───────────────────────────────────────┘

  ---
  五、候选根因逐一验证与排除

  5.1 候选A：数据库缺少对应表 — 确认为根因

  验证证据：
  - models.py 全文搜索：无 education_、douyin_、moment_、campaign_、student_ 等前缀的类定义
  - init_db()（database.py 第18-26行）：Base.metadata.create_all(bind=engine) — 只创建已定义的表
  - 示例表结构（已用zipfile+xml解析验证）：
    - 教育在线：含 目前学历/报考省份/报考学校/报考专业/报考层次/对话内容/分配日期/三次跟进 等字段
    - 抖音代运营：含 日消耗/投放效果/广告计划信息
    - 朋友圈广告：含 日消耗/联系方式/学生信息
  - 上述字段在现有任何表中均无对应列

  排除其他：这不是一个可选增强，而是结构性缺失。即使修复了导入路由，没有目标表数据也无法持久化。

  5.2 候选B：仅支持单Sheet — 确认为根因

  验证证据：
  - admin.py 第2000行：ws = wb.active — openpyxl 的 active 属性只返回第一个活动工作表
  - 完全无循环遍历 wb.sheetnames 的逻辑
  - 示例文件 多维--数据分配.xlsx 有3个Sheet，直播--数据分配.xlsx 有3个Sheet
  - 腾讯文档--数据分配.xlsx（合并文件）有7个Sheet

  影响：上传包含3个Sheet的文件，只有第一个Sheet（教育在线/新直播数据分配表）被处理，其余全部丢失。

  5.3 候选C：无去重逻辑 — 确认为根因

  验证证据：
  - confirm_excel_import（admin.py 第2106-2124行）for循环内只有 db.add(new_clue)，无任何 query.filter() 检查
  - create_manual_clue（admin.py 第1866-1900行）同理，无去重
  - 全局搜索 "重复"、"duplicate"、"dedup"：
    - clue_service.py 第216行：仅对API轮询的去重（clue_id in_查询）
    - clue_service.py 第252行：仅对TM→API反向桥接的去重
    - 无任何涉及 phone_decrypted 或 weixin 组合的去重
  - ApiClue 模型：clue_id 有 unique=True 约束，但 phone_decrypted + weixin 无任何唯一约束

  5.4 候选D：无CSV支持 — 确认为次要根因

  验证证据：
  - upload_excel_clues 函数名和注释：仅声明支持 .xlsx 和 .xls
  - 文件接收：file: bytes + openpyxl.load_workbook — 纯xlsx解析
  - .data/ 目录有CSV文件（线索分析列表.csv 等），说明CSV是业务中存在的格式
  - pandas 已安装在系统环境（C:\Program Files\Python313\Lib\site-packages），但项目代码中完全未使用

  5.5 候选E：前端入口限制 — 确认为次要根因

  验证证据：
  - leads.html 第29行：上传按钮仅在线索管理页面
  - admin/base.html 侧边栏导航中无独立的多维数据导入入口
  - pages.py 中无独立的多维数据导入页面路由
  - 模板文件 admin/ 目录下无任何"数据导入"相关的模板文件

  5.6 候选F：openpyxl版本 — 已排除

  验证证据：
  - pip show openpyxl → Version 3.1.2（最新稳定版）
  - 代码中导入方式 from openpyxl import load_workbook 是标准用法
  - 报错 TypeError: Fill() takes no arguments 是 Python 3.13 与旧版 openpyxl 的兼容性问题，3.1.2 已修复

  ---
  六、最终根因结论

  系统无法支持多维度Excel/CSV数据导入的根本原因是三层叠加：

  第一层：数据存储层（结构性缺失）——最深层根因

  现有模型只覆盖了直播线索数据，缺失3类数据的存储载体。

  ┌───────────────────┬──────────────┬────────────────────────────────┬───────────────────────────────────────────┐
  │  缺失的数据类型   │ 对应示例Shee │            关键字段            │                 缺失模型                  │
  │                   │      t       │                                │                                           │
  ├───────────────────┼──────────────┼────────────────────────────────┼───────────────────────────────────────────┤
  │ 教育在线招生数据  │ 教育在线     │ 学历/报考信息/对话内容/三次跟  │ education_records                         │
  │                   │              │ 进                             │                                           │
  ├───────────────────┼──────────────┼────────────────────────────────┼───────────────────────────────────────────┤
  │ 抖音代运营广告数  │ 抖音代运营   │ 日消耗/投放效果/计划关联       │ douyin_campaign_data                      │
  │ 据                │              │                                │                                           │
  ├───────────────────┼──────────────┼────────────────────────────────┼───────────────────────────────────────────┤
  │ 朋友圈广告数据    │ 朋友圈广告   │ 日消耗/客户信息/广告效果       │ moment_ad_data                            │
  ├───────────────────┼──────────────┼────────────────────────────────┼───────────────────────────────────────────┤
  │ 直播排班汇总数据  │ 直播排班表   │ 日期/消耗/线索数/主播时段      │ 可映射到现有Schedule+Session，但无导入支  │
  │                   │              │                                │ 持                                        │
  └───────────────────┴──────────────┴────────────────────────────────┴───────────────────────────────────────────┘

  这不是性能或配置问题，而是数据库Schema层面的结构性缺口。

  第二层：业务逻辑层（功能缺失）——直接原因

  现有Excel导入功能是单Sheet单用途的，无法处理多Sheet自动识别。

  1. upload_excel_clues 只调用 wb.active（单Sheet）
  2. 列名映射硬编码为线索类型（手机号/姓名/微信号/私信时间/备注）
  3. 无Sheet类型自动检测机制
  4. confirm_excel_import 无去重逻辑

  第三层：交互层（体验缺失）——表层原因

  前端无独立的多维数据导入入口，上传交互仅在线索页。

  ---
  七、业务影响分析

  7.1 直接影响

  ┌────────────────────────────────┬──────────┬────────────────────────────────────────────┐
  │              影响              │ 严重程度 │                    说明                    │
  ├────────────────────────────────┼──────────┼────────────────────────────────────────────┤
  │ 教育在线数据无法入库           │ P0       │ 1197条招生记录无法录入，招生老师无系统可查 │
  ├────────────────────────────────┼──────────┼────────────────────────────────────────────┤
  │ 抖音代运营数据无法入库         │ P0       │ 201条广告投放数据无法分析ROI               │
  ├────────────────────────────────┼──────────┼────────────────────────────────────────────┤
  │ 朋友圈广告数据无法入库         │ P1       │ 206条广告数据丢失                          │
  ├────────────────────────────────┼──────────┼────────────────────────────────────────────┤
  │ 多Sheet文件只能处理第一个Sheet │ P0       │ 合并文件（腾讯文档版）丢失6/7的数据        │
  ├────────────────────────────────┼──────────┼────────────────────────────────────────────┤
  │ 重复数据无法检测               │ P1       │ 同一客户重复录入后无法识别                 │
  └────────────────────────────────┴──────────┴────────────────────────────────────────────┘

  7.2 次生影响

  - 招生老师分配数据（分配日期/招生老师字段）无法与线索系统打通
  - 广告投放ROI分析缺少抖音代运营和朋友圈广告的基础数据
  - 排班数据（直播排班表Sheet）与现有Schedule系统无关联

  ---
  八、逐步排查计划

  Phase 1：数据模型设计（不可跳过，必须先完成）

  T1.1 新建 education_records 表

  ┌───────────────────────┬────────────┬────────────────────┐
  │         字段          │    类型    │        来源        │
  ├───────────────────────┼────────────┼────────────────────┤
  │ id                    │ Integer PK │ 自增               │
  ├───────────────────────┼────────────┼────────────────────┤
  │ source                │ Text       │ 来源（教育在线）   │
  ├───────────────────────┼────────────┼────────────────────┤
  │ name                  │ Text       │ 姓名               │
  ├───────────────────────┼────────────┼────────────────────┤
  │ phone                 │ Text       │ 电话号码（脱敏前） │
  ├───────────────────────┼────────────┼────────────────────┤
  │ education_level       │ Text       │ 目前学历           │
  ├───────────────────────┼────────────┼────────────────────┤
  │ exam_province         │ Text       │ 报考省份           │
  ├───────────────────────┼────────────┼────────────────────┤
  │ exam_school           │ Text       │ 报考学校           │
  ├───────────────────────┼────────────┼────────────────────┤
  │ exam_major            │ Text       │ 报考专业           │
  ├───────────────────────┼────────────┼────────────────────┤
  │ exam_level            │ Text       │ 报考层次           │
  ├───────────────────────┼────────────┼────────────────────┤
  │ weixin                │ Text       │ 微信               │
  ├───────────────────────┼────────────┼────────────────────┤
  │ province              │ Text       │ 所在省份           │
  ├───────────────────────┼────────────┼────────────────────┤
  │ city                  │ Text       │ 所在城市           │
  ├───────────────────────┼────────────┼────────────────────┤
  │ district              │ Text       │ 所在区县           │
  ├───────────────────────┼────────────┼────────────────────┤
  │ data_status           │ Text       │ 数据状态与标签     │
  ├───────────────────────┼────────────┼────────────────────┤
  │ improve_type          │ Text       │ 提升形式           │
  ├───────────────────────┼────────────┼────────────────────┤
  │ consultation_feedback │ Text       │ 咨询反馈           │
  ├───────────────────────┼────────────┼────────────────────┤
  │ followup_1            │ Text       │ 第一次跟进         │
  ├───────────────────────┼────────────┼────────────────────┤
  │ followup_2            │ Text       │ 二次跟进           │
  ├───────────────────────┼────────────┼────────────────────┤
  │ followup_3            │ Text       │ 三次跟进           │
  ├───────────────────────┼────────────┼────────────────────┤
  │ dialog_content        │ Text       │ 对话内容           │
  ├───────────────────────┼────────────┼────────────────────┤
  │ assign_date           │ Text       │ 分配日期           │
  ├───────────────────────┼────────────┼────────────────────┤
  │ assigned_teacher      │ Text       │ 招生老师           │
  ├───────────────────────┼────────────┼────────────────────┤
  │ notes                 │ Text       │ 备注               │
  ├───────────────────────┼────────────┼────────────────────┤
  │ raw_data              │ Text       │ 原始行数据JSON     │
  ├───────────────────────┼────────────┼────────────────────┤
  │ created_at            │ Text       │ 入库时间           │
  └───────────────────────┴────────────┴────────────────────┘

  唯一约束：UNIQUE(phone, weixin, assign_date) — 联系方式+微信+分配日期组合去重

  T1.2 新建 douyin_campaign_data 表

  ┌───────────────────────┬────────────┬───────────────────────────┐
  │         字段          │    类型    │           来源            │
  ├───────────────────────┼────────────┼───────────────────────────┤
  │ id                    │ Integer PK │ 自增                      │
  ├───────────────────────┼────────────┼───────────────────────────┤
  │ assign_date           │ Text       │ 分配日                    │
  ├───────────────────────┼────────────┼───────────────────────────┤
  │ lead_time             │ Text       │ 留资时间（Excel小数时间） │
  ├───────────────────────┼────────────┼───────────────────────────┤
  │ contact               │ Text       │ 联系方式                  │
  ├───────────────────────┼────────────┼───────────────────────────┤
  │ teacher               │ Text       │ 招生老师                  │
  ├───────────────────────┼────────────┼───────────────────────────┤
  │ data_status           │ Text       │ 数据状态与标签            │
  ├───────────────────────┼────────────┼───────────────────────────┤
  │ improve_type          │ Text       │ 提升形式                  │
  ├───────────────────────┼────────────┼───────────────────────────┤
  │ consultation_feedback │ Text       │ 咨询反馈                  │
  ├───────────────────────┼────────────┼───────────────────────────┤
  │ followup_1            │ Text       │ 第一次跟进                │
  ├───────────────────────┼────────────┼───────────────────────────┤
  │ followup_2            │ Text       │ 第二次跟进                │
  ├───────────────────────┼────────────┼───────────────────────────┤
  │ created_at            │ Text       │ 入库时间                  │
  └───────────────────────┴────────────┴───────────────────────────┘

  唯一约束：UNIQUE(contact, weixin, assign_date)

  T1.3 新建 moment_ad_data 表

  ┌───────────────────────┬────────────┬──────────────┐
  │         字段          │    类型    │     来源     │
  ├───────────────────────┼────────────┼──────────────┤
  │ id                    │ Integer PK │ 自增         │
  ├───────────────────────┼────────────┼──────────────┤
  │ assign_date           │ Text       │ 分配日       │
  ├───────────────────────┼────────────┼──────────────┤
  │ daily_spend           │ Float      │ 日消耗       │
  ├───────────────────────┼────────────┼──────────────┤
  │ contact               │ Text       │ 联系方式     │
  ├───────────────────────┼────────────┼──────────────┤
  │ student_name          │ Text       │ 学生姓名     │
  ├───────────────────────┼────────────┼──────────────┤
  │ teacher               │ Text       │ 招生老师     │
  ├───────────────────────┼────────────┼──────────────┤
  │ customer_info         │ Text       │ 客户简单信息 │
  ├───────────────────────┼────────────┼──────────────┤
  │ consultation_feedback │ Text       │ 咨询反馈     │
  ├───────────────────────┼────────────┼──────────────┤
  │ notes                 │ Text       │ 备注         │
  ├───────────────────────┼────────────┼──────────────┤
  │ created_at            │ Text       │ 入库时间     │
  └───────────────────────┴────────────┴──────────────┘

  唯一约束：UNIQUE(contact, weixin, assign_date)

  T1.4 在 database.py 的 init_db() 中添加新表迁移

  在 init_db() 函数中（database.py 第26行 Base.metadata.create_all 之后），添加：
  from models import EducationRecord, DouyinCampaignData, MomentAdData
  （需要models.py中先import这些类才能create_all生效）

  检查方法：
  - 验证：Base.metadata.create_all(bind=engine) 后查询 sqlite_master 确认3张新表存在
  - 异常分支：表已存在（CREATE TABLE IF NOT EXISTS 或捕获 OperationalError）
  - 判定标准：3张新表均可在数据库中通过 SELECT * FROM education_records 等查询

  ---
  Phase 2：Sheet类型识别引擎

  T2.1 实现Sheet类型自动检测函数

  在 admin.py 中新增函数 _detect_sheet_type(headers)：

  def _detect_sheet_type(headers):
      """
      根据列名自动识别Sheet类型
      返回: 'live_lead' | 'schedule' | 'education' | 'douyin_ops' | 'moment_ad' | 'unknown'
      """
      header_lower = [str(h).lower().strip() if h else '' for h in headers]

      # 教育在线：含"报考专业"/"报考层次"/"目前学历"
      if any('报考专业' in h or '报考层次' in h or '目前学历' in h for h in header_lower):
          return 'education'

      # 直播排班表：含"营销消耗"/"直播时间"/"总时长"
      if any('营销消耗' in h or '总时长' in h or '广告流线索' in h for h in header_lower):
          return 'schedule'

      # 朋友圈广告：含"日消耗"/"学生姓名"且无"营销消耗"
      if any('日消耗' in h for h in header_lower) and not any('营销消耗' in h for h in header_lower):
          return 'moment_ad'

      # 抖音代运营：含"联系方式"/"提升形式"/"咨询反馈"（不含学历字段）
      if any('联系方式' in h for h in header_lower) and not any('报考专业' in h for h in header_lower):
          if any('数据状态' in h or '提升形式' in h for h in header_lower):
              return 'douyin_ops'

      # 直播数据分配表：含"电话"/"微信"/"用户昵称"/"留资路径"/"投放账户"
      if any('电话' in h and '微信' in h for h in header_lower):
          if any('投放账户' in h or '单元名称' in h or '单元ID' in h for h in header_lower):
              return 'live_lead'
          if any('用户昵称' in h or '留资路径' in h for h in header_lower):
              return 'live_lead'

      return 'unknown'

  检查方法：
  - 单元测试：传入各Sheet的Row1列名，验证返回正确的sheet_type
  - 边界情况测试：混合列名、空列名、部分匹配

  T2.2 实现多Sheet遍历解析

  修改 upload_excel_clues 函数（admin.py 第1985行），从 wb.active 改为遍历所有Sheet：

  # 替换: ws = wb.active
  results_by_sheet = {}
  for sheet_name in wb.sheetnames:
      ws = wb[sheet_name]
      # 读取表头
      headers = [cell.value for cell in ws[1] if cell.value]
      if not headers:
          continue
      # 识别类型
      sheet_type = _detect_sheet_type(headers)
      # 按类型解析
      sheet_results = _parse_sheet_data(ws, headers, sheet_type, ...)
      results_by_sheet[sheet_name] = {
          'type': sheet_type,
          'data': sheet_results,
          'errors': sheet_errors,
          'total': len(sheet_results)
      }

  检查方法：
  - 上传多维文件（3个Sheet），验证返回 results_by_sheet 包含3个Sheet的解析结果
  - 每个Sheet的 type 字段正确（education/douyin_ops/moment_ad）
  - 异常分支：空Sheet被跳过并记录警告

  ---
  Phase 3：各Sheet数据解析器

  T3.1 直播数据分配表解析器（live_lead）

  映射关系：
  - 联系方式(H) → phone（若为微信号开头则存weixin）
  - 微信(I) → weixin
  - 用户昵称(S) → nickname
  - 所在城市(L) → city
  - 招生老师(M) → assigned_employee
  - 数据状态与标签(N) → is_valid标记
  - 留资路径(T) → path
  - 投放账户(U) → ad_account
  - 单元名称(V) → 存raw_data
  - 单元ID(W) → 存raw_data
  - 留资日期(B，Excel序列号) → 需转换（Excel epoch = 1899-12-30，序列号46203 → 2026-07-01）
  - 留资时间(D，小数) → 需转换（0.887 → 21:17）

  去重键：phone + weixin + 留资日期

  输出：ApiClue 记录（clue_source="excel"）

  T3.2 直播排班表解析器（schedule）

  此Sheet为汇总数据（每行=某日某时段），非单条线索：
  - 日期 → date
  - 营销消耗 → 存raw_data或ad_plan_spends
  - 直播人员 → 关联Anchor
  - 直播时间 → 时段字符串
  - 广告流线索/自然流线索/总线索 → 存raw_data
  - 运营值班人员 → 关联RecruitEmployee

  去重键：date + 直播时间（时段不重复）

  输出：映射到 ScheduleBinding 或新建汇总记录

  T3.3 教育在线解析器（education）

  映射关系（全部映射到新表 education_records）：
  - 电话号码(C) → phone
  - 姓名(B) → name
  - 微信(I) → weixin
  - 目前学历(D) → education_level
  - 报考省份(E) → exam_province
  - 报考学校(F) → exam_school
  - 报考专业(G) → exam_major
  - 报考层次(H) → exam_level
  - 所在城市(K) → city
  - 分配日期(Q，Excel序列号) → assign_date
  - 招生老师(R) → assigned_teacher
  - 数据状态与标签(S) → data_status
  - 对话内容(P) → dialog_content
  - 一次/二次/三次跟进(V/W/X) → followup_1/2/3

  去重键：phone + weixin + assign_date

  T3.4 抖音代运营解析器（douyin_ops）

  映射到新表 douyin_campaign_data：
  - 联系方式 → contact（存phone）
  - 留资时间 → lead_time
  - 分配日 → assign_date
  - 招生老师 → teacher
  - 数据状态与标签 → data_status
  - 咨询反馈/提升形式 → consultation_feedback/improve_type

  去重键：contact + weixin(可能为空) + assign_date

  T3.5 朋友圈广告解析器（moment_ad）

  映射到新表 moment_ad_data：
  - 联系方式 → contact
  - 学生姓名 → student_name
  - 日消耗 → daily_spend
  - 分配日 → assign_date

  去重键：contact + weixin(可能为空) + assign_date

  ---
  Phase 4：去重引擎

  T4.1 通用去重函数

  def _check_duplicates(db, table_class, unique_fields, items, field_mapping):
      """
      检查重复数据
      - unique_fields: 用于去重的字段列表（如 ['phone', 'weixin', 'assign_date']）
      - items: 待检查的数据列表
      - field_mapping: Excel列名→模型字段名的映射
      返回: (unique_items, duplicate_items)
      """
      # 构建现有记录的查找键集合
      existing_keys = set()
      query = db.query(*[getattr(table_class, f) for f in unique_fields])
      for row in query.all():
          key = tuple(str(v) if v is not None else '' for v in row)
          existing_keys.add(key)

      unique_items = []
      duplicate_items = []
      for item in items:
          key = tuple(str(item.get(field_mapping.get(f, '')) or '') for f in unique_fields)
          if key in existing_keys:
              duplicate_items.append(item)
          else:
              unique_items.append(item)

      return unique_items, duplicate_items

  T4.2 重复数据记录机制

  新增 import_logs 表：
  class ImportLog(Base):
      __tablename__ = "import_logs"
      id = Column(Integer, primary_key=True, autoincrement=True)
      sheet_type = Column(Text, nullable=False)          # Sheet类型
      sheet_name = Column(Text, nullable=False)          # Sheet名称
      admin_name = Column(Text, nullable=True)           # 操作管理员
      total_rows = Column(Integer, default=0)            # 总行数
      imported_count = Column(Integer, default=0)        # 导入成功数
      skipped_count = Column(Integer, default=0)         # 重复跳过数
      error_count = Column(Integer, default=0)           # 错误数
      errors = Column(Text, nullable=True)               # 错误详情JSON
      duplicates = Column(Text, nullable=True)           # 重复数据JSON
      created_at = Column(Text, server_default="CURRENT_TIMESTAMP")

  T4.3 前端重复数据展示

  在导入确认弹窗中增加"重复数据"标签页：
  - 显示被跳过的重复记录列表（phone, name, 重复原因）
  - 允许管理员"强制导入"覆盖已有记录（可选功能）

  ---
  Phase 5：路由重构

  T5.1 拆分路由为两个阶段

  # 阶段1：预览（解析+去重检查）
  POST /admin/api/import/multi-sheet-upload
    输入: multipart/form-data (file)
    输出: {
      sheets: {
        "教育在线": { type: "education", data: [...], total: N, errors: [...] },
        "抖音代运营": { type: "douyin_ops", data: [...], total: N },
        "朋友圈广告": { type: "moment_ad", data: [...], total: N },
        "直播数据分配表（7月始）": { type: "live_lead", data: [...], total: N },
        "直播排班表": { type: "schedule", data: [...], total: N }
      },
      summary: { total: N, by_type: {...} }
    }

  # 阶段2：确认导入
  POST /admin/api/import/multi-sheet-confirm
    输入: { sheets: {... parsed_data ...}, force_duplicate: false }
    输出: { code: 0, message: "成功导入X条，跳过Y条重复" }

  T5.2 CSV导入路由

  POST /admin/api/import/csv-upload
    输入: multipart/form-data (file, sheet_type hint)
    处理: csv.reader / pandas.read_csv
    输出: 与xlsx相同的格式

  T5.3 旧路由兼容

  保留旧路由 POST /admin/api/clues/excel-upload 和 excel-confirm，内部委托给新函数，确保现有前端调用不中断。

  ---
  Phase 6：前端改造

  T6.1 新建独立多维数据导入页面

  新增路由：GET /admin/import-data → admin/import_data.html

  新增模板：server/templates/admin/import_data.html

  组件结构：
  ┌─ 文件选择区 ─────────────────────────┐
  │ [选择.xlsx/.csv文件] [上传并解析]      │
  │ 支持格式: .xlsx, .xls, .csv            │
  │ 最大文件大小: 50MB                     │
  └──────────────────────────────────────┘
            ↓ 解析完成
  ┌─ Sheet/数据预览区 ────────────────────┐
  │ ┌─ 教育在线 (1197行) ── [导入] [跳过] ─┐ │
  │ │ [预览表格: 前10行]                     │ │
  │ │ 重复: 5条 [查看]                       │ │
  │ └──────────────────────────────────────┘ │
  │ ┌─ 抖音代运营 (201行) ── [导入] [跳过] ─┐ │
  │ │ [预览表格: 前10行]                     │ │
  │ └──────────────────────────────────────┘ │
  │ ┌─ 朋友圈广告 (206行) ── [导入] [跳过] ─┐ │
  │ │ [预览表格: 前10行]                     │ │
  │ └──────────────────────────────────────┘ │
  │ [全部导入]                              │
  └──────────────────────────────────────┘
            ↓ 导入完成
  ┌─ 导入结果 ────────────────────────────┐
  │ 成功: X条 | 跳过重复: Y条 | 错误: Z条  │
  │ [查看重复记录] [查看错误记录]            │
  └──────────────────────────────────────┘

  T6.2 侧边栏导航更新（admin/base.html）

  在侧边栏添加"多维数据导入"入口：
  <a href="/admin/import-data" class="...">📥 多维数据导入</a>

  ---
  Phase 7：数据库迁移

  T7.1 执行表创建迁移

  在 database.py 的 init_db() 中添加新表注册和迁移代码：

  # 1. 导入新模型（使SQLAlchemy注册表结构）
  from models import (..., EducationRecord, DouyinCampaignData,
                      MomentAdData, ImportLog)

  # 2. create_all会自动创建不存在的表
  Base.metadata.create_all(bind=engine)

  # 3. 为已有数据库添加唯一约束（ALTER TABLE方式）
  try:
      with engine.connect() as conn:
          conn.execute(text("""
              CREATE UNIQUE INDEX IF NOT EXISTS idx_edu_phone_weixin_date
              ON education_records(phone, weixin, assign_date)
          """))
          conn.commit()
  except Exception:
      pass

  T7.2 数据迁移脚本（可选）

  如需从现有Excel文件初始化历史数据：
  # scripts/import_historical_data.py
  # 读取 .docs/ 目录中的示例文件，批量导入历史数据

  ---
  九、最小验证闭环

  闭环1：模型层验证

  输入: 空数据库
  步骤: 启动服务 → init_db() 执行
  验证:
    ✓ 3张新表创建成功（SHOW TABLES / SELECT * FROM sqlite_master）
    ✓ 唯一约束生效（尝试插入重复记录，报UNIQUE constraint错误）
    ✓ 外键关系正确（可JOIN recruit_teams验证）

  闭环2：解析层验证

  输入: 多维--数据分配.xlsx（3个Sheet，共1604行）
  步骤: POST /admin/api/import/multi-sheet-upload
  验证:
    ✓ 返回3个Sheet的解析结果
    ✓ Sheet类型识别正确: 教育在线→education, 抖音代运营→douyin_ops, 朋友圈广告→moment_ad
    ✓ 每Sheet数据行数正确: 教育在线1197行, 抖音代运营201行, 朋友圈广告206行
    ✓ 列名映射正确（phone/weixin/name等字段不丢失）

  闭环3：去重层验证

  输入: 已导入的education_records中 phone="18349322909"
  步骤: 再次上传包含同一phone的文件
  验证:
    ✓ 该记录出现在"重复数据"列表中
    ✓ 确认导入后，该记录未被再次插入
    ✓ ImportLog中记录 skipped_count 增加

  闭环4：端到端验证

  输入: 腾讯文档--数据分配.xlsx（7个Sheet）
  步骤: 前端上传 → 预览 → 确认导入 → 查询各表
  验证:
    ✓ 7个Sheet均被识别和处理
    ✓ 教育在线数据出现在 education_records 表
    ✓ 直播数据分配数据出现在 api_clues 表（clue_source="excel"）
    ✓ 直播排班数据映射到 ScheduleBinding 或汇总记录
    ✓ 无重复记录
    ✓ 前端结果展示正确

  ---
  十、风险与边界条件

  10.1 技术风险

  ┌────────────────────────────┬──────┬───────────────────┬──────────────────────────────────────────────────────────┐
  │            风险            │ 概率 │       影响        │                         缓解措施                         │
  ├────────────────────────────┼──────┼───────────────────┼──────────────────────────────────────────────────────────┤
  │ Excel序列号日期转换偏差    │ 中   │ 排班/分配日期错误 │ 使用 openpyxl.utils.datetime.from_excel_serial()         │
  │                            │      │                   │ 精确转换                                                 │
  ├────────────────────────────┼──────┼───────────────────┼──────────────────────────────────────────────────────────┤
  │ 大文件内存溢出（>10万行）  │ 低   │ 服务崩溃          │ read_only=True 模式 + 分批处理                           │
  ├────────────────────────────┼──────┼───────────────────┼──────────────────────────────────────────────────────────┤
  │ SQLite并发写入冲突         │ 低   │ 导入失败          │ 使用 busy_timeout=5000（已配置）                         │
  ├────────────────────────────┼──────┼───────────────────┼──────────────────────────────────────────────────────────┤
  │ 部分Sheet列名不标准        │ 中   │ 解析失败          │ 增加列名别名映射表 + 人工指定类型覆盖                    │
  ├────────────────────────────┼──────┼───────────────────┼──────────────────────────────────────────────────────────┤
  │ CSV编码不一致（GBK/UTF-8） │ 中   │ 解析失败          │ chardet 自动检测编码                                     │
  └────────────────────────────┴──────┴───────────────────┴──────────────────────────────────────────────────────────┘

  10.2 业务风险

  ┌───────────────────────────────────────────────┬──────┬─────────────┬──────────────────────────────────────┐
  │                     风险                      │ 概率 │    影响     │               缓解措施               │
  ├───────────────────────────────────────────────┼──────┼─────────────┼──────────────────────────────────────┤
  │ 用户误操作覆盖已有数据                        │ 中   │ 数据丢失    │ 强制导入需二次确认 + 导入前自动备份  │
  ├───────────────────────────────────────────────┼──────┼─────────────┼──────────────────────────────────────┤
  │ 同一客户在不同Sheet中重复                     │ 高   │ 跨Sheet重复 │ 去重仅限同Sheet内，跨Sheet需后续关联 │
  ├───────────────────────────────────────────────┼──────┼─────────────┼──────────────────────────────────────┤
  │ 分配日期格式不一致（Excel序列号 vs 文本日期） │ 高   │ 去重失效    │ 统一转换后比较                       │
  └───────────────────────────────────────────────┴──────┴─────────────┴──────────────────────────────────────┘

  10.3 边界条件

  1. 空Sheet：跳过不报错，记录在ImportLog中
  2. 全空行：if not any(row): continue 已处理（admin.py 第2025行）
  3. 超大单元格（对话内容含HTML/图片）：存为TEXT，SQLite无长度限制
  4. 合并单元格：openpyxl只返回左上角值，需在解析时处理
  5. 同一Sheet中出现多种数据类型：以第一行为准识别类型，不一致的行记录为错误
  6. CSV无BOM的UTF-8 vs GBK：需编码检测

  ---
  十一、面向用户的直接建议

  11.1 当前可执行的操作（不修改代码）

  1. 数据整理：将合并的腾讯文档文件按Sheet拆分，分别导入现有线索管理页面
    - "新直播数据分配表（7月始）" → 通过现有Excel导入 → 创建线索
    - "直播排班表" → 通过排班管理页面手动录入
    - "教育在线"、"抖音代运营"、"朋友圈广告" → 暂时无法录入
  2. 重复数据手动检查：导入前先用Excel的"条件格式→重复值"功能高亮重复行

  11.2 改造优先级建议

  ┌────────┬──────────────────────────────────────┬────────────────────────────┐
  │ 优先级 │                 内容                 │            原因            │
  ├────────┼──────────────────────────────────────┼────────────────────────────┤
  │ P0     │ 新建3张数据表 + import_logs表        │ 没有表，后续一切无从谈起   │
  ├────────┼──────────────────────────────────────┼────────────────────────────┤
  │ P0     │ 实现多Sheet遍历 + Sheet类型识别      │ 这是解决多Sheet文件的核心  │
  ├────────┼──────────────────────────────────────┼────────────────────────────┤
  │ P1     │ 去重引擎 + 重复数据展示              │ 业务明确要求"杜绝重复添加" │
  ├────────┼──────────────────────────────────────┼────────────────────────────┤
  │ P1     │ 新增教育在线/代运营/朋友圈广告解析器 │ 映射到新表                 │
  ├────────┼──────────────────────────────────────┼────────────────────────────┤
  │ P2     │ 前端独立导入页面                     │ 当前线索页的上传入口不够用 │
  ├────────┼──────────────────────────────────────┼────────────────────────────┤
  │ P2     │ CSV支持                              │ 业务有CSV文件需求          │
  └────────┴──────────────────────────────────────┴────────────────────────────┘

  11.3 不推荐的方案

  - 不要用pandas：现有代码只用openpyxl，引入pandas会增加部署复杂度和内存消耗，openpyxl完全够用
  - 不要建统一的大宽表：3种数据类型结构差异大，应建3张独立表 + 统一的import_logs
  - 不要修改现有ApiClue/Lead表结构：现有系统运行稳定，新增表不干扰现有逻辑

  ---
  十二、文件级修复清单（原子化任务）

  12.1 models.py 修改（增3个类）

  - [ ] T1.1a: 在 models.py 第501行后新增 class EducationRecord(Base)
  - [ ] T1.1b: 在 models.py 新增 class DouyinCampaignData(Base)
  - [ ] T1.1c: 在 models.py 新增 class MomentAdData(Base)
  - [ ] T1.1d: 在 models.py 新增 class ImportLog(Base)
  - [ ] T1.1e: 在 database.py 第20行 import 列表中添加新类名

  12.2 database.py 修改

  - [ ] T7.1a: 在 init_db() 中添加新表的唯一约束迁移代码

  12.3 routers/admin.py 修改

  - [ ] T2.1a: 新增 _detect_sheet_type(headers) 函数
  - [ ] T2.1b: 新增 _parse_sheet_data(ws, headers, sheet_type, ...) 分发函数
  - [ ] T2.1c: 新增 _parse_live_lead_sheet() 解析器
  - [ ] T2.1d: 新增 _parse_education_sheet() 解析器
  - [ ] T2.1e: 新增 _parse_douyin_ops_sheet() 解析器
  - [ ] T2.1f: 新增 _parse_moment_ad_sheet() 解析器
  - [ ] T2.1g: 新增 _parse_schedule_sheet() 解析器
  - [ ] T2.2a: 重写 upload_excel_clues 中的 wb.active → 遍历所有Sheet
  - [ ] T3.x: 修改 confirm_excel_import 支持多Sheet数据 + 去重
  - [ ] T4.1a: 新增 _check_duplicates() 通用去重函数
  - [ ] T5.1a: 新增 POST /admin/api/import/multi-sheet-upload 路由
  - [ ] T5.1b: 新增 POST /admin/api/import/multi-sheet-confirm 路由
  - [ ] T5.2a: 新增 POST /admin/api/import/csv-upload 路由
  - [ ] T5.3a: 保留旧路由作为兼容层

  12.4 前端模板修改

  - [ ] T6.1a: 新增 server/templates/admin/import_data.html
  - [ ] T6.2a: 修改 server/templates/admin/base.html 侧边栏添加导入入口
  - [ ] T6.2b: 修改 server/routers/pages.py 添加 GET /admin/import-data 路由

  ---