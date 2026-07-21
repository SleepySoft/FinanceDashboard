# FinanceDashboard AI Skill

This skill defines what the AI agent does within the FinanceDashboard project, how it interacts with the system, and how to deploy/use it.

## Agent Role

The AI agent is the **analysis engine** of FinanceDashboard. It does NOT serve the web interface or manage real-time prices. Its job is:

1. **Claim analysis tasks** from the request pool
2. **Run deep financial analysis** using kimi_finance and Tushare
3. **Write reports** as Markdown files
4. **Mark tasks complete** so the frontend can display results

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

### Current Deployment (Single VM)

```
Tencent Cloud VM (VM-47-161-ubuntu)
├── Port 80  → Uvicorn (FastAPI + StaticFiles, 同时 serve API 和前端)
└── Port 22  → SSH
```

**Start:**
```bash
cd /root/data/FinanceDashboard/backend
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 80
```

- 前端代码改动后需要重新构建：`cd frontend && npm run build`
- 后端使用 `StaticFiles(directory="../frontend/dist", html=True)` 直接 serve 前端
- 已移除 Nginx，不再使用 Vite dev server 或双端口架构

### Data Persistence

All data lives in `/root/data/FinanceDashboard/data/`:
- `data/{code}/meta.json` — stock metadata, tags, cache timestamps
- `data/{code}/reports/` — analysis reports (markdown)
  - **IMPORTANT**: Generate separate files for fundamental and technical analysis
    - `fundamental_YYYYMMDD.md` — type: `fundamental`
    - `technical_YYYYMMDD.md` — type: `technical`
  - **Do NOT** combine both into a single `full` report file
- `data/{code}/briefs.json` — daily briefs
- `data/{code}/notes.md` — user notes
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
