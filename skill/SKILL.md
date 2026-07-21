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

## Deployment

### Current Deployment (Single VM)

```
Tencent Cloud VM (VM-47-161-ubuntu)
├── Port 80  → Vite dev server (frontend)
├── Port 8000 → FastAPI (backend)
└── Port 22  → SSH
```

**Start/Stop:**
```bash
# Backend
cd /root/data/FinanceDashboard/backend
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000

# Frontend
cd /root/data/FinanceDashboard/frontend
npx vite --host 0.0.0.0 --port 80
```

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
User → Tailscale network → 100.105.210.96:80 (frontend)
                              100.105.210.96:8000 (backend API)
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
