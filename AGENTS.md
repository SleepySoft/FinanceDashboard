# AGENTS.md - FinanceDashboard Development Context

This file captures the living state of the project so any AI (or future-you) can pick up where we left off without asking 20 questions.

## Project Identity

- **Name:** FinanceDashboard
- **Path:** `/root/data/FinanceDashboard/`
- **Purpose:** Personal stock analysis dashboard — track stocks, tag them, mark prices, run fundamental/technical analysis
- **Owner:** Sleepy (sleepysoft@gmail.com)
- **Runtime User:** root (uid=0) on VM-47-161-ubuntu (Tencent Cloud)

## Architecture

```
Internet: https://www.sleepysoft.dev/dashboard/
  │
  ▼
公网入口 Nginx（经 Tailscale 反代）
  │
  ▼
应用主机 100.105.210.96:80（Nginx）
  ├── /api/* → 127.0.0.1:8010（systemd + Uvicorn + FastAPI）
  └── /*     → /var/www/financedashboard（Vue3 静态文件）
                │
                ▼
          /root/data/FinanceDashboard/data/
```

| Layer | Tech | Port | Notes |
|-------|------|------|-------|
| Public Gateway | Nginx on remote Tailscale host | 443 | 发布 `/dashboard/`，API 仍使用 `/api/*` |
| App Gateway | Nginx | 80 | 静态文件 + `/api/` 反代 |
| App Server | systemd + Uvicorn + FastAPI | 127.0.0.1:8010 | 单元 `financedashboard.service`，禁止生产使用 `--reload` |
| Data | JSON + Markdown | — | One dir per stock, `_dashboard.json` for prices |
| Auth | backend/auth.py（stdlib，无新依赖） | — | PBKDF2 密码哈希 + 文件会话 + 权限配置 |
| Gateway | OpenClaw | 18789 | localhost only, not exposed |

## Data Layout

```
data/
├── _dashboard.json          # Price snapshot (updated by backend via Sina API)
├── _tasks.json              # Pending analysis task queue
├── _users.json              # 用户账号（PBKDF2 密码哈希；首次运行自动创建 admin）
├── _sessions.json           # 登录会话（token → username/expires_at）
├── _config.json             # 普通配置（权限 / 分类标签 / 定时任务间隔等，可入库）
├── _secrets.json            # 敏感配置（api_key / tushare_token，git 忽略）
├── _providers.json          # 交易数据网站跳转配置（网站 + URL 模板 + 默认网站）
├── _template/
│   └── meta.json            # Template for new stock entries
└── {CODE}/                  # One dir per stock (e.g. 002430.SZ/)
    ├── meta.json            # Tags, marks, cache timestamps, report list
    ├── notes.md             # User notes (markdown, ## timestamp format)
    ├── holdings.json        # Trade history + T-trade analysis + position summary
    └── reports/
        ├── fundamental_YYYYMMDD.md   # Fundamental analysis ONLY
        └── technical_YYYYMMDD.md     # Technical analysis ONLY
```

**IMPORTANT:** Never combine fundamental and technical into one file. When doing `full` analysis, generate two separate files and call complete API with `reports: [{path, type}, {path, type}]`.

## Key Design Decisions

1. **No Authentication** — All API endpoints are public. User explicitly requested this.
   **已变更（2026-08-11）**：接入登录与权限控制，默认未登录完全锁定。
2. **Two-speed Data** — Real-time prices via Sina API (backend direct); deep analysis via kimi_finance/Tushare (agent tool calls).
3. **Separate Caches** — Fundamental (30 days) and Technical (7 days) have independent expiry and refresh buttons.
4. **Agent-triggered Analysis** — User submits request → pool → agent claims → runs analysis → writes report. No automatic polling.
5. **File-based Storage** — No database. Everything is JSON or Markdown files.
6. **Unread Tag** — Agent `complete` 后 `tags.unread=true`，看板显示红色「未读」徽章；用户打开个股面板/详情页时前端自动 PATCH 清除。
7. **后台定时任务（2026-08-16 新增）** — 后端内置 asyncio 调度器：价格刷新（默认每 5 分钟）与异动扫描（默认关闭），
   间隔在「设置 → 自动更新」页配置，存于 `data/_config.json`，修改后下个周期生效，无需重启。
8. **数据文件防护（2026-08-19 新增）** — 原则：任何单个数据文件损坏都不能让接口 500。
   - 读取统一走 `main.py:_safe_json_load()`（解析失败/类型不符 → 返回默认值并打 `[data-guard]` 日志）；
   - 写入统一走 `_atomic_json_dump()`（临时文件 + `os.replace`，杜绝写盘半截留下坏 JSON；`auth.py:_save_json` 同样原子写）；
   - `/api/dashboard`、`/api/stocks`、`/api/holdings` 逐个股票隔离：单股数据异常只跳过该股票；
   - `_scan_reports` 对文件名日期段做校验，非法日期 `created_at` 置空，`id` 直接用文件名主干；
  - 注册子系统同样隔离坏文件：异动与交易网站配置使用安全读取和原子写，回测策略元数据/记录使用项目相对路径、类型校验和原子写；
   - FastAPI 全局 `exception_handler` 把未处理异常转为结构化 500 JSON 并打印堆栈；
  - 前端主页、请求池和持仓页加载失败显示错误横幅 + 重试按钮；股票面板对笔记、持仓、供应商等附属接口逐项降级，不再因单项失败白屏；
  - 回归测试脚本：`scripts/fault_injection_test.ps1`（仓库相对路径，注入坏 JSON、错误字段类型、非 UTF-8 notes 和异常报告名，验证接口仍 200 并自动恢复数据）；`frontend/tests/smoke.mjs` 同时模拟附属接口返回损坏 JSON。
9. **记录价格快照（2026-09-03 新增）** — 新增笔记和 Agent 完成分析时，从 `_dashboard.json` 读取可用价格并写入股票 `state.json.record_prices`；时间线按固定列显示，旧记录或取价失败显示 `--`。报告键为文件名主干，笔记键为 `##` 时间戳。

## 登录与权限（2026-08-11 新增）

- 认证实现：`backend/auth.py`（纯 stdlib：hashlib.pbkdf2_hmac + hmac + secrets），无新增依赖。
- 登录会话：`data/_sessions.json` + HttpOnly Cookie `fd_session`（SameSite=Lax，默认 7 天）。
- 用户角色（`_users.json` 的 `role` 字段）：
  - `admin`：全部权限，含用户管理、权限/分类/Tushare/定时任务配置、密钥重新生成；
  - `readonly`：只读账号（分享给朋友用），可浏览全部数据，所有写操作被中间件拦截返回 403
    （`/api/auth/*` 除外：可改自己的密码、登出）；老数据无 `role` 字段一律按 `admin` 兼容；
  - 前端 `useAuth.canWrite` = 仅 admin，只读账号登录后所有写操作按钮自动隐藏；
  - 用户管理接口（仅 admin）：`GET/POST /api/auth/users`、`DELETE /api/auth/users/{name}`、
    `POST /api/auth/users/{name}/password`（重置后吊销该用户全部会话）；不能删除自己或最后一个 admin。
  - 只读写白名单：`/api/pow`、`/api/messages`、`/api/stocks/*/feedback`（只读账号可发消息/投票，
    其余写操作仍 403）。

## 消息箱与股票反馈（POW 防刷屏）

- 协议与复用指南：`docs/powbox-design.md`；模块 `backend/powbox/` + `frontend/src/powbox/`（均自包含可拷走）。
- POW 绑定提交内容（消息=正文；反馈=`{code}|{vote}|{comment}`），challenge 自包含签名、10 分钟有效、
  不记历史：反馈 upsert 幂等，消息按「10 分钟内同用户同内容」去重。
- 消息箱 `data/_messages.json`：用户 → 站主单向信箱；admin 看全部/可删，用户只看自己；`/messages` 页。
- 股票反馈 `data/{code}/feedback.json`：每人一票（赞同/反对 + 可选评论，upsert 覆盖，不记历史），
  可撤回自己的；admin 可删任意条目；展示在 StockPanel「股友反馈」区块。
- 发消息/提交反馈需完成 POW（`PowPanel` 组件含说明、难度滑块、耗时预估、进度条）。
- 首次运行：访问 `/api/auth/config` 时自动创建管理员账号。
  - 用户名：环境变量 `FD_ADMIN_USERNAME`（默认 `admin`）
  - 密码：环境变量 `FD_ADMIN_PASSWORD`；未设置则使用默认密码
    `SleepySoft@299792458`（与 SSH 密码一致，登录后建议尽快在「设置」中修改）
- 未登录权限配置（`data/_config.json`，可在前端「设置」页修改）：
  - `allow_anonymous_read: false`（默认）= 完全锁定，未登录看不到任何数据
  - `allow_anonymous_read: true` = 未登录只读，可浏览但所有写操作返回 401
- 配置拆分（2026 起）：普通配置存 `data/_config.json`（**已纳入 git**）；敏感项 `api_key` / `tushare_token`
  存 `data/_secrets.json`（git 忽略）。读取时两文件合并（secrets 优先），写盘时自动拆分；
  旧版写在 `_config.json` 里的敏感项首次读取时自动迁移到 `_secrets.json`。
- 其他配置项（「设置」页可修改）：
  - `tushare_token`：Tushare Pro token（优先级：环境变量 `TUSHARE_TOKEN` → `data/_secrets.json` → 项目 `.env`），接口不回显明文
  - `price_refresh_interval_min`：价格自动刷新间隔（分钟，默认 5，0=关闭）
  - `anomaly_scan_interval_min`：异动自动扫描间隔（分钟，默认 0=关闭，需先配置 Tushare token）
  - `status_categories`：股票分类标签（投资状态）有序列表 `[{key, label, desc}]`，「设置」页可改名/新增/删除/拖动排序，
    `desc` 为分类说明（可选，≤200 字），鼠标悬停在卡片徽章/分组标题/下拉选项上时悬浮显示；
    首页分组与状态下拉顺序均按此列表；内置兜底分类 `none`（无分类）不可删除、不出现在下拉中，
    删除有股票的分类时其股票 `status` 自动改写为 `none`，看板仅在有股票时于最后显示「无分类」组
    （status 不在配置列表中的股票也归入此组）。key 规则 `^[a-z0-9_]{1,32}$` 且不能为 `none`。
  - `pow_difficulty`：POW 最低难度（bit，8~28，默认 20），「设置 → 防刷屏验证」可改，立即生效
- 写操作定义：所有非 GET/HEAD，以及 `GET /api/prices/refresh`、`GET /api/dashboard/refresh`（会改动数据）。
- Agent 访问：请求头 `X-API-Key`。密钥只落盘在本机：
  - 首次启动未设置 `FD_API_KEY` 时自动生成，写入 `data/_secrets.json`，
    并同步写入项目根目录 `agent_token.txt`（本地 Agent 直接读取该文件）；
  - 前端「设置 → Agent 访问密钥」可重新生成（`POST /api/auth/token/regenerate`，
    旧密钥立即失效，接口不返回明文，避免远程暴露）；
  - 也可在部署时用环境变量 `FD_API_KEY` 固定（优先级最高）。
  带 Key 的请求可访问全部接口（含 `/api/agent/*`，该前缀不参与"未登录只读"）。
- 修改密码：`POST /api/auth/change-password`，修改后会吊销该用户其他会话（当前会话保留）。

## API Endpoints (Human-facing)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/auth/config` | GET | 公开：权限配置 + Tushare/定时任务配置状态（登录页/前端引导用） |
| `/api/auth/me` | GET | 当前登录状态 |
| `/api/auth/login` | POST | 登录（设置 HttpOnly Cookie） |
| `/api/auth/logout` | POST | 登出 |
| `/api/auth/change-password` | POST | 修改密码（需登录） |
| `/api/auth/users` | GET/POST | 用户管理：列表 / 创建账号（仅 admin，role: admin/readonly） |
| `/api/auth/users/{name}` | DELETE | 删除账号并吊销其会话（仅 admin，不能删自己/最后一个 admin） |
| `/api/auth/users/{name}/password` | POST | 重置指定用户密码并吊销其会话（仅 admin） |
| `/api/auth/config` | PATCH | 修改权限/Tushare token/定时任务间隔（需登录） |
| `/api/dashboard` | GET | All stocks with prices and mark diffs |
| `/api/prices/refresh` | GET | Fetch live prices from Sina, update `_dashboard.json` |
| `/api/scheduler/status` | GET | 定时任务运行状态（间隔、上次/下次运行、结果/错误） |
| `/api/tushare/test` | POST | 测试 Tushare token 连通性（需登录，不保存） |
| `/api/requests` | GET/POST/DELETE | Request pool (pending analysis tasks) |
| `/api/stocks` | GET | List all analyzed stocks |
| `/api/stocks/{code}` | GET | Stock detail (meta + injected price) |
| `/api/stocks/{code}/tags` | PATCH | Update overall/watchlist/unread tags |
| `/api/stocks/{code}/price-marks` | POST | Add price mark |
| `/api/stocks/{code}/notes` | GET/POST | Notes |
| `/api/stocks/{code}/notes/{time}` | DELETE | Delete note(s) by timestamp |
| `/api/stocks/{code}/reports/{id}` | GET | Report content (Markdown) |
| `/api/holdings` | GET | List all holdings summaries |
| `/api/holdings/{code}` | GET | Holdings detail (position + T-trades) |
| `/api/holdings/{code}/trades` | POST | Record a trade (buy/sell) |
| `/api/holdings/{code}/trades/{id}` | DELETE | Remove a trade and rebuild |
| `/api/holdings/{code}/adjust` | POST | Corporate action (split/bonus/dividend) |
| `/api/providers` | GET | 交易数据网站列表（含默认网站） |
| `/api/providers/links/{code}` | GET | 指定股票在各网站的跳转链接 |
| `/api/providers/default` | PATCH | 设置默认跳转网站（写入 `_providers.json`） |
| `/api/pow/challenge` | POST | 签发 POW challenge（需登录，body: scope） |
| `/api/pow/config` | GET | POW 当前最低难度与参考计算量（需登录） |
| `/api/messages` | GET/POST | 消息箱：列表（admin 全部/用户看自己）/ 发消息（需 POW） |
| `/api/messages/{id}` | DELETE | 删除消息（仅 admin） |
| `/api/stocks/{code}/feedback` | GET/POST/DELETE | 股票反馈：汇总+评论 / 投票（需 POW）/ 撤回自己的 |
| `/api/stocks/{code}/feedback/{name}` | DELETE | 删除指定用户反馈（仅 admin） |

## API Endpoints (Agent-facing)

> Agent 请求需携带 `X-API-Key: <api_key>`（见「登录与权限」），否则返回 401。

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/agent/tasks` | GET | List pending tasks |
| `/api/agent/tasks/{id}/claim` | POST | Claim a task |
| `/api/agent/tasks/{id}/complete` | POST | Submit completed report |
| `/api/agent/tasks/{id}/fail` | POST | Mark task failed |

## External Credentials

- **登录账号**：首次启动自动创建，见上文「登录与权限」。可用 `FD_ADMIN_USERNAME` / `FD_ADMIN_PASSWORD` / `FD_API_KEY` 环境变量初始化。
- **Tushare Token:** `e637c3252c1aadecdc8a215a59abd44959e70efa5bfe1b36d83447fa`
  - 配置位置：`data/_secrets.json` 的 `tushare_token`（优先级：环境变量 `TUSHARE_TOKEN` → `_secrets.json` → 项目 `.env`）
  - 使用点：异动扫描（`backend/subsystems/anomaly/core.py` TushareClient）、回测数据源（`backend/subsystems/backtest/backtest/data_provider.py`）
  - Legacy: `/root/.openclaw/workspace/stock-analyst/.env`
- **Sina API:** No auth needed. Used for real-time price snapshots.

## Development Workflow

### Starting Services

#### Linux / macOS
```bash
cd /root/data/FinanceDashboard
sudo ./scripts/install_systemd_service.sh
```
- systemd 单元：`financedashboard.service`，默认监听 `127.0.0.1:8010`
- 生产启动脚本：`backend/start_production.sh`（无 `--reload`，避免文件监控高 CPU）
- 运维：`systemctl restart financedashboard`；日志：`journalctl -u financedashboard -f`
- Nginx 的 `/api/` 上游必须指向 `http://127.0.0.1:8010`
- 前端改动后需要 `npm run build` 重新构建

#### Windows
项目根目录提供一键脚本（自动创建虚拟环境、安装依赖并启动前后端）：
```cmd
start_all.bat      :: 启动后端(8010) + 前端(默认80，可传端口参数)
stop_all.bat       :: 停止前后端（含 --reload 派生的 worker 进程）
restart_all.bat    :: 重启（可传前端端口参数，如 restart_all.bat 5173）
```
> 说明：本机 8000 端口曾被其他项目占用，开发和生产后端统一使用 8010；生产入口 80 端口由 Nginx 监听。
单独启动：
```cmd
cd backend && start.bat
cd frontend && start.bat
```
生产部署：
```cmd
cd frontend && build.bat
cd backend && start_production.bat
```
详见 [docs/windows-setup.md](docs/windows-setup.md)。

Linux 生产拓扑、发布和故障排查详见 [docs/linux-deployment.md](docs/linux-deployment.md)。

### Dependency Files
- 后端：`backend/requirements.txt`（FastAPI + Uvicorn + Pydantic）
- 前端：`frontend/package.json`（Vue 3 + Vite + Axios + Vue Router）

### Code Quality Gates (frontend/)
```cmd
cd frontend
npm run lint    # ESLint (flat config, no-undef=error)。autoTimer 事故后引入
npm run smoke   # 冒烟测试：自动拉起前后端 → 无头 Chrome 验证股票卡片渲染 + 视图切换 + 无 JS 错误
```
根目录也提供一键脚本：`lint.bat`、`smoke.bat`（注意：必须在 frontend/ 目录或用这两个 bat，项目根目录没有 package.json）
- 冒烟测试脚本：`frontend/tests/smoke.mjs`（playwright-core + 系统 Chrome，无需下载浏览器）
- 修改任何 `.vue`/`.js` 后、提交前，务必跑这两个命令

### Mobile State Persistence (2026-08-02)

- 页面上下文同步到 URL query（`?view=` `?group=` `?watchlist=` `?holdings=`），详情页阅读位置同步到 `?open=<timeline key>`，手机切后台被浏览器刷新/分享链接后均可恢复。
- 草稿与 UI 状态存 sessionStorage（key 前缀 `fd:`）：笔记/价格标记草稿、交易录入表单、折叠分组、展开条目、滚动位置、异动雷达日期与筛选、请求页表单。
- 统一封装在 `frontend/src/composables/useSession.js`（`usePersistentRef` / `usePersistentSet` / `useScrollRestore` / `readState` / `writeState` / `removeState`）。
- 路由容器按 `$route.path` 加 key，避免切换股票时复用旧组件；`main.js` 在跨页跳转时回顶。

### Adding a New Stock for Analysis
1. User submits via frontend (`/requests`) or tells agent directly
2. Agent calls `POST /api/requests` with code/name/sector/type
3. Agent polls `GET /api/agent/tasks`（带 `X-API-Key`）, claims task
4. Agent runs analysis (kimi_finance/Tushare)
5. Agent writes report to `data/{code}/reports/`
6. Agent calls `POST /api/agent/tasks/{id}/complete`

### Refreshing Prices
- Backend endpoint `GET /api/prices/refresh` fetches from Sina
- Frontend auto-polls Dashboard every 30 seconds
- Manual refresh button also available

## Environment

- **OS:** Ubuntu 22.04, Linux 6.8.0-71-generic
- **Host:** VM-47-161-ubuntu (Tencent Cloud)
- **Public IP:** 82.156.5.238
- **Tailscale IP:** 100.105.210.96
- **Node:** v24.16.0
- **Python:** 3.12 (venv in backend/venv/)
- **RAM:** 7.5GB

## SSH Access

- Root login: **enabled** (user explicitly requested)
- Key auth: available at `~/.ssh/id_rsa.pub`
- Password: `SleepySoft@299792458` (same as Ubuntu)

## Known Issues

- **Tencent Cloud firewall** may block port 80 from public internet. ufw rules are set, but security group needs manual config in Tencent console.
- **Nginx removed**: 2025-07-21 起，前端静态文件由 FastAPI `StaticFiles` 直接 serve，不再使用 Nginx 或 Vite dev server。

## Open TODOs

- [x] **Separate fundamental/technical reports** — Backend API now supports `reports` array in complete endpoint. Agent MUST generate two files for `full` analysis.
- [x] **Holdings & T-trade tracking** — Smart FIFO + intraday LIFO matching, trade entry modal, holdings display on cards
- [x] Tushare token 迁入 `data/_config.json`（`tushare_token`），代码统一从配置读取
- [x] Windows startup scripts (`start_all.bat`, `backend/start.bat`, `frontend/start.bat`) and dependency docs (`docs/windows-setup.md`)
- [ ] Frontend Markdown rendering: add marked.js for proper tables/code blocks
- [ ] Add stock code validation/normalization (A-share format auto-correction)
- [x] 价格自动刷新定时任务（后台 asyncio 调度器 + 设置页可配置间隔，2026-08-16）
- [ ] Test end-to-end: web submit request → agent claim → analysis → report display
- [ ] Add search/filter to Dashboard
- [ ] OCR trade entry from screenshots (user uploads screenshot → auto-recognize price/qty)

## How to Update This File

When you make a significant change (architecture, new endpoint, credential rotation, deployment change), update this file. Future agents read this first.
