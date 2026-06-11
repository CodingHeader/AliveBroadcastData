# Phase 3: 油猴脚本 — 三级原子化执行方案

## Milestone 上下文

| 项 | 内容 |
|---|------|
| 所属Milestone | AliveBroadcastData 抖音直播数据分析系统 |
| 业务目标 | 自动采集抖音来客"线索大屏"页面数据，POST到服务端 |
| 在整体中的位置 | **第3个Phase**，依赖Phase 2（API可用） |
| 被依赖方 | Phase 9（端到端测试） |

## Phase 概要

| 项 | 内容 |
|---|------|
| 工期 | 3天 |
| 前置依赖 | Phase 2（POST /api/session 和 GET /api/session/check 可用） |
| 产出文件 | 1个新建文件 |
| 涉及模块 | 油猴脚本（Tampermonkey） |
| 运行环境 | 浏览器（Chrome/Edge），life.douyin.com |

## 产出文件总览

| 文件路径 | 类型 | 用途 |
|----------|------|------|
| `tampermonkey/alive-broadcast-sync.user.js` | 新建 | 数据采集油猴脚本 |

---

## Task 列表总览

| # | Task | 优先级 | 依赖 | 预估 |
|---|------|--------|------|------|
| 3.1 | 脚本框架+配置区 | P0 | Phase 2 | 1h |
| 3.2 | 场次遍历逻辑 | P0 | Task 3.1 | 3h |
| 3.3 | 核心指标采集 | P0 | Task 3.2 | 3h |
| 3.4 | 线索列表采集 | P0 | Task 3.2 | 2h |
| 3.5 | 评论明细采集 | P1 | Task 3.2 | 2h |
| 3.6 | 高意向用户采集 | P1 | Task 3.2 | 2h |
| 3.7 | 图片资源采集 | P2 | Task 3.2 | 1h |
| 3.8 | 数据发送+防重复 | P0 | Task 3.3~3.7 | 2h |
| 3.9 | 完整流程测试 | P0 | Task 3.8 | 3h |

---

## Task 3.1: 脚本框架+配置区

### 任务描述
编写 UserScript 头部声明、配置常量区、定时触发逻辑框架。

### 执行逻辑

#### 1. 触发
| 项目 | 内容 |
|------|------|
| 触发方式 | Tampermonkey 自动加载脚本 |
| 匹配页面 | `*://life.douyin.com/*` |

#### 2. 文件操作

**新建：**

| 路径 | 用途 |
|------|------|
| `tampermonkey/alive-broadcast-sync.user.js` | 油猴脚本主文件 |

### 伪代码

```javascript
// ==UserScript==
// @name         抖音直播数据同步
// @namespace    alive-broadcast-data
// @version      1.0.0
// @description  自动采集抖音来客线索大屏数据并同步到服务端
// @match        *://life.douyin.com/*
// @grant        GM_xmlhttpRequest
// @grant        GM_setValue
// @grant        GM_getValue
// @grant        GM_notification
// @connect      *
// @run-at       document-idle
// ==/UserScript==

(function() {
    'use strict';

    // ========== 配置区 ==========
    const CONFIG = {
        SERVER_URL: 'http://YOUR_SERVER_IP:8000',  // 服务器地址
        CHECK_INTERVAL: 60 * 1000,                  // 心跳检测间隔（1分钟）
        COLLECT_HOUR: 0,                             // 采集触发时间（0点）
        RETRY_COUNT: 3,                              // 重试次数
        RETRY_DELAY: 5000,                           // 重试间隔（5秒）
        PAGE_LOAD_TIMEOUT: 30000,                    // 页面加载超时（30秒）
        TAB_SWITCH_DELAY: 500,                       // Tab切换等待（500ms）
    };

    // ========== 选择器配置（集中定义，便于维护） ==========
    const SELECTORS = {
        prevButton: 'svg[data-log-name="上一场"]',
        nextButton: 'svg[data-log-name="下一场"]',
        disabledClass: 'cursor-not-allowed',
        enabledClass: 'cursor-pointer',
        timeRange: '[data-log-name="时间范围"]',     // 待真实DOM确认
        commentTab: '[data-log-name="评论"]',
        highIntentTab: '[data-log-name="高意向"]',
        // ... 更多选择器
    };

    // ========== 日志工具 ==========
    function log(msg, level = 'info') {
        const prefix = `[直播同步 ${new Date().toLocaleTimeString()}]`;
        console[level](`${prefix} ${msg}`);
    }

    // ========== 定时检测 ==========
    function startHeartbeat() {
        setInterval(() => {
            const now = new Date();
            const lastCollect = GM_getValue('last_collect_date', '');
            const today = now.toISOString().slice(0, 10);
            const yesterday = new Date(now - 86400000).toISOString().slice(0, 10);
            
            if (now.getHours() >= CONFIG.COLLECT_HOUR && lastCollect !== today) {
                log('触发采集流程');
                startCollection();
            }
        }, CONFIG.CHECK_INTERVAL);
    }

    // ========== 主入口 ==========
    log('脚本已加载');
    startHeartbeat();
})();
```

### 关联关系
- 脚本运行于浏览器 → 通过 HTTP 调用 `server/routers/api.py`
- `CONFIG.SERVER_URL` → 指向 FastAPI 服务端
- `GM_setValue/GM_getValue` → 持久化上次采集时间

### 验收条件
- [ ] 脚本可安装到 Tampermonkey 无报错
- [ ] 打开 life.douyin.com 后控制台输出"脚本已加载"
- [ ] 心跳检测每60秒执行一次
- [ ] 配置区所有选择器集中定义

---

## Task 3.2: 场次遍历逻辑

### 任务描述
实现场次时间解析、日期判断、上一场/下一场按钮点击、禁用检测、数据加载等待。

### 执行逻辑

#### 1. 场次遍历算法

```
1. 刷新页面 → 等待DOM稳定
2. 读取当前场次时间 "05-21 09：28～05-21 13：36"
3. 解析开播时间 → 判断日期：
   - 日期 > 昨天（今天或未来）→ 点"上一场"，回到步骤2
   - 日期 = 昨天 → 这就是目标场次之一
   - 日期 < 昨天（前天及更早）→ 点"下一场"进入昨天第一场
4. 开始采集当前场次
5. 采集完成 → 点"下一场"
6. 检查结束条件：
   - "下一场"按钮 class 包含 cursor-not-allowed → 结束
   - 下一场开播日期 = 今天 → 结束
7. 未结束 → 回到步骤4
```

### 伪代码

```javascript
// ========== 场次时间解析 ==========
function parseSessionTime(timeText) {
    // 输入: "05-21 09：28～05-21 13：36"
    // 输出: { start: "2026-05-21 09:28:00", end: "2026-05-21 13:36:00", startDate: "2026-05-21" }
    const [startStr, endStr] = timeText.split('～');
    const now = new Date();
    
    function parseHalf(str) {
        str = str.trim().replace(/：/g, ':');
        const match = str.match(/(\d{2})-(\d{2})\s+(\d{2}):(\d{2})/);
        if (!match) return null;
        let [_, month, day, hour, min] = match;
        let year = now.getFullYear();
        if (parseInt(month) > now.getMonth() + 1) year--;
        return `${year}-${month}-${day} ${hour}:${min}:00`;
    }
    
    return {
        start: parseHalf(startStr),
        end: parseHalf(endStr),
        startDate: parseHalf(startStr)?.slice(0, 10)
    };
}

// ========== 按钮操作 ==========
function clickButton(selector) {
    const btn = document.querySelector(selector);
    if (!btn) { log('未找到按钮: ' + selector, 'error'); return false; }
    if (btn.classList.contains(CONFIG_SELECTORS.disabledClass)) {
        log('按钮已禁用: ' + selector); return false;
    }
    btn.click();
    return true;
}

function isButtonDisabled(selector) {
    const btn = document.querySelector(selector);
    return !btn || btn.classList.contains('cursor-not-allowed');
}

// ========== 等待数据加载 ==========
function waitForDataLoad(timeout = CONFIG.PAGE_LOAD_TIMEOUT) {
    return new Promise((resolve, reject) => {
        const observer = new MutationObserver((mutations, obs) => {
            // 检测关键数据区域DOM变化稳定
            clearTimeout(timer);
            timer = setTimeout(() => {
                obs.disconnect();
                resolve();
            }, 1000); // DOM稳定1秒后视为加载完成
        });
        
        let timer = setTimeout(() => {
            observer.disconnect();
            reject(new Error('数据加载超时'));
        }, timeout);
        
        observer.observe(document.body, { childList: true, subtree: true });
    });
}

// ========== 时间文本提取函数 ==========
function getTimeRangeText() {
    const el = document.querySelector('[data-log-name="直播时间"]');
    if (!el) return "";
    return el.textContent.trim();
}

// ========== 场次遍历主函数 ==========
async function startCollection() {
    log('开始采集流程');
    const yesterday = getYesterdayStr(); // "2026-05-21"
    
    // Step 1: 定位到昨天的场次
    await navigateToYesterday(yesterday);
    
    // Step 2: 遍历昨天所有场次
    while (true) {
        const timeInfo = parseSessionTime(getTimeRangeText());
        if (timeInfo.startDate !== yesterday) break;
        
        // 防重复检查
        const exists = await checkSessionExists(timeInfo.start);
        if (!exists) {
            const data = await collectCurrentSession(timeInfo);
            data._version = '1.0.0'; // 版本协商字段，服务端据此判断兼容性
            await sendToServer(data);
        } else {
            log(`场次 ${timeInfo.start} 已存在，跳过`);
        }
        
        // 下一场
        if (isButtonDisabled(SELECTORS.nextButton)) break;
        clickButton(SELECTORS.nextButton);
        await waitForDataLoad();
    }
    
    GM_setValue('last_collect_date', new Date().toISOString().slice(0, 10));
    log('采集完成');
    GM_notification({ title: '直播数据同步', text: '采集完成' });
}
```

### 关联关系
- 依赖 `SELECTORS` 配置（Task 3.1 定义）
- 调用 `checkSessionExists()` → GET /api/session/check（Phase 2）
- 调用 `collectCurrentSession()` → Task 3.3~3.7
- 调用 `sendToServer()` → Task 3.8

### 验收条件
- [ ] 正确解析"05-21 09：28～05-21 13：36"格式
- [ ] 日期判断逻辑正确（今天/昨天/前天）
- [ ] 上一场/下一场按钮点击正常
- [ ] 禁用状态检测正确（cursor-not-allowed）
- [ ] MutationObserver等待数据加载，超时30秒自动跳过

---

## Task 3.3: 核心指标采集

### 任务描述
从线索大屏DOM中提取44个核心指标字段。

### 执行逻辑

#### DOM定位策略
- 优先使用 `data-log-name` 属性
- 其次匹配可见文本内容（如"曝光人数"旁边的数值）
- 不依赖动态class名（如 `V7dU-xxx`）

#### 采集字段（44个）

| 分类 | 字段 | DOM定位策略 |
|------|------|-------------|
| 流量 | 直播间曝光次数、曝光进入率、观看次数、累计观看人数、粉丝占比、>1分钟观看 | 通过标签文本定位相邻数值元素 |
| 留存 | 人均观看时长、粉丝停留、最高在线、平均在线、实时在线 | 同上 |
| 互动 | 互动次数/人数/率、评论次数/人数/率、点赞、分享、涨粉、关注率、粉丝团 | 同上 |
| 转化 | 留资人数、线索转化率、表单提交、填手机号、组件点击次数/率、商品点击 | 同上 |
| 成交 | 成交金额、营销订单数、订单人数、订单成本 | 同上 |
| 投放 | 营销消耗 | 同上 |
| 其他 | 打赏次数/金额 | 同上 |

### 伪代码

```javascript
// 3.2 虚拟滚动列表"边滚动边收集"策略（防止rc-virtual-list移除旧DOM导致遗漏）
async function collectAllVirtualListItems(container, extractFn) {
    const collected = new Map();
    let lastHeight = 0;
    while (true) {
        const visibleRows = container.querySelectorAll('[role="listitem"], [class*="row"], tr');
        for (const row of visibleRows) {
            const data = extractFn(row);
            if (data && data.id) collected.set(data.id, data);
        }
        container.scrollTop += 300;
        await new Promise(r => setTimeout(r, 300));
        if (container.scrollTop === lastHeight) break;
        lastHeight = container.scrollTop;
    }
    return Array.from(collected.values());
}

function collectMetrics() {
    const metrics = {};
    
    // 通用提取函数：通过标签文本找到对应的数值
    function getValueByLabel(labelText) {
        // 3.3 多层查找策略：data-log-name → 父容器向上查找 → 同级兄弟
        // 策略1: data-log-name
        const byAttr = document.querySelector(`[data-log-name="${labelText}"]`);
        if (byAttr) {
            const next = byAttr.nextElementSibling;
            if (next) return next.textContent.trim();
        }
        // 策略2: 文本匹配后向上查找父容器（2-3层），在容器内找数值元素
        const allEls = [...document.querySelectorAll('*')];
        for (const el of allEls) {
            if (el.childNodes.length === 1 && el.textContent.trim() === labelText) {
                let container = el.parentElement;
                for (let i = 0; i < 3; i++) {
                    if (!container) break;
                    const valueEl = container.querySelector('[class*="value"], [class*="num"], [class*="count"]');
                    if (valueEl && valueEl !== el) return valueEl.textContent.trim();
                    container = container.parentElement;
                }
                // 策略3: 同级下一个兄弟
                const next = el.nextElementSibling;
                if (next) return next.textContent.trim();
            }
        }
        return '--';
        const el = document.querySelector(`[data-log-name="${labelText}"]`);
        if (el) {
            const valueEl = el.closest('.metric-item')?.querySelector('.value')
                          || el.nextElementSibling;
            return valueEl?.textContent?.trim() || '--';
        }
        
        // 策略2: 文本内容匹配
        const allLabels = document.querySelectorAll('span, div, p');
        for (const label of allLabels) {
            if (label.textContent.trim() === labelText) {
                const sibling = label.nextElementSibling || label.parentElement?.querySelector('.value');
                return sibling?.textContent?.trim() || '--';
            }
        }
        return '--';
    }
    
    // 字段映射表（DOM标签文本 → JSON字段名）
    const FIELD_MAP = {
        '直播间曝光次数': 'exposure_count',
        '累计观看人数': 'cumulative_viewers',
        '曝光进入率': 'exposure_entry_rate',
        '直播间成交金额': 'gmv',
        '订单人数': 'order_count',
        '营销订单数': 'marketing_orders',
        '填手机号': 'phone_submits',
        '营销消耗': 'ad_spend',
        '全场景留资人数': 'total_leads',
        '订单成本': 'order_cost',
        '涨粉量': 'new_followers',
        '评论次数': 'comment_count',
        '评论人数': 'comment_users',
        '>1分钟观看次数': 'watch_gt_1min',
        '人均观看时长': 'avg_watch_duration',
        '粉丝停留时长': 'fan_stay_duration',
        '最高在线人数': 'max_online',
        '互动次数': 'interaction_count',
        '互动人数': 'interaction_users',
        '互动率': 'interaction_rate',
        '加粉丝团人数': 'fan_club_joins',
        '加团率': 'fan_club_rate',
        '风车房子点击次数': 'component_clicks',
        '点击率': 'click_rate',
        '打赏金额': 'gift_amount',
        '打赏次数': 'gift_count',
        '评论率': 'comment_rate',
        '线索转化率': 'lead_conversion_rate',
        '点赞率': 'like_rate',
        '点赞人数': 'like_users',
        '点赞次数': 'like_count',
        '商品曝光次数': 'product_exposure',
        '商品点击次数': 'product_clicks',
        '商品点击率': 'product_click_rate',
        '关注率': 'follow_rate',
        '分享次数': 'share_count',
        '分享人数': 'share_users',
        '粉丝占比': 'fan_ratio',
        '曝光次数': 'exposure_times',
        '直播间观看次数': 'view_count',
        '平均在线人数': 'avg_online',
        '实时在线人数': 'realtime_online',
    };
    
    for (const [label, field] of Object.entries(FIELD_MAP)) {
        metrics[field] = getValueByLabel(label);
    }
    
    return metrics;
}
```

### 验收条件
- [ ] 44个字段全部提取（与 `.data/` 样本CSV比对）
- [ ] 数值格式保持原始文本（"34,180"不在前端转换，服务端负责解析）
- [ ] 未找到的字段返回"--"而非undefined
- [ ] 不依赖动态class名

---

## Task 3.4: 线索列表采集

### 任务描述
从线索分析列表区域提取每条线索的9个字段，处理虚拟滚动。

### 伪代码

```javascript
async function collectLeads() {
    const leads = [];
    const container = findLeadListContainer();
    if (!container) return leads;
    
    let prevCount = 0;
    while (true) {
        // 滚动加载
        container.scrollTop = container.scrollHeight;
        await sleep(500);
        
        const rows = container.querySelectorAll('tr, [class*="row"]');
        if (rows.length === prevCount) break; // 不再增长
        prevCount = rows.length;
    }
    
    // 逐行提取
    const rows = container.querySelectorAll('tr, [class*="row"]');
    for (const row of rows) {
        const cells = row.querySelectorAll('td, [class*="cell"]');
        leads.push({
            lead_time: cells[0]?.textContent?.trim() || '',
            nickname: cells[1]?.textContent?.trim() || '',
            lead_id: cells[2]?.textContent?.trim() || '',
            phone_masked: cells[3]?.textContent?.trim() || '',
            product_name: cells[4]?.textContent?.trim() || '',
            city: cells[5]?.textContent?.trim() || '',
            path: cells[6]?.textContent?.trim() || '',
            tags: cells[7]?.textContent?.trim() || '',
            ad_account: cells[8]?.textContent?.trim() || '',
        });
    }
    return leads;
}
```

### 验收条件
- [ ] 线索数量与页面显示一致
- [ ] 9个字段全部提取
- [ ] 虚拟滚动场景下不遗漏数据
- [ ] 电话保持脱敏格式（`*******1956`）

---

## Task 3.5: 评论明细采集

### 任务描述
点击"评论"Tab，等待500ms，采集评论列表。

### 伪代码

```javascript
async function collectComments() {
    // 点击评论Tab
    const commentTab = document.querySelector(SELECTORS.commentTab);
    if (commentTab) {
        commentTab.click();
        await sleep(CONFIG.TAB_SWITCH_DELAY);
    }
    
    const comments = [];
    // 滚动加载全部评论（同线索列表逻辑）
    // 逐行提取: nickname, has_lead, content, comment_time
    // has_lead 判断: 行内是否有"已留资"标记
    return comments;
}
```

### 验收条件
- [ ] Tab切换后等待500ms再采集
- [ ] 评论数量与页面显示一致
- [ ] is_lead 正确识别留资/未留资状态

---

## Task 3.6: 高意向用户采集

### 任务描述
点击"高意向"Tab，等待500ms，采集高意向用户列表。

### 伪代码

```javascript
async function collectHighIntentUsers() {
    const tab = document.querySelector(SELECTORS.highIntentTab);
    if (tab) {
        tab.click();
        await sleep(CONFIG.TAB_SWITCH_DELAY);
    }
    
    const users = [];
    // 遍历用户卡片
    // 提取: nickname, avatar_url(img.src), comment_count, stay_duration, status
    return users;
}
```

### 验收条件
- [ ] 高意向用户数量与页面一致
- [ ] 头像URL正确提取（完整https链接）
- [ ] 状态字段正确（已留资/未留资/忽略）

---

## Task 3.7: 图片资源采集

### 任务描述
提取页面中用户头像等img标签的src URL。

### 伪代码

```javascript
function collectImages() {
    const images = [];
    document.querySelectorAll('img[src*="avatar"], img[src*="user"]').forEach(img => {
        if (img.src && !images.includes(img.src)) {
            images.push(img.src);
        }
    });
    return images;
}
```

### 验收条件
- [ ] 去重后返回URL列表
- [ ] URL格式完整（包含https://）

---

## Task 3.8: 数据发送+防重复

### 任务描述
调用API防重复检查，构造完整JSON，POST到服务端，实现3次重试和本地缓存补发。

### 伪代码

```javascript
async function checkSessionExists(startTime) {
    return new Promise((resolve) => {
        GM_xmlhttpRequest({
            method: 'GET',
            url: `${CONFIG.SERVER_URL}/api/session/check?start_time=${encodeURIComponent(startTime)}`,
            onload: (resp) => {
                const data = JSON.parse(resp.responseText);
                resolve(data.exists === true);
            },
            onerror: () => resolve(false) // 网络错误时假设不存在，尝试发送
        });
    });
}

// 3.4 数据完整性自检（DOM结构变化时及时发现，避免存入大量空数据）
function validateMetrics(metrics) {
    const total = Object.keys(metrics).length;
    const empty = Object.values(metrics).filter(v => v === '--' || v === null || v === '').length;
    const rate = (total - empty) / total;
    if (rate < 0.5) {
        log(`警告：指标完整率仅${(rate*100).toFixed(0)}%，可能DOM结构已变化`, 'warn');
        return false;
    }
    return true;
}

async function sendToServer(sessionData, retries = CONFIG.RETRY_COUNT) {
    return new Promise((resolve, reject) => {
        GM_xmlhttpRequest({
            method: 'POST',
            url: `${CONFIG.SERVER_URL}/api/session`,
            headers: { 'Content-Type': 'application/json' },
            data: JSON.stringify(sessionData),
            onload: (resp) => {
                const result = JSON.parse(resp.responseText);
                if (result.code === 0) {
                    log(`发送成功: session_id=${result.session_id}`);
                    resolve(result);
                } else {
                    log(`服务端返回错误: ${result.message}`, 'warn');
                    resolve(result); // 非网络错误不重试
                }
            },
            onerror: async (err) => {
                if (retries > 0) {
                    log(`发送失败，${retries}次重试后再试`, 'warn');
                    await sleep(CONFIG.RETRY_DELAY);
                    resolve(await sendToServer(sessionData, retries - 1));
                } else {
                    // 全部重试失败 → 存入本地缓存
                    log('全部重试失败，存入本地缓存', 'error');
                    const cache = JSON.parse(GM_getValue('pending_data', '[]'));
                    cache.push(sessionData);
                    GM_setValue('pending_data', JSON.stringify(cache));
                    reject(err);
                }
            }
        });
    });
}

// 补发缓存数据
async function retryCachedData() {
    const cache = JSON.parse(GM_getValue('pending_data', '[]'));
    if (cache.length === 0) return;
    log(`发现${cache.length}条缓存数据，开始补发`);
    const remaining = [];
    for (const data of cache) {
        try {
            await sendToServer(data);
        } catch {
            remaining.push(data);
        }
    }
    GM_setValue('pending_data', JSON.stringify(remaining));
}
```

### 异常恢复策略

| 异常场景 | 恢复策略 |
|----------|----------|
| 网络断开 | POST失败重试3次，间隔5秒；全部失败存入本地缓存 |
| 浏览器标签页休眠 | setInterval心跳检测，恢复后重新检查时间 |
| API返回错误 | 记录日志，跳过当前场次继续下一场 |
| 浏览器崩溃/重启 | GM_getValue读取上次采集日期，判断是否需补采 |

### 验收条件
- [ ] 防重复检查正确调用
- [ ] JSON数据结构与Phase 2 API要求一致
- [ ] 3次重试机制生效
- [ ] 重试全部失败后数据存入本地缓存
- [ ] 下次执行时自动补发缓存数据

---

## Task 3.9: 完整流程测试

### 任务描述
手动触发测试（不等0点），验证完整采集链路。

### 测试用例

| 测试项 | 操作 | 期望结果 |
|--------|------|----------|
| 手动触发 | 控制台调用 `startCollection()` | 开始采集流程 |
| 场次遍历 | 观察上一场/下一场点击 | 正确定位到昨天场次 |
| 指标采集 | 对比CSV和API接收数据 | 44字段完整 |
| 线索采集 | 对比CSV行数 | 数量一致 |
| 防重复 | 再次触发采集 | 已存在场次跳过 |
| 断网模拟 | 断网后触发 | 缓存数据，恢复后补发 |

### 验收条件
- [ ] 完整采集一天的所有场次（2-3场）
- [ ] 服务端数据库中数据完整正确
- [ ] 日志输出清晰（每步操作有记录）
- [ ] 手动触发测试通过后，测试代码清理

---

## Phase 3 整体验收清单

- [ ] 脚本安装到Tampermonkey无报错
- [ ] 打开 life.douyin.com 自动加载
- [ ] 配置区选择器集中定义，便于维护
- [ ] 场次遍历逻辑正确（定位昨天→逐场采集→结束检测）
- [ ] 44个核心指标全部采集（与CSV比对100%）
- [ ] 线索列表完整（含虚拟滚动处理）
- [ ] 评论明细完整
- [ ] 高意向用户完整
- [ ] 防重复机制生效
- [ ] 3次重试+本地缓存补发正常
- [ ] 桌面通知采集完成
