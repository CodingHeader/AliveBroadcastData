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
// @grant        unsafeWindow
// @run-at       document-idle
// ==/UserScript==

(function() {
    'use strict';

    // ========== 配置区 ==========
    const CONFIG = {
        SERVER_URL: 'https://jp.3.frp.one:35791',
        CHECK_INTERVAL: 60 * 1000,
        COLLECT_HOUR: 0,
        RETRY_COUNT: 3,
        RETRY_DELAY: 5000,
        PAGE_LOAD_TIMEOUT: 30000,
        TAB_SWITCH_DELAY: 500,
    };

    const SELECTORS = {
        prevButton: 'svg[data-log-name="上一场"]',
        nextButton: 'svg[data-log-name="下一场"]',
        disabledClass: 'cursor-not-allowed',
        enabledClass: 'cursor-pointer',
        commentTab: '[data-log-name="评论"]',
        highIntentTab: '[data-log-name="高意向"]',
        reviewTab: '[data-log-name="复盘表"]',
        leadsAnalysisTab: '[data-log-name="线索分析"]',
        leftButton: '[data-log-name="左侧按钮"]',
        rightButton: '[data-log-name="右侧按钮"]',
        downloadCSV: '[data-log-name="直播大屏下载CSV"]',
    };

    // ========== 日志工具 ==========
    function log(msg, level = 'info') {
        const prefix = `[直播同步 ${new Date().toLocaleTimeString()}]`;
        console[level](`${prefix} ${msg}`);
    }

    function sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    function getYesterdayStr() {
        const d = new Date();
        d.setDate(d.getDate() - 1);
        const y = d.getFullYear();
        const m = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        return `${y}-${m}-${day}`;
    }

    function getLocalDateStr(date) {
        const y = date.getFullYear();
        const m = String(date.getMonth() + 1).padStart(2, '0');
        const d = String(date.getDate()).padStart(2, '0');
        return `${y}-${m}-${d}`;
    }

    // ========== data-log-name → 数据库字段名映射（主指标24个）==========
    const DATA_LOG_MAP = {
        'live_show_count': 'exposure_count',
        'live_enter_rate': 'exposure_entry_rate',
        'live_watch_count': 'view_count',
        'live_watch_uv_by_room': 'cumulative_viewers',
        'live_single_watch_over_1m_count': 'watch_gt_1min',
        'live_avg_watch_duration_by_room': 'avg_watch_duration',
        'live_minute_max_watch_uv': 'max_online',
        'uv_realtime': 'realtime_online',
        'live_interaction_count': 'interaction_count',
        'live_interaction_rate': 'interaction_rate',
        'live_comment_count': 'comment_count',
        'live_watch_comment_rate': 'comment_rate',
        'live_like_count': 'like_count',
        'live_watch_like_rate': 'like_rate',
        'live_share_count': 'share_count',
        'live_fans_club_join_uv_by_room': 'fan_club_joins',
        'live_follow_uv_by_room': 'new_followers',
        'live_life_icon_click_count_all': 'component_clicks',
        'live_life_pay_order_gmv_all': 'gmv',
        'live_life_pay_order_uv_all': 'order_count',
        'live_life_product_click_count_all': 'product_clicks',
        'live_gift_count': 'gift_count',
        'stat_cost': 'ad_spend',
        'live_watch_share_rate': 'share_rate',
    };

    // ========== odometer数值提取 ==========
    function extractOdometerValue(container) {
        if (!container) return '--';
        const odometer = container.querySelector('.odometer-inside');
        if (!odometer) return container.textContent.trim() || '--';
        const parts = odometer.querySelectorAll('.odometer-value, .odometer-formatting-mark');
        let rawValue = '';
        for (const part of parts) {
            rawValue += part.textContent.trim();
        }
        const unitEls = container.querySelectorAll('.part-unit, .part-percentsign, [class*="part-"]');
        let unit = '';
        for (const el of unitEls) {
            unit += el.textContent.trim();
        }
        return (rawValue + unit) || '--';
    }

    // ========== 场次时间解析 ==========
    function parseSessionTime(timeText) {
        const [startStr, endStr] = timeText.split('\uff5e');
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

    function getTimeRangeText() {
        const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false);
        let node;
        while (node = walker.nextNode()) {
            const text = node.textContent.trim();
            if (text.includes('\uff5e') || text.includes('~')) {
                return text;
            }
        }
        return '';
    }

    // ========== 按钮操作 ==========
    function clickButton(selector) {
        const btn = document.querySelector(selector);
        if (!btn) { log('未找到按钮: ' + selector, 'error'); return false; }
        if (btn.classList.contains(SELECTORS.disabledClass)) {
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
            let timer;
            const observer = new MutationObserver(() => {
                clearTimeout(timer);
                timer = setTimeout(() => {
                    observer.disconnect();
                    resolve();
                }, 1000);
            });
            timer = setTimeout(() => {
                observer.disconnect();
                reject(new Error('数据加载超时'));
            }, timeout);
            observer.observe(document.body, { childList: true, subtree: true });
        });
    }

    // ========== 防重复检查（批量拉取，主流程使用）==========
    function getExistingSessions(dateStr) {
        return new Promise((resolve) => {
            GM_xmlhttpRequest({
                method: 'GET',
                url: `${CONFIG.SERVER_URL}/api/sessions/by-date?date=${encodeURIComponent(dateStr)}`,
                onload: (resp) => {
                    try {
                        const data = JSON.parse(resp.responseText);
                        if (data.code === 0 && Array.isArray(data.starts)) {
                            resolve(new Set(data.starts));
                        } else {
                            resolve(new Set());
                        }
                    } catch {
                        resolve(new Set());
                    }
                },
                onerror: () => {
                    log('服务端不可达，将采集所有场次', 'warn');
                    resolve(new Set());
                }
            });
        });
    }

    // 备用：单场检查（主流程已改用批量拉取）
    function checkSessionExists(startTime, retry = 1) {
        return new Promise((resolve) => {
            GM_xmlhttpRequest({
                method: 'GET',
                url: `${CONFIG.SERVER_URL}/api/session/check?start_time=${encodeURIComponent(startTime)}`,
                onload: (resp) => {
                    try {
                        const data = JSON.parse(resp.responseText);
                        resolve(data.exists === true ? 'exists' : 'not_exists');
                    } catch {
                        if (retry > 0) {
                            log('解析响应失败，重试...', 'warn');
                            setTimeout(() => {
                                checkSessionExists(startTime, retry - 1).then(resolve);
                            }, 3000);
                        } else {
                            resolve('error');
                        }
                    }
                },
                onerror: () => {
                    if (retry > 0) {
                        log('服务端不可达，3秒后重试...', 'warn');
                        setTimeout(() => {
                            checkSessionExists(startTime, retry - 1).then(resolve);
                        }, 3000);
                    } else {
                        log('服务端不可达，跳过该场次', 'error');
                        resolve('error');
                    }
                }
            });
        });
    }

    // ========== 核心指标采集 ==========
    async function collectMetrics() {
        const metrics = {};

        // 子指标中文标签映射（卡片底部小字段）
        const SUB_FIELD_MAP = {
            '粉丝停留': 'fan_stay_duration',
            '粉丝占比': 'fan_ratio',
            '营销订单数': 'marketing_orders',
            '填手机号': 'phone_submits',
            '看过': 'exposure_times',
            '互动人数': 'interaction_users',
            '加团率': 'fan_club_rate',
            '点击率': 'click_rate',
            '打赏金额': 'gift_amount',
            '线索转化率': 'lead_conversion_rate',
            '点赞人数': 'like_users',
            '商品曝光次数': 'product_exposure',
            '商品点击率': 'product_click_rate',
            '关注率': 'follow_rate',
            '分享人数': 'share_users',
            '平均在线人数': 'avg_online',
            '全场景留资人数': 'total_leads',
            '订单成本': 'order_cost',
            '线索成本': 'lead_cost',
        };

        function collectPageMetrics() {
            for (const [logName, fieldName] of Object.entries(DATA_LOG_MAP)) {
                if (metrics[fieldName] && metrics[fieldName] !== '--') continue;
                const card = document.querySelector(`[data-log-name="${logName}"]`);
                if (!card) continue;
                // 主数值：卡片内第一个odometer
                const mainValueEl = card.querySelector('.odometer') || card.querySelector('[class*="odometer"]');
                metrics[fieldName] = extractOdometerValue(mainValueEl);

                // 子指标：在卡片内搜索中文标签
                const cardTexts = card.querySelectorAll('span, div, p');
                for (const el of cardTexts) {
                    const text = el.textContent.trim();
                    if (SUB_FIELD_MAP[text]) {
                        const sibling = el.nextElementSibling || el.parentElement?.querySelector('[class*="odometer"]');
                        if (sibling) {
                            const val = extractOdometerValue(sibling);
                            if (val !== '--') metrics[SUB_FIELD_MAP[text]] = val;
                        }
                    }
                }
            }
        }

        // 采集第1页
        collectPageMetrics();

        // 翻到第2页采集
        const rightBtn = document.querySelector(SELECTORS.rightButton);
        if (rightBtn && !rightBtn.classList.contains(SELECTORS.disabledClass)) {
            rightBtn.click();
            await sleep(500);
            collectPageMetrics();
            // 返回第1页
            const leftBtn = document.querySelector(SELECTORS.leftButton);
            if (leftBtn && !leftBtn.classList.contains(SELECTORS.disabledClass)) {
                leftBtn.click();
                await sleep(500);
            }
        }

        // fallback: 全局搜索子指标
        for (const [labelText, fieldName] of Object.entries(SUB_FIELD_MAP)) {
            if (metrics[fieldName] && metrics[fieldName] !== '--') continue;
            const allLabels = document.querySelectorAll('span, div, p');
            for (const label of allLabels) {
                if (label.textContent.trim() === labelText) {
                    const sibling = label.nextElementSibling || label.parentElement?.querySelector('[class*="odometer"]');
                    if (sibling) {
                        metrics[fieldName] = extractOdometerValue(sibling);
                    }
                    break;
                }
            }
        }

        return metrics;
    }

    // ========== 线索列表采集 ==========
    async function collectLeads() {
        const tab = document.querySelector(SELECTORS.leadsAnalysisTab);
        if (tab) {
            tab.click();
            await sleep(CONFIG.TAB_SWITCH_DELAY + 500);
        }
        await sleep(1000);

        const leads = [];
        const seen = new Set();

        // 定位列表容器（通过"留资时间"列头）
        const allSpans = document.querySelectorAll('span');
        let listContainer = null;
        for (const span of allSpans) {
            if (span.textContent.trim() === '留资时间') {
                listContainer = span.closest('[class*="list"], [class*="table"], [class*="container"]') || span.parentElement?.parentElement;
                break;
            }
        }
        if (!listContainer) {
            listContainer = document.querySelector('[class*="virtual-list"], [class*="rc-virtual-list"], [class*="scroll"]');
        }
        if (!listContainer) {
            return collectLeadsLegacy();
        }

        // 虚拟滚动加载
        let prevCount = 0;
        for (let i = 0; i < 15; i++) {
            listContainer.scrollTop = listContainer.scrollHeight;
            await sleep(500);
            const rows = listContainer.querySelectorAll('[style*="translateY"]');
            if (rows.length === prevCount && prevCount > 0) break;
            prevCount = rows.length;
        }

        // 采集：优先translateY行，回退到class包含row
        let rows = listContainer.querySelectorAll('[style*="translateY"]');
        if (rows.length === 0) {
            rows = listContainer.querySelectorAll('[class*="row"], [class*="item"]');
        }
        for (const row of rows) {
            const cells = row.querySelectorAll('div, td');
            if (cells.length < 2) continue;
            const lead_id = cells[2]?.textContent?.trim() || '';
            if (seen.has(lead_id) || !lead_id) continue;
            seen.add(lead_id);
            leads.push({
                lead_time: cells[0]?.textContent?.trim() || '',
                nickname: cells[1]?.textContent?.trim() || '',
                lead_id,
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

    // 线索列表采集（旧逻辑回退）
    function collectLeadsLegacy() {
        const leads = [];
        const container = document.querySelector('table') || document.querySelector('[class*="table"]');
        if (!container) return leads;
        const rows = container.querySelectorAll('tr, [class*="row"]');
        for (const row of rows) {
            const cells = row.querySelectorAll('td, [class*="cell"]');
            if (cells.length >= 2) {
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
        }
        return leads;
    }

    // ========== 评论明细采集 ==========
    async function collectComments() {
        const commentTab = document.querySelector(SELECTORS.commentTab);
        if (commentTab) {
            commentTab.click();
            await sleep(CONFIG.TAB_SWITCH_DELAY);
        }
        await sleep(1000);

        const comments = [];
        const seen = new Set();

        // 找到评论列表容器（通过"昵称"列头定位）
        const allSpans = document.querySelectorAll('span');
        let listContainer = null;
        for (const span of allSpans) {
            if (span.textContent.trim() === '昵称') {
                listContainer = span.closest('[class*="list"], [class*="table"], [class*="container"]') || span.parentElement?.parentElement;
                break;
            }
        }
        if (!listContainer) {
            listContainer = document.querySelector('[class*="virtual-list"], [class*="rc-virtual-list"], [class*="scroll"]');
        }
        if (!listContainer) return comments;

        // 虚拟滚动采集：滚动到底部加载全部
        let prevCount = 0;
        for (let i = 0; i < 15; i++) {
            listContainer.scrollTop = listContainer.scrollHeight;
            await sleep(500);
            let rows = listContainer.querySelectorAll('[style*="translateY"]');
            if (rows.length === 0) {
                rows = listContainer.querySelectorAll('[class*="row"], [class*="item"]');
            }
            if (rows.length === prevCount && prevCount > 0) break;
            prevCount = rows.length;
        }

        // 采集：div虚拟滚动行默认顺序（昵称/是否留资/评论内容/评论时间/操作）
        let rows = listContainer.querySelectorAll('[style*="translateY"]');
        if (rows.length === 0) {
            rows = listContainer.querySelectorAll('[class*="row"], [class*="item"]');
        }
        for (const row of rows) {
            const cells = row.querySelectorAll('div, td');
            if (cells.length >= 4) {
                const nickname = cells[0]?.textContent?.trim().replace(/\s*avatar\s*/i, '') || '';
                const isLeadText = cells[1]?.textContent?.trim() || '';
                const content = cells[2]?.querySelector('p')?.textContent?.trim() || cells[2]?.textContent?.trim() || '';
                const commentTime = cells[3]?.textContent?.trim() || '';

                const key = nickname + commentTime;
                if (seen.has(key) || !nickname) continue;
                seen.add(key);

                comments.push({
                    nickname,
                    has_lead: isLeadText.includes('已留资'),
                    content: content.length > 200 ? content.slice(0, 200) : content,
                    comment_time: commentTime
                });
            }
        }
        return comments;
    }

    // ========== 高意向用户采集 ==========
    async function collectHighIntentUsers() {
        const tab = document.querySelector(SELECTORS.highIntentTab);
        if (tab) {
            tab.click();
            await sleep(CONFIG.TAB_SWITCH_DELAY);
        }
        await sleep(1000);
        
        const users = [];
        
        // 找到高意向列表容器
        const allSpans = document.querySelectorAll('span');
        let listContainer = null;
        for (const span of allSpans) {
            if (span.textContent.trim().includes('高意向')) {
                listContainer = span.closest('[class*="list"], [class*="container"]') || span.parentElement?.parentElement;
                break;
            }
        }
        if (!listContainer) {
            listContainer = document.querySelector('[role="list"], [class*="virtual-list"]');
        }
        if (!listContainer) return users;
        
        // 采集用户卡片
        const cards = listContainer.querySelectorAll('[role="listitem"], [class*="card"], [class*="user"], [class*="item"]');
        for (const card of cards) {
            const img = card.querySelector('img');
            const nicknameEl = card.querySelector('p, [class*="name"]');
            const nickname = nicknameEl?.textContent?.trim().replace(/\s*avatar\s*/i, '') || img?.alt?.replace(/\s*avatar\s*/i, '') || '';
            
            // 提取评论数和停留时长
            const allTexts = card.querySelectorAll('p, span');
            let commentCount = 0;
            let stayDuration = '';
            let status = '未留资';
            
            for (let i = 0; i < allTexts.length - 1; i++) {
                const text = allTexts[i].textContent.trim();
                const nextText = allTexts[i + 1].textContent.trim();
                if (text === '评论数' || text.includes('评论')) {
                    const num = nextText.match(/\d+/);
                    commentCount = num ? parseInt(num[0]) : 0;
                }
                if (text === '停留时长' || text.includes('停留')) {
                    stayDuration = nextText;
                }
            }
            
            // 状态判断
            if (card.textContent.includes('已留资')) status = '已留资';
            else if (card.textContent.includes('忽略')) status = '忽略';
            
            if (nickname && nickname.length > 0) {
                users.push({
                    nickname,
                    avatar_url: img?.src || '',
                    comment_count: commentCount,
                    stay_duration: stayDuration,
                    status
                });
            }
        }
        return users;
    }

    // ========== 复盘表采集 ==========
    async function collectReviewData() {
        const tab = document.querySelector(SELECTORS.reviewTab);
        if (!tab) return null;
        tab.click();
        await sleep(CONFIG.TAB_SWITCH_DELAY + 500);
        // 复盘表DOM结构待根据实际页面完善，当前返回空对象占位
        return {};
    }

    // ========== 数据完整性自检 ==========
    function validateMetrics(metrics) {
        const totalFields = Object.keys(metrics).length;
        let emptyCount = 0;
        for (const [key, value] of Object.entries(metrics)) {
            if (value === '--' || value === null || value === undefined || value === '') {
                emptyCount++;
            }
        }
        const completeness = ((totalFields - emptyCount) / totalFields * 100).toFixed(1);
        log(`指标完整率: ${completeness}% (${totalFields - emptyCount}/${totalFields})`);
        
        if (completeness < 50) {
            log('❌ 完整率过低，跳过该场次', 'error');
            sendAlert('采集异常', `指标完整率仅${completeness}%，DOM可能已变化`);
            return false;
        }
        if (completeness < 70) {
            log('️ 完整率偏低，可能DOM结构已变化', 'warn');
        }
        return true;
    }

    // ========== 数据发送 ==========
    async function sendToServer(sessionData, retries = CONFIG.RETRY_COUNT) {
        return new Promise((resolve, reject) => {
            GM_xmlhttpRequest({
                method: 'POST',
                url: `${CONFIG.SERVER_URL}/api/session`,
                headers: { 'Content-Type': 'application/json' },
                data: JSON.stringify(sessionData),
                onload: (resp) => {
                    try {
                        const result = JSON.parse(resp.responseText);
                        if (result.code === 0) {
                            log(`发送成功: session_id=${result.session_id}`);
                            resolve(result);
                        } else {
                            log(`服务端返回错误: ${result.message}`, 'warn');
                            resolve(result);
                        }
                    } catch { reject(new Error('解析响应失败')); }
                },
                onerror: async () => {
                    if (retries > 0) {
                        log(`发送失败，${retries}次重试`, 'warn');
                        await sleep(CONFIG.RETRY_DELAY);
                        resolve(await sendToServer(sessionData, retries - 1));
                    } else {
                        log('全部重试失败，存入本地缓存', 'error');
                        const cache = JSON.parse(GM_getValue('pending_data', '[]'));
                        cache.push(sessionData);
                        GM_setValue('pending_data', JSON.stringify(cache));
                        reject(new Error('发送失败'));
                    }
                }
            });
        });
    }

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

    // ========== 异常告警推送 ==========
    function sendAlert(type, message, sessionTime) {
        GM_xmlhttpRequest({
            method: 'POST',
            url: `${CONFIG.SERVER_URL}/api/alert`,
            headers: { 'Content-Type': 'application/json' },
            data: JSON.stringify({
                type, message,
                session_time: sessionTime || '',
                timestamp: new Date().toLocaleString('zh-CN')
            }),
            onload: () => log(`告警已发送: ${type}`),
            onerror: () => log('告警发送失败', 'warn')
        });
    }

    // ========== 采集当前场次 ==========
    async function collectCurrentSession(timeInfo) {
        log(`采集场次: ${timeInfo.start}`);
        const metrics = await collectMetrics();

        // 数据完整性自检
        if (!validateMetrics(metrics)) {
            return null;
        }

        const review = await collectReviewData();
        const leads = await collectLeads();
        const comments = await collectComments();
        const highIntentUsers = await collectHighIntentUsers();

        return {
            version: "1.0",
            start_time: timeInfo.start,
            end_time: timeInfo.end,
            metrics, review, leads, comments, high_intent_users: highIntentUsers
        };
    }

    // ========== 定位到昨天 ==========
    async function navigateToYesterday(yesterday) {
        log('定位到昨天的场次...');
        for (let i = 0; i < 50; i++) {
            const timeInfo = parseSessionTime(getTimeRangeText());
            if (!timeInfo.startDate) {
                log('无法解析场次时间，等待加载...', 'warn');
                await sleep(2000);
                continue;
            }
            if (timeInfo.startDate === yesterday) {
                log('已定位到昨天');
                return true;
            }
            if (timeInfo.startDate > yesterday) {
                clickButton(SELECTORS.prevButton);
            } else {
                clickButton(SELECTORS.nextButton);
            }
            await sleep(2000);
        }
        log('定位昨天超时', 'error');
        return false;
    }

    // ========== 主采集流程 ==========
    async function startCollection() {
        log('开始采集流程');
        const yesterday = getYesterdayStr();

        await retryCachedData();

        const existingStarts = await getExistingSessions(yesterday);
        log(`服务端已有 ${existingStarts.size} 个昨日场次`);

        if (!await navigateToYesterday(yesterday)) {
            log('未能定位到昨天场次', 'error');
            return;
        }

        let collected = 0;
        let skipped = 0;
        let failed = 0;

        while (true) {
            const timeInfo = parseSessionTime(getTimeRangeText());
            if (!timeInfo.startDate || timeInfo.startDate !== yesterday) break;

            if (existingStarts.has(timeInfo.start)) {
                log(`场次 ${timeInfo.start} 已存在，跳过`);
                skipped++;
            } else {
                try {
                    const data = await collectCurrentSession(timeInfo);
                    if (data) {
                        await sendToServer(data);
                        collected++;
                        log(` 数据摘要: 消耗¥${data.metrics.ad_spend||'--'} | 留资${data.metrics.total_leads||'--'} | 线索${data.leads.length}条`);
                    } else {
                        failed++;
                    }
                } catch (e) {
                    log(`采集失败: ${e.message}`, 'error');
                    failed++;
                }
            }

            if (isButtonDisabled(SELECTORS.nextButton)) break;
            clickButton(SELECTORS.nextButton);
            try {
                await waitForDataLoad();
            } catch {
                log('数据加载超时，继续下一场', 'warn');
            }
            await sleep(1000);
        }

        GM_setValue('last_collect_date', getLocalDateStr(new Date()));
        log(`采集完成: 新增${collected}场, 跳过${skipped}场`);
        GM_notification({ title: '直播数据同步', text: `采集完成: 新增${collected}场` });
        if (failed > 0) {
            sendAlert('采集失败', `昨日采集完成：新增${collected}场，跳过${skipped}场，失败${failed}场`);
        }
    }

    // ========== 定时检测 ==========
    function startHeartbeat() {
        setInterval(() => {
            const now = new Date();
            const lastCollect = GM_getValue('last_collect_date', '');
            const today = getLocalDateStr(now);

            if (now.getHours() >= CONFIG.COLLECT_HOUR && lastCollect !== today) {
                log('触发采集流程，页面将自动刷新');
                GM_setValue('pending_collect', 'true');
                location.reload();
            }
        }, CONFIG.CHECK_INTERVAL);
    }

    // ========== 主入口 ==========
    log('脚本已加载');
    const pending = GM_getValue('pending_collect', 'false');
    if (pending === 'true') {
        GM_setValue('pending_collect', 'false');
        log('页面已刷新，3秒后开始采集');
        setTimeout(() => startCollection(), 3000);
    } else {
        startHeartbeat();
    }

    // 暴露给控制台手动触发
    unsafeWindow.startCollection = startCollection;
})();
