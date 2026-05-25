# Phase 10.5：系统最终收尾

## Milestone
- Milestone: 系统最终收尾
- 目标：消除最后3个已知问题（页面刷新、告警推送、share_rate列）
- 工期：1天（2026-05-22）

---

## Phase-1: 页面自动刷新

### Task 1-1: reload+标记位机制

**文件**: `tampermonkey/alive-broadcast-sync.user.js`

**修改点1** — `startHeartbeat()`:
```javascript
// 检测到采集条件 → 设置标记 → reload
GM_setValue('pending_collect', 'true');
location.reload();
```

**修改点2** — 主入口:
```javascript
const pending = GM_getValue('pending_collect', 'false');
if (pending === 'true') {
    GM_setValue('pending_collect', 'false');
    setTimeout(() => startCollection(), 3000);
} else {
    startHeartbeat();
}
```

**防死循环**: reload后标记立即清除，采集完成后不再触发reload。

---

## Phase-2: 异常告警推送

### Task 2-1: 服务端 POST /api/alert

**文件**: `server/routers/api.py`

**新增内容**:
- `_alert_last_sent = {}` 内存频率限制字典
- `ALERT_COOLDOWN_SECONDS = 600`（10分钟）
- `receive_alert(data: dict, db)` 函数：
  1. 同类型10分钟去重
  2. 读取Setting表邮箱配置
  3. 未配置 → 仅记录
  4. 构造HTML邮件 → 调用 `send_email()`
  5. 返回 `{code:0, message:"告警已发送"}`

**响应场景**:
| 场景 | 响应 |
|------|------|
| 成功发送 | `{"code":0,"message":"告警已发送"}` |
| 邮箱未配置 | `{"code":0,"message":"告警已记录（邮箱未配置）"}` |
| 频率限制 | `{"code":0,"message":"告警已忽略（10分钟内重复）"}` |

### Task 2-2: 油猴脚本 sendAlert()

**文件**: `tampermonkey/alive-broadcast-sync.user.js`

**新增函数**:
```javascript
function sendAlert(type, message, sessionTime) {
    GM_xmlhttpRequest({
        method: 'POST',
        url: `${CONFIG.SERVER_URL}/api/alert`,
        headers: { 'Content-Type': 'application/json' },
        data: JSON.stringify({ type, message, session_time: sessionTime, timestamp: ... })
    });
}
```

**调用位置**:
1. `validateMetrics()` 完整率<50% → `sendAlert('采集异常', ...)`
2. `startCollection()` collected===0 && skipped===0 → `sendAlert('采集失败', ...)`

---

## Phase-3: share_rate数据库列补充

### Task 3-1: models.py + ai_service.py + database.py

**models.py**:
```python
share_rate = Column(Text)  # SessionMetric类，share_users之后
```

**ai_service.py FIELD_LABELS**:
```python
"share_rate": "分享率"
```

**database.py init_db()迁移**:
```python
try:
    with engine.connect() as conn:
        conn.execute("ALTER TABLE session_metrics ADD COLUMN share_rate TEXT")
except Exception:
    pass  # 列已存在则忽略
```

---

## 验收条件

| # | 验收项 | 状态 |
|---|--------|------|
| 1 | 页面自动刷新 | ✅ |
| 2 | 刷新后立即采集 | ✅ |
| 3 | 无死循环 | ✅ |
| 4 | 异常告警邮件 | ✅ |
| 5 | 0场成功告警 | ✅ |
| 6 | 告警频率限制 | ✅ |
| 7 | share_rate入库 | ✅ |
| 8 | 已有data.db兼容 | ✅ |

## 文件变更

- 修改: 5个文件 (user.js, api.py, models.py, ai_service.py, database.py)
- 语法验证: JS✅ Python✅
