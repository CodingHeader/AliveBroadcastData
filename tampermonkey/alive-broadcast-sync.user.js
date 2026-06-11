// ==UserScript==
// @name         抖音直播数据同步
// @namespace    alive-broadcast-data
// @version      1.5.0
// @description  自动采集抖音来客线索大屏/评论洞察分析数据并同步到服务端
// @match        *://life.douyin.com/p/liteapp/leads_analysis/live-screen*
// @match        *://life.douyin.com/p/liteapp/leads_analysis/live-comment*
// @grant        GM_xmlhttpRequest
// @grant        GM_setValue
// @grant        GM_getValue
// @grant        GM_notification
// @grant        GM_registerMenuCommand
// @connect      *
// @grant        unsafeWindow
// @run-at       document-idle
// ==/UserScript==

(function() {
    'use strict';

    // ========== 手动采集（控制台执行） ==========
    // window.startCollection()
    // 直播大屏采集: startCollection()
    // 评论洞察采集: startCollection()
    // ==========================================

    // ========== 后台标签页伪装（防止SPA检测到后台跳过渲染）==========
    try {
        Object.defineProperty(document, 'hidden', { get: () => false, configurable: true });
        Object.defineProperty(document, 'visibilityState', { get: () => 'visible', configurable: true });
    } catch (e) { /* 某些环境不支持覆盖，忽略 */ }

    // ========== 配置区 ==========
    const CONFIG = {
        SERVER_URL: 'http://127.0.0.1:12306',
        ACCOUNT_ID: GM_getValue('account_id', '') || '',  // 广告账户ID，在脚本菜单中设置
        CHECK_INTERVAL: 60 * 1000,
        COLLECT_HOUR: 1,       // 凌晨1点启动自动采集
        RETRY_COUNT: 3,
        RETRY_DELAY: 5000,
        PAGE_LOAD_TIMEOUT: 8000,   // 数据加载等待超时（原30s，实时数据页1s静默永远不成立）
        TAB_SWITCH_DELAY: 3000,    // Tab切换后等待数据加载（毫秒）
        MAX_DAILY_ATTEMPTS: 3,  // 每天自动采集最大尝试次数（含失败）
        COLLECT_DAYS: 1,      // 采集天数: 1=昨天, 30=最近30天, 数字越大耗时越长
        NAVIGATION_TIMEOUT: 60000, // goToLatest/navigateToDate 绝对超时（毫秒）
        MAX_NAVIGATION_STEPS: 50,  // goToLatest 最大翻页步数（原500，最坏4.2h）
        HTTP_TIMEOUT: 15000,       // GM_xmlhttpRequest 统一超时（毫秒）
    };

    // ========== 脚本菜单：设置直播告账户ID ==========
    GM_registerMenuCommand('设置直播账户ID', () => {
        const current = GM_getValue('account_id', '');
        const val = prompt('请输入直播账户ID（对应后台"直播告账户"中的ID）：', current);
        if (val !== null) {
            GM_setValue('account_id', val.trim());
            CONFIG.ACCOUNT_ID = val.trim();
            alert('账户ID已设置为: ' + (val.trim() || '(空)'));
        }
    });

    // ========== 并发保护锁 ==========
    let isCollecting = false;

    // ========== 页面类型检测 ==========
    function getPageType() {
        const href = location.href;
        if (href.includes('/leads_analysis/live-comment')) return 'comment-insight';
        if (href.includes('/leads_analysis/live-screen')) return 'live-screen';
        return 'unknown';
    }

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
        const prefix = `[直播同步]`;
        console[level](`${prefix} ${msg}`);
    }

    function sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    // 等待odometer动画完成（轮询检测，最多2秒）
    async function waitForOdometer() {
        const deadline = Date.now() + 2000;
        while (Date.now() < deadline) {
            const animating = document.querySelector('.odometer-animating, .odometer-animating-up, .odometer-animating-down');
            if (!animating) break;
            await sleep(200);
        }
        await sleep(300); // 额外等待值稳定
    }

    function getYesterdayStr() {
        const d = new Date();
        d.setDate(d.getDate() - 1);
        const y = d.getFullYear();
        const m = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        return `${y}-${m}-${day}`;
    }

    function getDaysList(days) {
        const result = [];
        for (let i = 1; i <= days; i++) {
            const d = new Date();
            d.setDate(d.getDate() - i);
            result.push(getLocalDateStr(d));
        }
        return result;
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
    // 从拼接值中提取首个有效数值（限位小数，避免贪心匹配）
    function extractFirstValidNumber(str) {
        // 优先匹配1-2位小数的数值（如 0.72, 12.5, 0.8%）
        const m = str.match(/-?\d+\.\d{1,2}/);
        if (m) return m[0];
        // 纯整数拼接（如 248284）无法自动拆分，取首个连续数字
        const m2 = str.match(/-?\d+/);
        return m2 ? m2[0] : null;
    }

    function extractOdometerValue(container) {
        if (!container) return '--';
        const odometer = container.querySelector('.odometer-inside');
        if (!odometer) {
            const raw = container.textContent.trim() || '--';
            // 检测拼接值：含多个"."或明显异常长（odometer动画过渡值被textContent一次抓取）
            if (raw !== '--' && raw.length > 10) {
                const first = extractFirstValidNumber(raw);
                if (first) return first;
            }
            return raw;
        }
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
        const result = (rawValue + unit) || '--';
        // 检测拼接值
        if (result !== '--' && result.length > 10) {
            const first = extractFirstValidNumber(result);
            if (first) return first;
        }
        return result;
    }

    // ========== 场次时间解析 ==========
    function parseSessionTime(timeText, referenceDate) {
        if (!timeText) {
            return { start: null, end: null, startDate: null, isLive: false };
        }
        // 支持全角～和半角~两种分隔符
        const parts = timeText.split(/[\uff5e~]/);
        const startStr = parts[0] || '';
        const endStr = parts[1] || '';

        // 从 referenceDate 提取参考年份（用于跨年推断）
        const refYear = referenceDate ? parseInt(referenceDate.slice(0, 4)) : new Date().getFullYear();
        const refMonth = referenceDate ? parseInt(referenceDate.slice(5, 7)) : (new Date().getMonth() + 1);

        function parseHalf(str) {
            if (!str) return null;
            str = str.trim().replace(/：/g, ':');
            if (str === '--' || str === '-') return null;
            const match = str.match(/(\d{2})-(\d{2})\s+(\d{2}):(\d{2})(?::(\d{2}))?/);
            if (!match) return null;
            let [_, month, day, hour, min, sec] = match;
            month = parseInt(month);
            day = parseInt(day);

            // 基于 referenceDate 推断年份：选择使 |场次日期 - referenceDate| 最小的年份
            const candidates = [refYear];
            if (month > refMonth || (month === refMonth && day > parseInt(referenceDate?.slice(8, 10) || '0'))) {
                candidates.push(refYear - 1);
            } else {
                candidates.push(refYear + 1);
            }
            // 额外处理年初/年末跨年场景
            if (refMonth <= 2 && month >= 11) candidates.push(refYear - 1);
            if (refMonth >= 11 && month <= 2) candidates.push(refYear + 1);

            let bestYear = refYear;
            let minDiff = Infinity;
            for (const y of [...new Set(candidates)]) {
                const candidateDate = new Date(y, month - 1, day);
                const refDateObj = referenceDate ? new Date(referenceDate) : new Date();
                const diff = Math.abs(candidateDate - refDateObj);
                if (diff < minDiff) {
                    minDiff = diff;
                    bestYear = y;
                }
            }
            return `${bestYear}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')} ${hour}:${min}:${sec || '00'}`;
        }

        const start = parseHalf(startStr);
        const end = parseHalf(endStr);
        return {
            start,
            end,
            startDate: start?.slice(0, 10) || null,
            isLive: !end && (!endStr || endStr.trim() === '' || endStr.trim() === '--' || endStr.trim() === '-')
        };
    }

    function getTimeRangeText() {
        // 策略1: 在场次信息区域搜索（缩小范围避免误匹配）
        const sessionInfoArea = document.querySelector('[class*="session"], [class*="time-range"], [class*="header-info"]');
        if (sessionInfoArea) {
            const spans = sessionInfoArea.querySelectorAll('span');
            for (const span of spans) {
                const text = span.textContent.trim();
                if (text.match(/\d{2}-\d{2}\s+\d{2}:\d{2}/) && (text.includes('~') || text.includes('\uff5e'))) {
                    return text;
                }
            }
        }
        // 策略2: 全局querySelector（fallback）
        const spans = document.querySelectorAll('span');
        for (const span of spans) {
            const text = span.textContent.trim();
            if (text.match(/\d{2}-\d{2}\s+\d{2}:\d{2}/) && (text.includes('~') || text.includes('\uff5e'))) {
                return text;
            }
        }
        // 策略3: TreeWalker遍历文本节点（最后备用）
        const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false);
        let node;
        while (node = walker.nextNode()) {
            const text = node.textContent.trim();
            if (text.match(/\d{2}-\d{2}\s+\d{2}:\d{2}/) && (text.includes('~') || text.includes('\uff5e'))) {
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
        btn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
        return true;
    }

    // 按钮状态三态返回：null=不存在, true=禁用, false=可用
    function isButtonDisabled(selector) {
        const btn = document.querySelector(selector);
        if (!btn) return null;
        return btn.classList.contains('cursor-not-allowed');
    }

    // ========== 等待数据加载 ==========
    // 重构：观察范围从document.body缩小到数据卡片区域，避免实时在线人数等高频更新导致静默条件永远不成立
    function waitForDataLoad(timeout = CONFIG.PAGE_LOAD_TIMEOUT, targetSelector = null) {
        return new Promise((resolve, reject) => {
            // 确定观察目标：优先指定容器，否则找[data-log-name]卡片区域，最后fallback到body
            let observeTarget = null;
            if (targetSelector) {
                observeTarget = document.querySelector(targetSelector);
            }
            if (!observeTarget) {
                // 尝试找包含所有数据卡片的最近公共祖先
                const firstCard = document.querySelector('[data-log-name]');
                if (firstCard) {
                    observeTarget = firstCard.parentElement;
                    // 向上找到包含多个卡片的容器（至少2层）
                    if (observeTarget && observeTarget.parentElement &&
                        observeTarget.parentElement.querySelectorAll('[data-log-name]').length > 1) {
                        observeTarget = observeTarget.parentElement;
                    }
                }
            }
            if (!observeTarget) observeTarget = document.body;

            let settled = false;
            let hasMutated = false;
            const SILENCE_MS = 500; // 静默阈值：500ms内无DOM变化视为加载完成

            function finish(result) {
                if (settled) return;
                settled = true;
                observer.disconnect();
                clearTimeout(silenceTimer);
                clearTimeout(absoluteTimer);
                if (result === 'ok') resolve();
                else reject(new Error('数据加载超时'));
            }

            let silenceTimer;
            const observer = new MutationObserver(() => {
                hasMutated = true;
                clearTimeout(silenceTimer);
                silenceTimer = setTimeout(() => finish('ok'), SILENCE_MS);
            });

            // 绝对超时
            const absoluteTimer = setTimeout(() => finish('timeout'), timeout);

            observer.observe(observeTarget, { childList: true, subtree: true });

            // 无事件快速通道：如果500ms内无任何mutation，说明DOM已稳定或目标容器不变
            setTimeout(() => {
                if (!hasMutated && !settled) finish('ok');
            }, SILENCE_MS);
        });
    }

    // ========== 等待SPA数据就绪（轮询关键DOM元素）==========
    async function waitForPageReady(timeout = 60000) {
        const deadline = Date.now() + timeout;
        const checkInterval = 2000;
        log(`等待页面数据就绪（超时${timeout / 1000}秒）...`);
        while (Date.now() < deadline) {
            const dataCard = document.querySelector('[data-log-name]');
            const navBtn = document.querySelector(SELECTORS.prevButton) || document.querySelector(SELECTORS.nextButton);
            if (dataCard && navBtn) {
                log('页面数据已就绪');
                await sleep(500);
                return true;
            }
            await sleep(checkInterval);
        }
        log(`页面数据${timeout / 1000}秒内未就绪，放弃本次采集`, 'error');
        return false;
    }

    // ========== 防重复检查（批量拉取，主流程使用）==========
    function getExistingSessions(dateStr) {
        return new Promise((resolve) => {
            GM_xmlhttpRequest({
                method: 'GET',
                url: `${CONFIG.SERVER_URL}/api/sessions/by-date?date=${encodeURIComponent(dateStr)}`,
                timeout: CONFIG.HTTP_TIMEOUT,
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
                },
                ontimeout: () => {
                    log(`获取已有场次超时(${CONFIG.HTTP_TIMEOUT/1000}s)，将采集所有场次`, 'warn');
                    resolve(new Set());
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
                        // 限制在标签所在卡片范围内搜索value，避免跨卡片误抓
                        const scope = el.closest('[data-log-name]') || el.parentElement;
                        const sibling = scope ? scope.querySelector('[class*="odometer"]') : el.nextElementSibling;
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
            // 等待odometer动画完成
            await waitForOdometer();
            collectPageMetrics();
            // 返回第1页
            const leftBtn = document.querySelector(SELECTORS.leftButton);
            if (leftBtn && !leftBtn.classList.contains(SELECTORS.disabledClass)) {
                leftBtn.click();
                await waitForOdometer();
            }
        }

        // fallback: 全局搜索子指标
        for (const [labelText, fieldName] of Object.entries(SUB_FIELD_MAP)) {
            if (metrics[fieldName] && metrics[fieldName] !== '--') continue;
            const allLabels = document.querySelectorAll('span, div, p');
            for (const label of allLabels) {
                if (label.textContent.trim() === labelText) {
                    const scope = label.closest('[data-log-name]') || label.parentElement;
                    const sibling = scope ? scope.querySelector('[class*="odometer"]') : label.nextElementSibling;
                    if (sibling) {
                        metrics[fieldName] = extractOdometerValue(sibling);
                    }
                    break;
                }
            }
        }

        return metrics;
    }

    // ========== 通用滚动采集函数 ==========
    // 边滚边采，用 Set 去重，连续2次无新行时退出
    async function scrollAndCollect(options) {
        const {
            container,          // 滚动容器元素
            rowSelector,        // 行选择器
            parseFn,            // 行解析函数 → 对象 | null
            dedupKeyFn,         // 去重键函数 → string
            maxScrolls = 50,    // 最大滚动次数
            scrollDelay = 600,  // 每次滚动后等待ms
            label = '数据',     // 日志标签
        } = options;

        if (!container) return [];
        const results = [];
        const seen = new Set();
        let noNewCount = 0;

        for (let i = 0; i < maxScrolls; i++) {
            // 采集当前可见行
            const rows = container.querySelectorAll(rowSelector);
            let newInRound = 0;
            for (const row of rows) {
                const item = parseFn(row);
                if (!item) continue;
                const key = dedupKeyFn(item);
                if (!seen.has(key)) {
                    seen.add(key);
                    results.push(item);
                    newInRound++;
                }
            }

            if (newInRound === 0) {
                noNewCount++;
                if (noNewCount >= 2) break; // 连续2次无新行，退出
            } else {
                noNewCount = 0;
            }

            // 检测"加载更多"/"下一页"按钮
            const loadMoreBtn = container.querySelector('[data-log-name="加载更多"], [class*="load-more"], [class*="loadmore"]') ||
                document.querySelector('[data-log-name="加载更多"], [class*="load-more"], [class*="loadmore"]');
            if (loadMoreBtn && !loadMoreBtn.classList.contains('cursor-not-allowed')) {
                loadMoreBtn.click();
                await sleep(scrollDelay);
                continue;
            }

            // 检测分页器"下一页"按钮
            const nextPagBtn = container.querySelector('[class*="next"]:not([class*="cursor-not-allowed"])') ||
                container.querySelector('[aria-label="Next Page"]');
            if (nextPagBtn) {
                nextPagBtn.click();
                await sleep(scrollDelay);
                continue;
            }

            // 虚拟滚动：向下滚动容器
            const prevScrollTop = container.scrollTop;
            container.scrollTop = container.scrollHeight;
            await sleep(scrollDelay);
            // 如果滚动位置未变，说明到底了
            if (container.scrollTop === prevScrollTop) break;
        }

        // 回到初始位置
        try { container.scrollTop = 0; } catch {}
        log(`${label}滚动采集完成: ${results.length}条`);
        return results;
    }

    // ========== 线索列表采集 ==========
    async function collectLeads() {
        // 点击"线索分析"Tab
        const tab = document.querySelector(SELECTORS.leadsAnalysisTab);
        if (tab) {
            tab.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
            await sleep(CONFIG.TAB_SWITCH_DELAY);
        }

        // 轮询等待线索表格数据就绪（历史场次数据加载可能超过TAB_SWITCH_DELAY）
        let tables = document.querySelectorAll('table[role="table"]');
        let bodyTable = Array.from(tables).find(t => t.querySelectorAll('tbody tr[role="row"]').length > 0);
        const waitDeadline = Date.now() + 12000;
        while (!bodyTable && Date.now() < waitDeadline) {
            await sleep(1000);
            tables = document.querySelectorAll('table[role="table"]');
            bodyTable = Array.from(tables).find(t => t.querySelectorAll('tbody tr[role="row"]').length > 0);
        }
        // 最终fallback：找任何有tbody行的table，或按索引取
        if (!bodyTable) {
            bodyTable = Array.from(tables).find(t => t.querySelectorAll('tbody tr').length > 0) || tables[1] || tables[0];
        }
        const headTable = Array.from(tables).find(t => t.querySelector('thead tr'));
        if (!bodyTable) {
            log('未找到线索表格，尝试Legacy方式', 'warn');
            return collectLeadsLegacy();
        }

        // 找到可滚动容器，验证包含预期行数（fallback到bodyTable本身）
        const scrollContainer = bodyTable.closest('[class*="scroll"], [class*="virtual"], [style*="overflow"]') || bodyTable.parentElement;
        const containerRowCount = scrollContainer ? scrollContainer.querySelectorAll('tbody tr[role="row"]').length : 0;
        const effectiveContainer = containerRowCount > 0 ? scrollContainer : bodyTable;
        log(`线索表格: ${tables.length}个table, body行数=${bodyTable.querySelectorAll('tbody tr[role="row"]').length}, container行数=${containerRowCount}`);

        // 动态列头映射：从表头读取列名，避免硬编码索引（表头可能在另一个table中）
        const headerRow = (headTable || bodyTable)?.querySelector('thead tr');
        const colMap = {};
        if (headerRow) {
            const headers = headerRow.querySelectorAll('th');
            const HEADER_MAP = {
                '留资时间': 'lead_time', '用户信息': 'nickname', '电话': 'phone_masked',
                '商品名称': 'product_name', '所在城市': 'city', '留资路径': 'path',
                '特征标签': 'tags', '来源客户': 'ad_account', '序号': '_seq',
            };
            headers.forEach((th, idx) => {
                const text = th.textContent.trim();
                if (HEADER_MAP[text]) colMap[HEADER_MAP[text]] = idx;
            });
        }
        // fallback: 默认索引
        if (Object.keys(colMap).length < 3) {
            colMap.lead_time = 1; colMap.nickname = 2; colMap.phone_masked = 3;
            colMap.product_name = 4; colMap.city = 5; colMap.path = 6;
            colMap.tags = 7; colMap.ad_account = 8;
        }

        return scrollAndCollect({
            container: effectiveContainer,
            rowSelector: 'tbody tr[role="row"]',
            parseFn: (row) => {
                const cells = row.querySelectorAll('td');
                if (cells.length < 3) return null;
                const get = (field) => cells[colMap[field]]?.textContent?.trim() || '';
                const phoneRaw = get('phone_masked');
                const phoneMasked = phoneRaw.match(/\*+\d+/) ? phoneRaw.match(/\*+\d+/)[0] : phoneRaw;
                return {
                    lead_time: get('lead_time'),
                    nickname: get('nickname'),
                    lead_id: '',
                    phone_masked: phoneMasked,
                    product_name: get('product_name'),
                    city: get('city'),
                    path: get('path'),
                    tags: get('tags'),
                    ad_account: get('ad_account'),
                };
            },
            dedupKeyFn: (item) => `${item.lead_time}|${item.nickname}`,
            label: '线索',
        });
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

    // ========== 评论采集（右侧面板"评论"Tab）==========
    async function collectComments() {
        const commentTab = document.querySelector(SELECTORS.commentTab);
        if (commentTab) {
            commentTab.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
            await sleep(CONFIG.TAB_SWITCH_DELAY);
        }

        const BUTTON_LABELS = ['私信', '聊天', '私2', '咨询', '立即咨询'];

        // 找到评论虚拟滚动容器
        let scrollContainer = null;
        // 策略1: 找包含translateY行的最近overflow祖先
        const firstVRow = document.querySelector('[style*="translateY"]');
        if (firstVRow) {
            scrollContainer = firstVRow.closest('[class*="scroll"], [class*="virtual"], [style*="overflow"]') || firstVRow.parentElement;
        }
        // 策略2: 从评论Tab标签向下搜索
        if (!scrollContainer && commentTab) {
            const panel = commentTab.closest('[class*="tab"], [class*="panel"]') || commentTab.parentElement?.parentElement;
            if (panel) {
                scrollContainer = panel.querySelector('[class*="virtual"], [class*="scroll"], [style*="overflow"]');
            }
        }
        // 策略3: 全局搜索虚拟滚动容器
        if (!scrollContainer) {
            scrollContainer = document.querySelector('[class*="virtual-list"], [class*="virtualList"]');
        }

        if (!scrollContainer) {
            log('未找到评论滚动容器，尝试单次采集', 'warn');
            // fallback: 只采集当前可见行
            const vRows = document.querySelectorAll('[style*="translateY"]');
            const comments = [];
            for (const row of vRows) {
                const children = row.children;
                for (const child of children) {
                    const parsed = parseCommentText(child.textContent, BUTTON_LABELS);
                    if (parsed) comments.push(parsed);
                }
            }
            log(`评论单次采集: ${comments.length}条`);
            return comments;
        }

        return scrollAndCollect({
            container: scrollContainer,
            rowSelector: '[style*="translateY"]',
            parseFn: (row) => {
                const children = row.children;
                for (const child of children) {
                    const parsed = parseCommentText(child.textContent, BUTTON_LABELS);
                    if (parsed) return parsed;
                }
                return null;
            },
            dedupKeyFn: (item) => `${item.comment_time}|${item.nickname}|${item.content.slice(0, 30)}`,
            label: '评论',
            maxScrolls: 40,
        });
    }

    // 评论文本解析辅助函数
    function parseCommentText(rawText, buttonLabels) {
        let text = (rawText || '').trim();
        if (!text || text === '点击加载更多评论') return null;
        // 去除按钮文字污染
        for (const label of buttonLabels) {
            text = text.replace(new RegExp(label + '$'), '');
        }
        text = text.trim();
        // 格式: "20:44 人生南北多歧路：我之前在广东"
        const match = text.match(/^(\d{2}:\d{2})\s+(.+?)：(.+)$/);
        if (match) {
            return {
                nickname: match[2].trim(),
                has_lead: false,
                content: match[3].trim().slice(0, 200),
                comment_time: match[1]
            };
        }
        // 备用：无法解析格式时整条存入
        const timeMatch = text.match(/^(\d{2}:\d{2})\s+(.+)/);
        if (timeMatch) {
            return {
                nickname: '',
                has_lead: false,
                content: timeMatch[2].trim().slice(0, 200),
                comment_time: timeMatch[1]
            };
        }
        return null;
    }

    // ========== 高意向用户采集（右侧面板"高意向"Tab）==========
    async function collectHighIntentUsers() {
        const tab = document.querySelector(SELECTORS.highIntentTab);
        if (tab) {
            tab.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
            await sleep(CONFIG.TAB_SWITCH_DELAY);
        }
        
        // 策略1: 从Tab内容面板区域搜索列表容器
        let listContainer = null;
        const hiEl = document.querySelector('[data-log-name="高意向"]');
        if (hiEl) {
            const tabPanel = hiEl.closest('[class*="tab"], [class*="panel"], [class*="pane"]') || hiEl.parentElement?.parentElement;
            if (tabPanel) {
                listContainer = tabPanel.querySelector('[class*="list"], [class*="virtual"], [class*="card-list"]');
                if (!listContainer) {
                    let sibling = tabPanel.nextElementSibling;
                    while (sibling && !listContainer) {
                        listContainer = sibling.querySelector('[class*="list"], [class*="virtual"], [class*="card-list"]');
                        sibling = sibling.nextElementSibling;
                    }
                }
            }
            if (!listContainer) {
                listContainer = hiEl.closest('[class*="list"], [class*="container"], [class*="card-list"], [class*="virtual"]');
            }
        }
        // 策略2: 文本搜索回退
        if (!listContainer) {
            const allSpans = document.querySelectorAll('span');
            for (const span of allSpans) {
                if (span.textContent.trim().includes('高意向')) {
                    const tabPanel2 = span.closest('[class*="tab"], [class*="panel"], [class*="pane"]') || span.parentElement?.parentElement;
                    if (tabPanel2) {
                        listContainer = tabPanel2.querySelector('[class*="list"], [class*="virtual"], [class*="card-list"]');
                    }
                    if (!listContainer) {
                        listContainer = span.closest('[class*="list"], [class*="container"], [class*="card-list"], [class*="virtual"]') || span.parentElement?.parentElement;
                    }
                    break;
                }
            }
        }
        if (!listContainer) {
            listContainer = document.querySelector('[role="list"], [class*="virtual-list"]');
        }
        if (!listContainer) return [];
        
        const scrollContainer = listContainer.querySelector('.rc-virtual-list-holder') || listContainer;
        return scrollAndCollect({
            container: scrollContainer,
            rowSelector: '[role="listitem"], [class*="card"], [class*="user-card"], [class*="user-item"], [class*="item"]',
            parseFn: (card) => {
                const img = card.querySelector('img');
                // 昵称提取：img.alt优先，否则叶节点扫描
                const SKIP_TEXTS = new Set(['忽略','私信','评论数','停留时长','已留资','高光','违规','状态','评论']);
                let nickname = (img?.alt || '').replace(/\s*avatar\s*/gi, '').trim();
                if (!nickname) {
                    for (const el of card.querySelectorAll('*')) {
                        if (el.children.length > 0) continue;
                        const text = el.textContent.trim();
                        if (!text) continue;
                        if (SKIP_TEXTS.has(text)) continue;
                        if (/^\d+([条分钟秒s.]+)?$/.test(text)) continue;
                        nickname = text;
                        break;
                    }
                }
                if (!nickname) return null;

                const allTexts = card.querySelectorAll('p, span, div');
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

                if (card.textContent.includes('已留资')) status = '已留资';
                else if (card.textContent.includes('忽略')) status = '忽略';

                return { nickname, avatar_url: img?.src || '', comment_count: commentCount, stay_duration: stayDuration, status };
            },
            dedupKeyFn: (item) => item.nickname,
            label: '高意向',
            maxScrolls: 30,
        });
    }

    // ========== 复盘表采集 ==========
    async function collectReviewData() {
        const tab = document.querySelector(SELECTORS.reviewTab);
        if (!tab) {
            log('未找到复盘表Tab');
            return {};
        }
        tab.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
        await sleep(CONFIG.TAB_SWITCH_DELAY);

        const review = {};

        // 策略1: table结构采集（抖音来客使用分离表头模式：thead在第一个table，tbody在第二个table）
        const tabPanel = tab.closest('.leads-tab')?.querySelector('.leads-tab-item-active, .leads-tab-item') || document;
        const tables = tabPanel.querySelectorAll('table[role="table"]');
        // 分离表头模式：从有thead的table取表头，从有tbody的table取数据行
        const headTable = Array.from(tables).find(t => t.querySelector('thead tr'));
        const bodyTable = Array.from(tables).find(t => t.querySelectorAll('tbody tr').length > 0);
        if (headTable || bodyTable) {
            const headerRow = (headTable || bodyTable)?.querySelector('thead tr');
            const bodyRows = (bodyTable || headTable)?.querySelectorAll('tbody tr') || [];
            if (headerRow && bodyRows.length > 0) {
                const headers = Array.from(headerRow.querySelectorAll('th')).map(th => th.textContent.trim());
                for (const row of bodyRows) {
                    const cells = row.querySelectorAll('td');
                    if (cells.length < 2) continue;
                    const rowKey = cells[0]?.textContent?.trim() || '';
                    // 将每行转为 key-value 对
                    for (let i = 1; i < cells.length && i < headers.length; i++) {
                        const colName = headers[i] || `col${i}`;
                        const val = cells[i]?.textContent?.trim() || '';
                        if (rowKey && val) {
                            review[`${rowKey}_${colName}`] = val;
                        }
                    }
                }
                if (Object.keys(review).length > 0) {
                    log(`复盘表table采集完成: ${Object.keys(review).length}项`);
                    return review;
                }
            }
        }

        // 策略2: 卡片/列表结构采集
        const cardContainer = document.querySelector('[class*="review"], [class*="replay"], [class*="summary"]');
        if (cardContainer) {
            const items = cardContainer.querySelectorAll('[class*="item"], [class*="card"], [class*="row"]');
            for (const item of items) {
                const labels = item.querySelectorAll('[class*="label"], [class*="title"], [class*="key"]');
                const values = item.querySelectorAll('[class*="value"], [class*="content"], [class*="num"]');
                for (let i = 0; i < Math.min(labels.length, values.length); i++) {
                    const key = labels[i]?.textContent?.trim();
                    const val = values[i]?.textContent?.trim();
                    if (key && val) review[key] = val;
                }
            }
            if (Object.keys(review).length > 0) {
                log(`复盘表卡片采集完成: ${Object.keys(review).length}项`);
                return review;
            }
        }

        // 策略3: 时段分析行结构
        const timeRows = document.querySelectorAll('[class*="time-period"], [class*="time-slot"], [class*="period"]');
        if (timeRows.length > 0) {
            for (const row of timeRows) {
                const spans = row.querySelectorAll('span, div, p');
                let periodName = '';
                const metrics = {};
                for (const span of spans) {
                    const text = span.textContent.trim();
                    if (text.match(/\d{2}:\d{2}/)) {
                        periodName = text;
                    } else if (text.match(/\d+/) && periodName) {
                        metrics[periodName] = metrics[periodName] ? metrics[periodName] + ',' + text : text;
                    }
                }
                if (periodName) review[periodName] = metrics[periodName] || '';
            }
            if (Object.keys(review).length > 0) {
                log(`复盘表时段采集完成: ${Object.keys(review).length}项`);
                return review;
            }
        }

        // 所有策略均未匹配
        log('复盘表DOM不匹配，可能抖音来客已更新', 'warn');
        return review;
    }

    // ========== 私信分析采集（左侧Tab"私信分析"）==========
    async function collectPrivateMessages() {
        const tab = document.querySelector('[data-log-name="私信分析"]');
        if (!tab) { log('未找到私信分析Tab'); return []; }
        tab.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
        await sleep(CONFIG.TAB_SWITCH_DELAY);

        // 私信分析使用分离表头模式：thead在tables[0]，tbody在tables[1]
        const tables = document.querySelectorAll('table[role="table"]');
        const bodyTable = Array.from(tables).find(t => t.querySelectorAll('tbody tr').length > 0) || tables[1] || tables[0];
        if (!bodyTable) { log('未找到私信分析表格'); return []; }

        const scrollContainer = bodyTable.closest('[class*="scroll"], [class*="virtual"], [style*="overflow"]') || bodyTable.parentElement;

        return scrollAndCollect({
            container: scrollContainer,
            rowSelector: 'tbody tr[role="row"]',
            parseFn: (row) => {
                const cells = row.querySelectorAll('td');
                if (cells.length < 8) return null;
                const userCell = cells[1];
                const nickname = userCell?.querySelector('div[style*="font-size: 16px"]')?.textContent?.trim() || userCell?.querySelector('div')?.textContent?.trim() || '';
                const douyinId = userCell?.querySelector('[class*="opacity-70"]')?.textContent?.trim()?.replace('抖音ID：', '') || '';
                return {
                    nickname,
                    douyin_id: douyinId,
                    has_lead: cells[2]?.textContent?.trim() === '是',
                    last_message_time: cells[3]?.textContent?.trim() || '',
                    last_reply_time: cells[4]?.textContent?.trim() || '',
                    pending_reply: cells[5]?.textContent?.trim() || '',
                    message_count: parseInt(cells[6]?.textContent?.trim()) || 0,
                    ai_reply_count: parseInt(cells[7]?.textContent?.trim()) || 0,
                };
            },
            dedupKeyFn: (item) => `${item.nickname}|${item.douyin_id}`,
            label: '私信',
        });
    }

    // ========== 数据完整性自检 ==========
    function validateMetrics(metrics) {
        const totalFields = Object.keys(metrics).length;
        if (totalFields === 0) {
            const existingCards = document.querySelectorAll('[data-log-name]');
            const cardNames = Array.from(existingCards).map(el => el.getAttribute('data-log-name')).slice(0, 15);
            log(`未采集到任何指标字段，页面可能未就绪。当前页面data-log-name: [${cardNames.join(', ')}]（共${existingCards.length}个）`, 'error');
            return false;
        }
        let emptyCount = 0;
        const emptyFields = [];
        for (const [key, value] of Object.entries(metrics)) {
            if (value === '--' || value === null || value === undefined || value === '') {
                emptyCount++;
                emptyFields.push(key);
            }
        }
        const completeness = ((totalFields - emptyCount) / totalFields * 100).toFixed(1);
        log(`指标完整率: ${completeness}% (${totalFields - emptyCount}/${totalFields})`);

        // 关键字段强制检查（缺失时告警但不阻止提交）
        const criticalFields = ['ad_spend', 'view_count', 'exposure_count'];
        const missingCritical = criticalFields.filter(f => !metrics[f] || metrics[f] === '--');
        if (missingCritical.length > 0) {
            log(`关键字段缺失: ${missingCritical.join(', ')}`, 'warn');
            sendAlert('关键字段缺失', `场次缺少关键字段: ${missingCritical.join(', ')}`);
        }

        if (completeness < 70) {
            log('完整率过低，跳过该场次', 'error');
            sendAlert('采集异常', `指标完整率仅${completeness}%，缺失字段: ${emptyFields.slice(0, 5).join(',')}`);
            return false;
        }
        if (completeness < 80) {
            log('完整率偏低，可能DOM结构已变化', 'warn');
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
                timeout: CONFIG.HTTP_TIMEOUT,
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
                        if (cache.length >= 50) cache.shift(); // 容量限制
                        cache.push(sessionData);
                        GM_setValue('pending_data', JSON.stringify(cache));
                        reject(new Error('发送失败'));
                    }
                },
                ontimeout: async () => {
                    log(`发送超时(${CONFIG.HTTP_TIMEOUT/1000}s)`, 'warn');
                    if (retries > 0) {
                        await sleep(CONFIG.RETRY_DELAY);
                        resolve(await sendToServer(sessionData, retries - 1));
                    } else {
                        const cache = JSON.parse(GM_getValue('pending_data', '[]'));
                        if (cache.length >= 50) cache.shift(); // 容量限制
                        cache.push(sessionData);
                        GM_setValue('pending_data', JSON.stringify(cache));
                        reject(new Error('发送超时'));
                    }
                }
            });
        });
    }

    // ========== 直播补采持久化队列 ==========
    const PENDING_LIVE_KEY = 'pending_live_sessions';
    const MAX_PENDING_LIVE = 20;

    function addPendingLiveSession(startTime) {
        const queue = JSON.parse(GM_getValue(PENDING_LIVE_KEY, '[]'));
        if (queue.includes(startTime)) return; // 去重
        queue.push(startTime);
        if (queue.length > MAX_PENDING_LIVE) queue.shift(); // 容量限制
        GM_setValue(PENDING_LIVE_KEY, JSON.stringify(queue));
        log(`直播补采队列: +${startTime} (共${queue.length}条)`);
    }

    function getPendingLiveSessions() {
        return JSON.parse(GM_getValue(PENDING_LIVE_KEY, '[]'));
    }

    function removePendingLiveSession(startTime) {
        const queue = JSON.parse(GM_getValue(PENDING_LIVE_KEY, '[]'));
        const idx = queue.indexOf(startTime);
        if (idx >= 0) {
            queue.splice(idx, 1);
            GM_setValue(PENDING_LIVE_KEY, JSON.stringify(queue));
        }
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
    function sendAlert(type, message, sessionTime, level = 'warning') {
        if (level !== 'critical') {
            log(`[告警-仅日志] ${type}: ${message}`, 'warn');
            return;
        }
        GM_xmlhttpRequest({
            method: 'POST',
            url: `${CONFIG.SERVER_URL}/api/alert`,
            headers: { 'Content-Type': 'application/json' },
            data: JSON.stringify({
                type, message,
                session_time: sessionTime || '',
                timestamp: new Date().toLocaleString('zh-CN')
            }),
            timeout: CONFIG.HTTP_TIMEOUT,
            onload: () => log(`告警已发送: ${type}`),
            onerror: () => {
                log('告警发送失败', 'warn');
                // 服务端不可达时，通过桌面通知兜底
                GM_notification({ title: '⚠️ 告警发送失败', text: `${type}: ${message.slice(0, 100)}` });
            },
            ontimeout: () => {
                log(`告警发送超时(${CONFIG.HTTP_TIMEOUT/1000}s)`, 'warn');
                GM_notification({ title: '⚠️ 告警发送超时', text: `${type}: ${message.slice(0, 100)}` });
            }
        });
    }

    // ========== 采集当前场次 ==========
    async function collectCurrentSession(timeInfo) {
        log(`采集场次: ${timeInfo.start}`);
        // 等待数据卡片渲染完成（锚点/翻页后卡片可能延迟加载，尤其后台标签页）
        try { await waitForDataLoad(); } catch {}
        await waitForOdometer();
        const metrics = await collectMetrics();

        // 数据完整性自检
        if (!validateMetrics(metrics)) {
            return null;
        }

        const review = await collectReviewData();
        const leads = await collectLeads();
        const privateMessages = await collectPrivateMessages();
        const comments = await collectComments();
        const highIntentUsers = await collectHighIntentUsers();

        // 交叉验证告警：列表为空但指标卡显示有数据
        if (leads.length === 0 && parseFloat(metrics.total_leads) > 0) {
            sendAlert('线索采集异常', `指标卡显示留资${metrics.total_leads}人但列表为空，可能翻页未生效`);
        }
        if (comments.length === 0 && parseFloat(metrics.comment_count) > 0) {
            sendAlert('评论采集异常', `指标卡显示评论${metrics.comment_count}条但列表为空，可能虚拟滚动未遍历`);
        }
        if (Object.keys(review).length === 0) {
            log('复盘表无数据', 'warn');
        }

        // 采集完成后切回"综合趋势"Tab（恢复默认状态）
        const defaultTab = document.querySelector('[data-log-name="综合趋势"]');
        if (defaultTab) defaultTab.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));

        return {
            version: "1.0",
            account_id: CONFIG.ACCOUNT_ID || null,
            start_time: timeInfo.start,
            end_time: timeInfo.end,
            metrics, review, leads, comments, high_intent_users: highIntentUsers, private_messages: privateMessages
        };
    }

    // ========== 评论洞察分析页面 - 定位"评论明细"区域 ==========
    function findCommentDetailSection() {
        // 从"评论明细"文本向上找高度>500的容器
        const detailText = [...document.querySelectorAll('*')].find(e =>
            e.textContent?.trim() === '评论明细' && e.children.length === 0
        );
        if (!detailText) return null;
        let section = detailText;
        for (let i = 0; i < 10; i++) {
            section = section.parentElement;
            if (!section) break;
            if (section.getBoundingClientRect().height > 500) return section;
        }
        return null;
    }

    // ========== 评论洞察分析页面 - 滚动采集"全部"tab下的所有评论 ==========
    async function collectCommentInsightScroll(section) {
        const scrollEl = section.querySelector('[class*="overflow-auto"]') || section.querySelector('[style*="overflow"]');
        if (!scrollEl) {
            log('未找到评论洞察滚动容器', 'error');
            return [];
        }

        const collected = new Map(); // key=昵称|评论时间|内容前30字 → 数据对象
        const ROW_HEIGHT = 60;
        const totalRows = Math.round(scrollEl.scrollHeight / ROW_HEIGHT);
        log(`评论洞察虚拟列表: scrollH=${scrollEl.scrollHeight}, 预计${totalRows}行`);

        function collectVisible() {
            const rows = section.querySelectorAll('[style*="translateY"]');
            let newCount = 0;
            rows.forEach(row => {
                const cols = row.querySelectorAll(':scope > div');
                if (cols.length < 4) return;

                // 验证列宽匹配评论级格式: [160,120,600,150,160] 5列
                // 或用户级格式: [160,120,400,100,150,160] 6列
                const widths = [...cols].map(c => parseInt(c.style.width) || 0);

                // 昵称 (第1列, 160px)
                const nickname = cols[0]?.textContent.trim().split('\n')[0];
                // 是否留资 (第2列, 120px)
                const leadText = cols[1]?.textContent.trim();
                const hasLead = leadText.includes('已留资');
                // 评论内容 (第3列, 600px or 400px)
                const content = cols[2]?.textContent.trim();

                let commentTime = '';
                if (widths.length === 5) {
                    // 评论级5列: 昵称(160)|是否留资(120)|评论内容(600)|评论时间(150)|操作(160)
                    commentTime = cols[3]?.textContent.trim();
                } else if (widths.length >= 6) {
                    // 用户级6列: 昵称(160)|是否留资(120)|最新评论内容(400)|评论次数(100)|最新评论时间(150)|操作(160)
                    commentTime = cols[4]?.textContent.trim();
                }

                if (!nickname || !content) return;

                const key = `${nickname}|${commentTime}|${content.slice(0, 30)}`;
                if (!collected.has(key)) {
                    collected.set(key, { nickname, has_lead: hasLead, content: content.slice(0, 500), comment_time: commentTime });
                    newCount++;
                }
            });
            return newCount;
        }

        // 逐步滚动采集
        scrollEl.scrollTop = 0;
        await sleep(300);

        const step = 200; // 每次滚200px，确保不遗漏
        const maxScroll = scrollEl.scrollHeight - scrollEl.clientHeight;
        let scrollPos = 0;
        let maxRounds = Math.ceil(maxScroll / step) + 5;

        for (let round = 0; round < maxRounds; round++) {
            collectVisible();
            scrollPos += step;
            if (scrollPos >= maxScroll) {
                scrollEl.scrollTop = maxScroll;
                await sleep(300);
                collectVisible();
                break;
            }
            scrollEl.scrollTop = scrollPos;
            await sleep(150);
        }

        // 回到顶部
        try { scrollEl.scrollTop = 0; } catch {}

        const results = [...collected.values()];
        log(`评论洞察滚动采集完成: ${results.length}条评论`);
        return results;
    }

    // ========== 评论洞察分析采集（重构版）==========
    async function collectCommentInsight() {
        log('开始采集评论洞察分析数据...');

        // 1. 提取当前场次信息
        const timeInfo = parseSessionTime(getTimeRangeText(), getLocalDateStr(new Date()));
        const roomId = new URLSearchParams(location.search).get('room_id') || '';

        // 2. 提取汇总信息 (textarea.leads-ls-screen-text)
        let summary = '';
        const summaryEl = document.querySelector('textarea.leads-ls-screen-text');
        if (summaryEl) {
            summary = summaryEl.value || summaryEl.textContent || '';
            log(`汇总: ${summary}`);
        }

        // 3. 点击"全部"tab切换到全部评论视图
        const allTab = [...document.querySelectorAll('[data-log-name="全部"]')].find(e =>
            e.classList.contains('leads-ls-screen-radio-tag') || e.closest('.leads-ls-screen-radio-tag')
        );
        if (allTab) {
            log('点击"全部"tab...');
            allTab.click();
            await sleep(1500); // 等待数据加载
        } else {
            log('未找到"全部"tab，使用当前视图采集', 'warn');
        }

        // 4. 定位"评论明细"区域
        const section = findCommentDetailSection();
        if (!section) {
            log('未找到评论明细区域', 'error');
            return { room_id: roomId, session_start: timeInfo.start, session_end: timeInfo.end, summary, comments: [], anchor_stats: [] };
        }

        // 5. 滚动采集所有评论
        const comments = await collectCommentInsightScroll(section);

        if (comments.length === 0) {
            log('滚动采集到0条评论，尝试fallback: 直接读取当前可见行', 'warn');
            // fallback: 不切换tab直接采集当前可见行
            const rows = document.querySelectorAll('[style*="translateY"]');
            for (const row of rows) {
                const cols = row.querySelectorAll(':scope > div');
                if (cols.length < 4) continue;
                const nickname = cols[0]?.textContent.trim().split('\n')[0];
                const hasLead = cols[1]?.textContent.trim().includes('已留资');
                const content = cols[2]?.textContent.trim();
                const time = cols[3]?.textContent.trim();
                if (nickname && content) {
                    comments.push({ nickname, has_lead: hasLead, content: content.slice(0, 500), comment_time: time });
                }
            }
            log(`fallback采集: ${comments.length}条`);
        }

        // 6. 从后端获取主播时段信息用于分组统计
        const anchorSlots = [];
        if (timeInfo.start) {
            try {
                const sessionDate = timeInfo.start.slice(0, 10);
                const resp = await new Promise((resolve, reject) => {
                    GM_xmlhttpRequest({
                        method: 'GET',
                        url: `${CONFIG.SERVER_URL}/api/anchors/by-date?date=${sessionDate}`,
                        timeout: CONFIG.HTTP_TIMEOUT,
                        onload: (r) => { try { resolve(JSON.parse(r.responseText)); } catch { resolve({ code: -1 }); } },
                        onerror: () => reject(new Error('获取主播信息失败')),
                        ontimeout: () => reject(new Error('获取主播信息超时'))
                    });
                });
                if (resp.code === 0 && resp.data) {
                    anchorSlots.push(...resp.data);
                }
            } catch (e) {
                log(`获取主播时段信息失败: ${e.message}`, 'warn');
            }
        }

        // 7. 按主播时段分组统计评论
        const anchorStats = [];
        for (const slot of anchorSlots) {
            const slotComments = comments.filter(c => {
                if (!c.comment_time || !slot.on_time || !slot.off_time) return false;
                // comment_time格式: MM-DD HH:mm, 需要拼接日期部分
                const commentHourMin = c.comment_time.replace(/^\d{2}-\d{2}\s*/, ''); // 提取HH:mm部分
                const onHourMin = slot.on_time.length > 5 ? slot.on_time.slice(11, 16) : slot.on_time;
                const offHourMin = slot.off_time.length > 5 ? slot.off_time.slice(11, 16) : slot.off_time;
                return commentHourMin >= onHourMin && commentHourMin <= offHourMin;
            });
            anchorStats.push({
                anchor_name: slot.name,
                on_time: slot.on_time,
                off_time: slot.off_time,
                comment_count: slotComments.length,
                lead_count: slotComments.filter(c => c.has_lead).length
            });
        }

        // 8. 统计汇总
        const uniqueUsers = new Set(comments.map(c => c.nickname));
        const leadUsers = new Set(comments.filter(c => c.has_lead).map(c => c.nickname));
        log(`评论洞察统计: ${comments.length}条评论, ${uniqueUsers.size}个用户, ${leadUsers.size}人已留资`);

        return {
            room_id: roomId,
            session_start: timeInfo.start,
            session_end: timeInfo.end,
            summary,
            anchor_stats: anchorStats,
            comments
        };
    }

    async function collectCommentInsightCollection(isAuto = true) {
        if (isCollecting) {
            log('采集进行中，跳过本次调用');
            return;
        }
        isCollecting = true;
        try {
            log(`开始评论洞察分析采集 (${isAuto ? '自动' : '手动'})`);
            
            // 等待页面加载
            try { await waitForDataLoad(); } catch {}
            await sleep(2000);
            
            // 采集数据
            const data = await collectCommentInsight();
            
            if (!data || data.comments.length === 0) {
                log('未采集到评论数据', 'warn');
                GM_notification({ title: '⚠️ 采集完成', text: '未采集到评论数据' });
                return;
            }
            
            // 发送到服务端
            try {
                const result = await new Promise((resolve, reject) => {
                    GM_xmlhttpRequest({
                        method: 'POST',
                        url: `${CONFIG.SERVER_URL}/api/comment-insight`,
                        headers: { 'Content-Type': 'application/json' },
                        data: JSON.stringify(data),
                        timeout: CONFIG.HTTP_TIMEOUT,
                        onload: (r) => resolve(JSON.parse(r.responseText)),
                        onerror: () => reject(new Error('发送失败')),
                        ontimeout: () => reject(new Error('发送超时'))
                    });
                });
                
                if (result.code === 0) {
                    log(`评论洞察分析采集完成: ${data.comments.length}条评论, ${data.anchor_stats.length}个主播时段`);
                    GM_notification({ 
                        title: '✅ 采集完成', 
                        text: `评论${data.comments.length}条, 主播时段${data.anchor_stats.length}个` 
                    });
                } else {
                    log(`发送失败: ${result.message}`, 'error');
                    GM_notification({ title: '❌ 采集失败', text: result.message || '发送到服务端失败' });
                }
            } catch (e) {
                log(`发送失败: ${e.message}`, 'error');
                // 缓存到本地
                const cache = JSON.parse(GM_getValue('pending_comment_insight', '[]'));
                if (cache.length < 10) {
                    cache.push(data);
                    GM_setValue('pending_comment_insight', JSON.stringify(cache));
                    log('数据已缓存到本地', 'warn');
                }
                GM_notification({ title: '❌ 采集失败', text: e.message.slice(0, 100) });
            }
        } catch (e) {
            log(`采集崩溃: ${e.message}`, 'error');
            GM_notification({ title: '❌ 采集崩溃', text: e.message.slice(0, 100) });
        } finally {
            isCollecting = false;
        }
    }

    // ========== 定位到最晚场次（锚点） ==========
    async function goToLatest() {
        log('开始定位锚点（最晚场次）...');
        const deadline = Date.now() + CONFIG.NAVIGATION_TIMEOUT;
        let steps = 0;
        for (let i = 0; i < CONFIG.MAX_NAVIGATION_STEPS; i++) {
            if (Date.now() > deadline) {
                log(`定位超时（${CONFIG.NAVIGATION_TIMEOUT/1000}秒），已走${steps}步`, 'error');
                sendAlert('定位超时', `${CONFIG.MAX_NAVIGATION_STEPS}步/${CONFIG.NAVIGATION_TIMEOUT/1000}秒内未定位到最晚场次`);
                return false;
            }
            const nextBtnState = isButtonDisabled(SELECTORS.nextButton);
            if (nextBtnState === null) {
                log('下一场按钮不存在，DOM可能未就绪，等待重试', 'warn');
                await sleep(2000);
                continue;
            }
            if (nextBtnState === true) {
                const timeInfo = parseSessionTime(getTimeRangeText(), getLocalDateStr(new Date()));
                log(`锚点定位完成: ${timeInfo.start || '未知日期'}, 步数: ${steps}`);
                return true;
            }
            clickButton(SELECTORS.nextButton);
            try { await waitForDataLoad(); } catch {}
            await sleep(300);
            steps++;
        }
        log(`定位最晚场次超限（超过${CONFIG.MAX_NAVIGATION_STEPS}步），可能DOM异常`, 'error');
        sendAlert('定位超限', `超过${CONFIG.MAX_NAVIGATION_STEPS}步未定位到最晚场次`);
        return false;
    }

    // ========== 主采集流程 ==========
    async function startCollection(isAuto = true) {
        // 并发保护锁
        if (isCollecting) {
            log('采集进行中，跳过本次调用');
            return;
        }
        isCollecting = true;
        try {
        log(`开始采集流程 (${isAuto ? '自动' : '手动'})`);

        // DOM健康检查：关键元素是否存在
        const prevBtn = document.querySelector(SELECTORS.prevButton);
        const nextBtn = document.querySelector(SELECTORS.nextButton);
        if (!prevBtn || !nextBtn) {
            log('关键DOM元素缺失，抖音来客可能已更新', 'error');
            sendAlert('DOM异常', `关键元素缺失: prevBtn=${!!prevBtn}, nextBtn=${!!nextBtn}，抖音来客可能已更新`);
            GM_notification({ title: '❌ DOM异常', text: '关键导航按钮消失，请检查抖音来客页面' });
            return;
        }

        const today = getLocalDateStr(new Date());
        const collectDay = today;  // 缓存发起日期，防止跨午夜

        if (isAuto) {
            const lastAttemptDate = GM_getValue('last_attempt_date', '');
            let todayAttempts = 0;
            if (lastAttemptDate === today) {
                todayAttempts = parseInt(GM_getValue('today_attempts', '0')) || 0;
            }
            if (todayAttempts >= CONFIG.MAX_DAILY_ATTEMPTS) {
                log(`今日已达最大尝试次数(${CONFIG.MAX_DAILY_ATTEMPTS})，跳过采集，等待明天0点`);
                GM_notification({ title: '直播数据同步', text: `今日自动采集已尝试${CONFIG.MAX_DAILY_ATTEMPTS}次均未成功，已放弃，等待明天0点` });
                sendAlert('自动采集放弃', `今日自动采集已尝试${CONFIG.MAX_DAILY_ATTEMPTS}次均未成功，已放弃重试，等待明天0点`);
                return;
            }
            GM_setValue('last_attempt_date', today);
            GM_setValue('today_attempts', String(todayAttempts + 1));
            log(`今日第 ${todayAttempts + 1}/${CONFIG.MAX_DAILY_ATTEMPTS} 次自动尝试`);
        }

        const dateRange = getDaysList(CONFIG.COLLECT_DAYS);
        const dateSet = new Set(dateRange);

        // 预拉取所有目标日期的已有场次，合并为单一Set
        const allExistingStarts = new Set();
        for (const d of dateRange) {
            const starts = await getExistingSessions(d);
            for (const s of starts) allExistingStarts.add(s);
        }
        log(`服务端已有 ${allExistingStarts.size} 个目标日期场次`);

        await retryCachedData();

        // 定位到最晚场次锚点（后续所有日期导航均从此单向回退）
        if (!await goToLatest()) {
            log('无法定位到最晚场次锚点，终止采集', 'error');
            sendAlert('定位失败', '无法定位到最晚场次锚点，请检查抖音来客页面是否正常加载');
            return;
        }

        let collected = 0;
        let skipped = 0;
        let failed = 0;

        // 计算最早目标日期（停止边界）
        const earliestDate = dateRange[dateRange.length - 1];

        // 单次回退遍历：从锚点最晚场次开始，回退处理所有目标日期场次
        const maxLoopSteps = Math.max(CONFIG.COLLECT_DAYS * 15 + 30, 100); // 最少100步，覆盖长期停机
        let loopStep;
        for (loopStep = 0; loopStep < maxLoopSteps; loopStep++) {
            const timeInfo = parseSessionTime(getTimeRangeText(), dateRange[0]);

            // 停止条件1：无法解析时间
            if (!timeInfo.startDate) {
                log('无法解析场次时间，停止遍历');
                break;
            }

            // 停止条件2：日期早于最早目标日期
            if (timeInfo.startDate < earliestDate) {
                log(`已遍历至 ${timeInfo.startDate}，早于目标范围 ${earliestDate}，停止`);
                break;
            }

            log(`← 回退至 ${timeInfo.startDate} ${timeInfo.start || ''}`);

            // 非目标日期：仅回退，不采集
            if (!dateSet.has(timeInfo.startDate)) {
                log(`场次日期 ${timeInfo.startDate} 不在目标范围，跳过`);
                const prevBtnState3 = isButtonDisabled(SELECTORS.prevButton);
                if (prevBtnState3 === null) { log('prevButton不存在，DOM异常', 'warn'); await sleep(2000); continue; }
                if (prevBtnState3 === true) break;
                clickButton(SELECTORS.prevButton);
                try { await waitForDataLoad(); } catch {}
                await sleep(300);
                continue;
            }

            // 直播中场次：记录待补采，继续回退
            if (timeInfo.isLive) {
                log(`直播中场次 ${timeInfo.start}，记录待补采`);
                addPendingLiveSession(timeInfo.start);
                const prevBtnState4 = isButtonDisabled(SELECTORS.prevButton);
                if (prevBtnState4 === null) { log('prevButton不存在，DOM异常', 'warn'); await sleep(2000); continue; }
                if (prevBtnState4 === true) break;
                clickButton(SELECTORS.prevButton);
                try { await waitForDataLoad(); } catch {}
                await sleep(300);
                continue;
            }

            // 已存在：跳过
            if (allExistingStarts.has(timeInfo.start)) {
                log(`场次 ${timeInfo.start} 已存在，跳过`);
                skipped++;
                const prevBtnState5 = isButtonDisabled(SELECTORS.prevButton);
                if (prevBtnState5 === null) { log('prevButton不存在，DOM异常', 'warn'); await sleep(2000); continue; }
                if (prevBtnState5 === true) break;
                clickButton(SELECTORS.prevButton);
                try { await waitForDataLoad(); } catch {}
                await sleep(300);
                continue;
            }

            // 新场次：采集+发送+校验
            try {
                const data = await collectCurrentSession(timeInfo);
                if (data && data.metrics && Object.values(data.metrics).some(v => v && v !== '--')) {
                    const result = await sendToServer(data);
                    if (result.code === 0) {
                        collected++;
                        log(`数据摘要: 消耗¥${data.metrics.ad_spend||'--'} | 留资${data.metrics.total_leads||'--'} | 线索${data.leads.length}条`);
                    } else if (result.message && result.message.includes('已存在')) {
                        skipped++;
                        log(`服务端确认重复: ${timeInfo.start}`);
                    } else {
                        failed++;
                        log(`发送失败: ${result.message}`, 'error');
                    }
                } else if (data) {
                    log(`指标全为空值，拒绝发送: ${timeInfo.start}`, 'warn');
                    failed++;
                } else {
                    failed++;
                }
            } catch (e) {
                log(`采集失败: ${e.message}`, 'error');
                failed++;
            }

            const prevBtnState6 = isButtonDisabled(SELECTORS.prevButton);
            if (prevBtnState6 === null) {
                log('prevButton不存在，DOM异常，停止遍历', 'warn');
                sendAlert('DOM异常', 'prevButton消失，可能抖音来客已更新');
                break;
            }
            if (prevBtnState6 === true) break;
            clickButton(SELECTORS.prevButton);
            try { await waitForDataLoad(); } catch {}
            await sleep(300);
        }
        if (loopStep >= maxLoopSteps) {
            log(`遍历超限（${maxLoopSteps}步），可能DOM异常`, 'error');
            sendAlert('遍历超限', `超过${maxLoopSteps}步未完成遍历`);
        }

        // 补采队列消费：检查直播中场次是否已结束
        const pendingLive = getPendingLiveSessions();
        if (pendingLive.length > 0) {
            log(`发现${pendingLive.length}个待补采直播场次`);
            for (const pendingStart of pendingLive) {
                // 从当前位置导航到待补采场次（通过goToLatest重新锚定再回退）
                // 简化策略：直接检查服务端是否已有该场次（可能其他途径已采集）
                try {
                    const existingCheck = await getExistingSessions(pendingStart.slice(0, 10));
                    if (existingCheck.has(pendingStart)) {
                        log(`补采场次 ${pendingStart} 已存在，移除`);
                        removePendingLiveSession(pendingStart);
                        continue;
                    }
                } catch {}
                // 无法导航到具体场次时，标记为待下次采集
                log(`补采场次 ${pendingStart} 需手动采集或等待下次自动采集`, 'warn');
                sendAlert('待补采', `直播场次 ${pendingStart} 已结束，需手动补采`);
            }
        }

        if (collected > 0) {
            GM_setValue('last_collect_date', collectDay);
        }
        log(`采集完成: 新增${collected}场, 跳过${skipped}场${failed > 0 ? `, 失败${failed}场` : ''}`);
        GM_notification({ title: '直播数据同步', text: `采集完成: 新增${collected}场${failed > 0 ? `，失败${failed}场` : ''}` });
        if (failed > 0 && collected === 0) {
            log('全部场次采集失败，心跳将在下个周期重试', 'warn');
            sendAlert('采集失败', `${CONFIG.COLLECT_DAYS}天采集全部失败（${failed}场），等待心跳重试`);
        } else if (failed > 0) {
            sendAlert('采集失败', `${CONFIG.COLLECT_DAYS}天采集完成：新增${collected}场，跳过${skipped}场，失败${failed}场`);
        }
        } finally {
            isCollecting = false;
        }
    }

    // ========== 定时检测 ==========
    function startHeartbeat() {
        const heartbeatTimer = setInterval(() => {
            const now = new Date();
            const lastCollect = GM_getValue('last_collect_date', '');
            const today = getLocalDateStr(now);
            const lastAttemptDate = GM_getValue('last_attempt_date', '');
            let todayAttempts = 0;
            if (lastAttemptDate === today) {
                todayAttempts = parseInt(GM_getValue('today_attempts', '0')) || 0;
            }

            if (now.getHours() >= CONFIG.COLLECT_HOUR && now.getHours() < CONFIG.COLLECT_HOUR + 6 && lastCollect !== today && todayAttempts < CONFIG.MAX_DAILY_ATTEMPTS) {
                // 自动采集：仅1:00~7:00窗口，受MAX_DAILY_ATTEMPTS限制
                log('触发采集流程，页面将自动刷新');
                GM_setValue('pending_collect', 'true');
                location.reload();
            } else if (todayAttempts >= CONFIG.MAX_DAILY_ATTEMPTS) {
                // 不clearInterval：明天日期变更后 todayAttempts 自动归零，心跳将重新触发采集
                // （仅在采集时间窗口内打印，避免白天刷新时日志刷屏）
                if (now.getHours() >= CONFIG.COLLECT_HOUR && now.getHours() < CONFIG.COLLECT_HOUR + 6) {
                    log(`今日已达最大尝试次数(${CONFIG.MAX_DAILY_ATTEMPTS})，等待明天0点重试`);
                }
            }
            // lastCollect === today 或 todayAttempts>=MAX 时均不clearInterval，保持心跳运行以便次日自动触发
        }, CONFIG.CHECK_INTERVAL);
    }

    // ========== 全局异常捕获 ==========
    window.addEventListener('error', (event) => {
        // 仅捕获脚本自身异常，过滤第三方脚本和抖音来客自身错误
        const src = event.filename || '';
        if (src && !src.includes('userscript') && !src.includes('tampermonkey') && !src.includes('greasemonkey') && event.error?.stack?.includes('alive-broadcast') === false) {
            return; // 非本脚本异常，忽略
        }
        const msg = event.message || '未知错误';
        log(`全局异常: ${msg}`, 'error');
        GM_notification({ title: '⚠️ 脚本异常', text: msg.slice(0, 100) });
        sendAlert('脚本异常', msg, '', 'critical');
    });
    window.addEventListener('unhandledrejection', (event) => {
        const reason = event.reason?.message || event.reason || '未知Promise异常';
        const stack = event.reason?.stack || '';
        // 仅捕获脚本自身的Promise异常
        if (stack && !stack.includes('alive-broadcast') && !stack.includes('startCollection') && !stack.includes('scrollAndCollect')) {
            return;
        }
        log(`未捕获Promise异常: ${reason}`, 'error');
        GM_notification({ title: '⚠️ 脚本异常', text: String(reason).slice(0, 100) });
        sendAlert('脚本异常', String(reason), '', 'critical');
    });

    // ========== 主入口 ==========
    log('脚本已加载 v1.5.0');
    
    // 页面类型检测：非目标页面不执行
    const pageType = getPageType();
    if (pageType === 'unknown') {
        log('非目标页面（live-screen/live-comment），脚本不执行');
        return;
    }
    log(`当前页面类型: ${pageType}`);
    
    const pending = GM_getValue('pending_collect', 'false');
    if (pending === 'true') {
        GM_setValue('pending_collect', 'false');
        log('页面已刷新，等待数据加载后开始采集...');
        setTimeout(async () => {
            const ready = await waitForPageReady(60000);
            if (!ready) {
                log('页面未就绪，本次采集放弃，等待心跳下次重试', 'warn');
                GM_notification({ title: '⚠️ 采集延迟', text: '页面数据60秒未加载，等待下次重试' });
                if (pageType === 'live-screen') startHeartbeat();
                return;
            }
            try {
                if (pageType === 'comment-insight') {
                    await collectCommentInsightCollection(true);
                } else {
                    await startCollection(true);
                }
            } catch (e) {
                log(`采集崩溃: ${e.message}\n${e.stack}`, 'error');
                GM_notification({ title: '❌ 采集崩溃', text: e.message.slice(0, 100) });
                sendAlert('脚本崩溃', e.message + '\n' + (e.stack || '').slice(0, 200), '', 'critical');
            }
            // P0修复：pending路径采集完成后必须重启heartbeat，否则Day2+无自动采集
            if (pageType === 'live-screen') startHeartbeat();
        }, 3000);
    } else {
        if (pageType === 'live-screen') startHeartbeat();
    }

    // 暴露给控制台手动触发
    unsafeWindow.startCollection = () => {
        if (pageType === 'comment-insight') {
            return collectCommentInsightCollection(false);
        } else {
            return startCollection(false);
        }
    };
})();
