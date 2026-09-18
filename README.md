# FinanceDashboard

个人定制化的股票分析看板，支持多维度标签评估、技术分析、基本面分析、以及持仓管理。

## 功能

### 1. 股票跟踪与评估
- 多维度标签系统：质量、估值、时机、风险、综合 verdict
- 价格标记：在关键价位设置买入/卖出/关注标记
- 状态分组：跟踪中、看好、观望、回避、归档

### 2. 分析报告
- 基本面分析（财务指标、行业对比、竞争力）
- 技术面分析（均线、MACD、KDJ、RSI、BOLL）
- 每日简报（基于当天走势和新闻的简短更新）
- 报告自动缓存，避免重复分析

### 3. 持仓管理（新）
- 逐笔成交录入，支持幂等保护
- 智能匹配算法：日内做T自动识别，跨天走FIFO
- 自动计算手续费（万2.5，最低5元）
- 实时显示：持仓数量、成本、浮动盈亏、做T利润

### 4. 前端看板
- 分组视图（按状态/评级/行业）
- 矩阵视图（质量 × 估值）
- 股票详情弹窗/独立页面
- 支持手机端访问

### 5. 登录与权限控制
- 登录 / 登出 / 修改密码（前端「设置」页）
- 未登录权限可配置：
  - **完全锁定**（默认）：未登录看不到任何数据，一律跳转登录页
  - **只读模式**：未登录可浏览，所有修改操作需登录
- 会话基于 HttpOnly Cookie，默认有效期 7 天

## 技术栈

- **Backend**: FastAPI + Python
- **Frontend**: Vue 3 + Vite
- **数据源**: Sina实时行情、kimi_finance（同花顺）、Tushare
- **部署**: Uvicorn（默认 `127.0.0.1:8010`）+ systemd，前置 Nginx 提供静态文件与 API 反代

## 目录结构

```
FinanceDashboard/
├── backend/           # FastAPI 服务
├── frontend/          # Vue3 前端
├── data/             # 股票数据（每只股票一个目录）
│   ├── {code}/
│   │   ├── meta.json        # 元数据、标签、缓存
│   │   ├── reports/         # 分析报告
│   │   ├── briefs.json      # 每日简报
│   │   ├── holdings.json    # 持仓记录
│   │   └── notes.md         # 笔记
│   ├── _dashboard.json      # 价格缓存
│   └── _tasks.json          # 分析任务队列
│   ├── _users.json          # 用户账号（PBKDF2 密码哈希）
│   ├── _sessions.json       # 登录会话
│   └── _config.json         # 普通配置（权限/分类标签等，入库）
│   └── _secrets.json        # 敏感配置（api_key/tushare_token，git 忽略）
├── skill/            # AI Agent Skill 定义
├── schemas/          # 数据文件 JSON Schema（validate.bat 校验）
└── docs/             # 文档（按 WHY/WHAT/HOW 组织，见 docs/README.md）
    ├── why/          # 为什么：动机、选型、复盘
    ├── what/         # 是什么：数据/分析/模块规范
    └── how/          # 怎么做：安装、部署、运维
```

## 登录与权限配置

首次访问时后端会自动创建管理员账号：

```bash
# 可选：指定初始账号/密码（不设置则默认 admin / SleepySoft@299792458）
export FD_ADMIN_USERNAME=admin
export FD_ADMIN_PASSWORD='你的密码'
```

登录后在「设置」页可以修改密码，以及切换「完全锁定 / 只读模式」。

AI Agent 需要额外配置访问密钥：

```bash
# 不设置则首次启动自动生成，并写入项目根目录 agent_token.txt
export FD_API_KEY='一段随机字符串'
```

Agent 请求时携带请求头 `X-API-Key: <密钥>` 即可通过鉴权。

本机 Agent 最简单的方式：登录后在「设置 → Agent 访问密钥」点击「生成新 Token」，
后端会把密钥写入项目根目录 `agent_token.txt`（不会通过接口返回明文），
本地 Agent 直接读取该文件即可，例如：

```bash
TOKEN=$(cat agent_token.txt)
curl -H "X-API-Key: $TOKEN" http://localhost:8010/api/agent/tasks
```

## 快速开始

### Linux / macOS 开发

```bash
# 构建前端（如有代码改动）
cd frontend
npm run build

# 启动开发后端
cd backend
source venv/bin/activate
uvicorn main:app --host 127.0.0.1 --port 8010 --reload
```

### Linux 生产部署

生产服务器使用 systemd 管理后端。首次部署或服务配置更新后执行：

```bash
cd /root/data/FinanceDashboard
sudo ./scripts/install_systemd_service.sh
```

脚本会注册并启动 `financedashboard.service`，默认仅监听
`127.0.0.1:8010`，同时替换该项目中遗留的 `uvicorn --reload` 开发进程。
可在项目根目录的 `.env` 中设置 `FD_HOST`、`FD_PORT` 等环境变量。

```bash
systemctl status financedashboard
journalctl -u financedashboard -f
```

当前公网通过另一台 Tailscale 主机反向代理发布，应用主机 Nginx 将 `/api/`
转发到 `127.0.0.1:8010`。完整拓扑、前端发布、更新和 502 排查步骤见
[Linux 生产部署](docs/how/linux-deployment.md)。

### Windows

项目已提供 Windows 批处理脚本，详见 [docs/how/windows-setup.md](docs/how/windows-setup.md)。

```powershell
# 一键启动后端 + 前端（推荐）
start_all.bat

# 或分别启动
cd backend && start.bat
cd frontend && start.bat

# 生产部署：先构建前端，再由后端统一 serve
cd frontend && build.bat
cd backend && start_production.bat
```

## AI Agent 使用

Agent 负责深度分析，用户可以通过微信直接交互：

| 命令 | 功能 |
|------|------|
| "分析 {code}" | 生成基本面+技术面报告 |
| "刷新价格" | 更新所有股票价格 |
| "标记 {code} {label} {price}" | 添加价格标记 |
| "录入 {code} 买入/卖出 {price} {qty}" | 录入成交 |
| "持仓 {code}" | 查看持仓分析 |

详见 [skill/SKILL.md](skill/SKILL.md)
