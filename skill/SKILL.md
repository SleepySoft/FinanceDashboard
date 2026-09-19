# FinanceDashboard AI Skill

This skill defines what the AI agent does within the FinanceDashboard project, how it interacts with the system, and how to deploy/use it.

## Agent Role

The AI agent is the **analysis engine** of FinanceDashboard. It does NOT serve the web interface or manage real-time prices. Its job is:

1. **Claim analysis tasks** from the request pool
2. **Run deep financial analysis** using kimi_finance and Tushare
3. **Write reports** as Markdown files
4. **Mark tasks complete** so the frontend can display results

## Hard Constraints (硬性约束)

1. **笔记只能用户写，AI 严禁写笔记** — `data/{code}/notes.md` 是用户的私人记录区。Agent 只负责编写 `reports/` 下的分析报告；**严禁**通过 `POST /api/stocks/{code}/notes` 或直接写文件的方式添加/修改/删除笔记（读取笔记了解用户想法是允许的）。分析结论一律写进报告文件，不是笔记。
2. **「价格网格」= 价格阶梯功能，不是价格标记** — 用户说「设置价格网格/价格阶梯」时，必须使用价格阶梯功能（`backend/ladder.py`）：内置 grid 策略走 `POST /api/stocks/{code}/ladder/strategy`，AI 自定义档位（如压力位/支撑位）走 `PUT /api/agent/stocks/{code}/ladder`。**不要**用 `/api/stocks/{code}/price-marks` 价格标记——它只是单个关注价位的展示，没有买/卖方向、数量和临近/触及提醒语义。
3. **AI 技术面水位标记走专用接口** — 技术面分析得出的阻力位/支撑位/筹码密集区等纯参考价位，用 `PUT /api/agent/stocks/{code}/price-marks` 整体写入（`source=agent`，与手工标记分区共存，前端水位轴展示为紫色 AI 徽标）。**不要**混进 `POST /api/stocks/{code}/price-marks`（那是手工通道），也不要写进 ladder（那是带买卖方向的交易计划）。
4. **写数据文件必须过 schema 校验** — 所有会被载入的 JSON 文件在 `schemas/` 目录有对应 schema（`{文件名}.schema.json`）。Agent 新增/修改 `data/` 下任何 JSON 文件、或改动读写数据文件的代码后，**必须运行 `validate.bat`（或 `python scripts/validate_data.py`）**，全部通过才算完成；新增数据文件种类必须同步在 `schemas/` 新增对应 schema。写数据优先走 API（有 Pydantic 校验），直接写文件时必须严格遵守 `schemas/` 中的结构（字段名、类型、枚举值）。

## What the Agent Does

### 1. Stock Analysis (Primary)

When a user submits an analysis request (or asks directly), the agent:

```
User: "分析 002430.SZ 基本面"
   │
   ▼
Agent checks cache in meta.json
   │
   ├─ Cache valid? → Return cached report (or ask if re-analysis wanted)
   └─ Cache expired / no cache? → Proceed with analysis
   │
   ▼
Agent calls kimi_finance for:
   - Financial statements (income, balance, cash flow)
   - Key metrics (ROE, margin, growth)
   - Historical price data + technical indicators (MA, MACD, KDJ, RSI, BOLL)
   │
   ▼
Agent writes Markdown report to:
   data/{code}/reports/fundamental_YYYYMMDD.md
   data/{code}/reports/technical_YYYYMMDD.md
   │
   ▼
Agent updates meta.json cache timestamps
   │
   ▼
Agent notifies user: "分析完成，报告已生成"
```

### 2. Price Refresh (Secondary)

The backend handles real-time prices via Sina API. The agent only intervenes when:
- User explicitly asks "刷新价格"
- The agent wants to verify current price before giving advice
- Weekend/non-trading hours when Sina has stale data

The agent uses **kimi_finance** (not Sina) for price checks because it also gets technical indicators in one call.

### 3. Task Queue Management

The system has an asynchronous task queue (`data/_tasks.json`):

```
User submits via web → Task created (status: pending)
                           │
                           ▼
Agent polls /api/agent/tasks → Claims task (status: in_progress)
                           │
                           ▼
Agent analyzes → Writes report → Marks complete (status: completed)
                           │
                           ▼
Frontend auto-refreshes → Report appears
```

## How to Use the Agent

> **鉴权（2026-08-11 起）**：所有 `/api/agent/*` 接口需要请求头
> `X-API-Key: <密钥>`（后端 `FD_API_KEY` 或 `data/_secrets.json` 的 `api_key`，
> 首次启动未配置时自动生成；本机 Agent 直接读取项目根目录 `agent_token.txt`，
> 也可登录前端在「设置 → Agent 访问密钥」重新生成）。
> 未带 Key 会返回 401。其余业务接口若后端处于「未登录只读」模式，读接口可匿名访问，
> 写接口同样需要 Key 或登录会话。

### Direct Chat (WeChat)

Users can talk to the agent directly via WeChat (openclaw-weixin channel):

| Command | Action |
|---------|--------|
| "分析 {code}" | Run full analysis (fundamental + technical) |
| "分析 {code} 基本面" | Run fundamental only |
| "分析 {code} 技术面" | Run technical only |
| "刷新价格" | Manually refresh price snapshot via kimi_finance |
| "看看 {code}" | Show current status, latest report summary |
| "标记 {code} {label} {price}" | Add price mark |
| "设置价格网格 {code}" | 用价格阶梯 grid 策略（`/api/stocks/{code}/ladder/strategy`），**不是** price mark |

### Web Interface

Users can also use the web UI at `http://100.105.210.96` or `http://82.156.5.238`:
- Submit analysis requests (goes to task pool)
- View Dashboard with price marks
- Read reports
- Add notes and tags

## Agent Tools Available

| Tool | Purpose | When to Use |
|------|---------|-------------|
| `kimi_finance` | Real-time price + technical indicators | Price checks, technical analysis |
| `kimi_datasource_call` (stock_finance_data) | Historical prices, financial statements | Fundamental analysis, backtesting |
| `kimi_search` | Web search for news/context | Qualitative analysis, recent events |
| `read/write/edit` | File operations | Read/write reports, update meta.json |
| `exec` | Shell commands | Start/stop services, git operations |

## Holdings & T-Trade Tracking (持仓管理)

FinanceDashboard now includes a **position tracking system** that goes beyond simple "average cost" calculations. It tracks every trade, identifies T-trades (intraday buy-sell pairs), and calculates realized/unrealized PnL separately.

### How It Works

**Matching Algorithm: Smart FIFO + Intraday LIFO**

1. **Same-day trades** (做T): Sell matches against same-day buys first (LIFO within day)
   - Example: Buy 1000 @ 10:00, Sell 500 @ 14:00 → Profit = 500 × (sell_price - 10.00)
   - This profit is tracked separately as "T-trade profit"

2. **Cross-day trades**: Standard FIFO for position reduction
   - Example: Day1 Buy 1000 @ 10.00, Day3 Sell 300 @ 12.00 → Matches Day1 position

3. **Short-selling / 反T**: Selling more than you own creates a "short" position
   - Tracked as open short, can be closed by later buys

### Trade Entry API

```bash
# Add a trade
POST /api/holdings/{code}/trades
{
  "date": "2026-07-21",
  "time": "10:30:00",
  "type": "buy",        # or "sell"
  "price": 24.50,
  "quantity": 1000,
  "note": "开盘买入"
}

# Auto-calculated: fee = max(price × qty × 0.00025, 5.00)

# Idempotent: same date/time/price/qty/type won't duplicate

# Get holdings summary
GET /api/holdings/{code}
Response: {
  "summary": {
    "total_quantity": 1000,
    "avg_cost": 10.000,
    "total_cost": 10000.00,
    "realized_pnl": 500.00,    # T-trade profits
    "open_short": 0,
    "last_trade": {...}
  },
  "t_trades": [
    {"type": "正T", "quantity": 500, "profit": 500.00, ...}
  ]
}

# Corporate actions (送转股)
POST /api/holdings/{code}/adjust
{
  "date": "2026-06-15",
  "type": "split",       # or "bonus", "dividend"
  "ratio": 1.3,          # 10送3 → 1.3x
  "dividend_per_share": 0.2
}
```

### Frontend Integration

- Each stock card shows holdings summary (if any): quantity, avg cost, unrealized PnL, T-trade profits
- Click **「记」** button on card to open trade entry modal
- Holdings data auto-refreshes with dashboard

### Data File

Holdings stored in `data/{code}/holdings.json`:
```json
{
  "trades": [...],
  "t_trades": [...],
  "adj_events": [...],
  "summary": {...}
}
```

## Deployment

### Current Deployment

```
Internet → public Nginx → Tailscale → application Nginx :80
                                      ├── /api/* → Uvicorn 127.0.0.1:8010
                                      └── /*     → Vue static files
```

**Start:**
```bash
cd /root/data/FinanceDashboard
sudo ./scripts/install_systemd_service.sh
```

- 前端代码改动后需要重新构建：`cd frontend && npm run build`
- systemd 单元为 `financedashboard.service`，生产模式禁止 `--reload`
- 后端仅监听 `127.0.0.1:8010`；应用主机 Nginx 的 `/api/` 必须反代到该端口
- 公网入口位于另一台 Tailscale 主机，发布地址为 `https://www.sleepysoft.dev/dashboard/`
- 完整部署说明见 `docs/how/linux-deployment.md`

### Data Persistence

All data lives in `/root/data/FinanceDashboard/data/`:
- `data/{code}/meta.json` — stock metadata, tags, cache timestamps
- `data/{code}/reports/` — analysis reports (markdown)
  - **IMPORTANT**: Generate separate files for fundamental and technical analysis
    - `fundamental_YYYYMMDD.md` — type: `fundamental`
    - `technical_YYYYMMDD.md` — type: `technical`
  - **Do NOT** combine both into a single `full` report file
- `data/{code}/briefs.json` — daily briefs
- `data/{code}/notes.md` — user notes（用户专用；Agent 只读，严禁写入，见上方硬性约束）
- `data/_dashboard.json` — price snapshot cache
- `data/_tasks.json` — pending analysis tasks
- Git tracks code, NOT data (data/ is in .gitignore except templates)
- Backup: `rsync -av /root/data/FinanceDashboard/data/ /backup/path/`

### Tailscale Access (Alternative)

If public IP is blocked by Tencent firewall:
```
User → Tailscale network → 100.105.210.96:80 (API + frontend)
```

## Agent Workflow File

The agent should read `/root/data/FinanceDashboard/AGENTS.md` on every session start to understand current project state, open TODOs, and credentials.

## Report Generation Rules

### Critical: Separate Fundamental and Technical Reports

When a user requests `full` analysis (or just "分析 {code}" without specifying type), the agent MUST generate **TWO separate markdown files**:

```
data/{code}/reports/fundamental_YYYYMMDD.md   # type: fundamental
data/{code}/reports/technical_YYYYMMDD.md     # type: technical
```

**Do NOT** put both analyses in a single file. This causes the frontend to show duplicate content in both sections.

When calling the complete API, pass both reports:

```python
# After generating both files
requests.post(f"/api/agent/tasks/{task_id}/complete", json={
    "reports": [
        {"path": f"data/{code}/reports/fundamental_YYYYMMDD.md", "type": "fundamental"},
        {"path": f"data/{code}/reports/technical_YYYYMMDD.md", "type": "technical"}
    ],
    "summary": "分析完成"
})
```

### Single-Type Analysis

When user explicitly asks for one type:
- "分析 {code} 基本面" → only `fundamental_YYYYMMDD.md`
- "分析 {code} 技术面" → only `technical_YYYYMMDD.md`

In this case, call complete with single report:

```python
requests.post(f"/api/agent/tasks/{task_id}/complete", json={
    "report_path": f"data/{code}/reports/fundamental_YYYYMMDD.md",
    "report_type": "fundamental",
    "summary": "基本面分析完成"
})
```

## Analysis Standards

### Fundamental Analysis Report Format

```markdown
# {Stock Name} ({Code}) 基本面分析

## 核心结论
一句话观点 + 标签建议（看好/观望/回避）

## 财务概览
- 营收趋势（近3-5年）
- 利润趋势
- 现金流状况

## 关键指标
| 指标 | 数值 | 评价 |
|------|------|------|
| ROE | xx% | 高/中/低 |
| 毛利率 | xx% | 趋势 ↑↓→ |

## 风险与机会
...因果分析，不是罗列...

## 总结
...
```

### Technical Analysis Report Format

```markdown
# {Stock Name} ({Code}) 技术面分析

## 走势概览
当前价、涨跌幅、 vs 均线位置

## 技术指标
- MA: 5/10/20/60 日均线及排列
- MACD: DIF/DEA/柱状线
- KDJ: K/D/J 值及位置
- RSI: 6/12/24
- BOLL: 上轨/中轨/下轨

## 关键价位
支撑位 / 阻力位

## 短期判断
...
```

## Communication Style

- **Language:** Chinese ( user's preference)
- **Tone:** Professional but conversational, causal analysis over raw data dumps
- **Must include:** Clear opinion (看好/观望/回避), not fence-sitting
- **Must explain WHY**, not just WHAT

## Security Notes

- Root SSH is enabled (user request)
- No API authentication (user request)
- Gateway port 18789 is localhost-only
- Tushare token is stored in plaintext — do not expose
