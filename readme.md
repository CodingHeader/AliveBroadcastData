# AliveBroadcastData — 抖音直播数据分析系统

## 功能
- 自动采集抖音来客线索大屏数据 (油猴脚本)
- 数据看板 (KPI+趋势+场次+漏斗)
- AI分析报告 (自动+手动)
- 邮件推送 (HTML日报)
- 后台管理 (成单/主播/AI/邮箱/系统设置)

## 快速开始

### 1. 启动服务端
- Windows: 双击 `start.bat`
- Linux: `chmod +x start.sh && ./start.sh`

### 2. 安装油猴脚本
1. 安装 Tampermonkey 浏览器插件
2. 打开 `tampermonkey/alive-broadcast-sync.user.js`
3. 修改 `SERVER_URL` 为你的服务器地址
4. 安装脚本，保持浏览器打开 life.douyin.com

### 3. 后台配置
1. 访问 http://YOUR_IP:12306/admin/login
2. 默认账号: admin / admin123
3. 配置AI (API Key + 模型) 和邮箱 (SMTP + 收件人)

## 技术栈
Python 3.11+ | FastAPI | SQLite | Jinja2 | TailwindCSS | Alpine.js | ECharts

## 定时任务
| 任务 | 时间 | 说明 |
|------|------|------|
| AI分析 | 每小时:05 | 自动分析未分析场次 |
| 日报生成 | 每天01:20 | 聚合前日数据(AI分析后) |
| 邮件推送 | 每天01:30 | 发送日报邮件 |
| 周报 | 每周一02:00 | 聚合上周数据+AI分析 |
| 月报 | 每月1号03:00 | 聚合上月数据 |
| 数据库备份 | 每天04:00 | 保留7天 |

## 常见问题

**Q: 油猴脚本安装后不触发采集？**
A: 确认浏览器保持打开life.douyin.com页面，检查控制台是否有"[直播同步] 脚本已加载"日志。如果没有，检查@match规则是否匹配当前URL。

**Q: 邮件发送失败？**
A: 163邮箱需要开启SMTP服务并获取授权码（非登录密码）。在163邮箱设置→POP3/SMTP中开启，获取授权码填入后台配置。

**Q: AI分析返回空或报错？**
A: 检查后台AI配置的API Key是否有效、base_url是否正确。可点击"测试连接"验证。Github Models的base_url为 https://models.github.ai/inference。

**Q: 数据库报"database is locked"？**
A: 系统已配置WAL模式，正常情况不会出现。如仍出现，重启服务即可。避免同时运行多个服务实例。

**Q: 端口12306被占用？**
A: 修改server/config.py中的PORT为其他端口（如12307），同时更新油猴脚本中的SERVER_URL。

**Q: 修改了.env环境变量但配置没生效？**
A: 环境变量仅在首次初始化data.db时写入settings表。如果data.db已存在，需要：
- 方案1：在后台管理页面手动修改对应配置
- 方案2：删除`server/data.db`后重启服务（会丢失所有数据）
- 方案3：用SQLite工具直接修改settings表中对应key的value
