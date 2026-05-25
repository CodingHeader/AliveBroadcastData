# 执行日志: 油猴脚本去重优化

执行日期: 2026-05-22
方案: 方案C — 一次拉取+本地比对+一轮遍历

## Phase-1: 服务端新增按日期查询已有场次API

### Task 1-1: GET /api/sessions/by-date
- 文件: `server/routers/api.py`
- 新增路由 `@router.get("/sessions/by-date")`
- 参数: `date` (Query, 格式 YYYY-MM-DD)
- 逻辑: 范围查询 sessions 表 start_time >= date 00:00:00 AND < date+1 00:00:00
- 响应: `{"code": 0, "starts": ["2026-05-21 09:28:00", ...]}`

## Phase-2: 油猴脚本去重逻辑重构

### Task 2-1: getExistingSessions() 函数
- 文件: `tampermonkey/alive-broadcast-sync.user.js`
- 新增函数，调用 `GET /api/sessions/by-date`，返回 `Set`
- 降级策略: 服务端不可达/解析失败 → 空Set → 全部采集

### Task 2-2: startCollection() 重构
- 循环前: `const existingStarts = await getExistingSessions(yesterday)`
- 循环内: `checkSessionExists` → `existingStarts.has(timeInfo.start)`
- 新增: `collected`/`skipped` 计数器 + 完成日志

### Task 2-3: 旧调用清理
- startCollection() 中移除 checkSessionExists 调用
- checkSessionExists 函数定义保留，标记为"备用"

## 验证结果

| # | 验收项 | 结果 |
|---|--------|------|
| 1 | 服务端API有数据 | `{"code":0,"starts":["2026-05-21 09:28:00"]}` |
| 2 | 服务端API无数据 | `{"code":0,"starts":[]}` |
| 3 | 参数缺失 | 422 (FastAPI校验) |
| 4 | JS语法检查 | 通过 |
| 5 | api.py导入 | 通过，13 routes注册 |
