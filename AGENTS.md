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
Frontend (Vue3 + Vite)          Backend (FastAPI)               Data (File-based)
    Port 80  ────────────►    Port 8000  ────────────►    /root/data/FinanceDashboard/data/
```

| Layer | Tech | Port | Notes |
|-------|------|------|-------|
| Frontend | Vue 3 + Vite | 80 | Hash routing (`/#/stock/002430.SZ`), no auth |
| Backend | Python FastAPI | 8000 | CORS open, no auth (user request) |
| Data | JSON + Markdown | — | One dir per stock, `_dashboard.json` for prices |
| Gateway | OpenClaw | 18789 | localhost only, not exposed |

## Data Layout

```
data/
├── _dashboard.json          # Price snapshot (updated by backend via Sina API)
├── _tasks.json              # Pending analysis task queue
├── _template/
│   └── meta.json            # Template for new stock entries
└── {CODE}/                  # One dir per stock (e.g. 002430.SZ/)
    ├── meta.json            # Tags, marks, cache timestamps, report list
    ├── notes.md             # User notes (markdown, ## timestamp format)
    └── reports/
        ├── fundamental_YYYYMMDD.md
        └── technical_YYYYMMDD.md
```

## Key Design Decisions

1. **No Authentication** — All API endpoints are public. User explicitly requested this.
2. **Two-speed Data** — Real-time prices via Sina API (backend direct); deep analysis via kimi_finance/Tushare (agent tool calls).
3. **Separate Caches** — Fundamental (30 days) and Technical (7 days) have independent expiry and refresh buttons.
4. **Agent-triggered Analysis** — User submits request → pool → agent claims → runs analysis → writes report. No automatic polling.
5. **File-based Storage** — No database. Everything is JSON or Markdown files.

## API Endpoints (Human-facing)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/dashboard` | GET | All stocks with prices and mark diffs |
| `/api/prices/refresh` | GET | Fetch live prices from Sina, update `_dashboard.json` |
| `/api/requests` | GET/POST/DELETE | Request pool (pending analysis tasks) |
| `/api/stocks` | GET | List all analyzed stocks |
| `/api/stocks/{code}` | GET | Stock detail (meta + injected price) |
| `/api/stocks/{code}/tags` | PATCH | Update overall/watchlist tags |
| `/api/stocks/{code}/price-marks` | POST | Add price mark |
| `/api/stocks/{code}/notes` | GET/POST | Notes |
| `/api/stocks/{code}/reports/{id}` | GET | Report content (Markdown) |

## API Endpoints (Agent-facing)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/agent/tasks` | GET | List pending tasks |
| `/api/agent/tasks/{id}/claim` | POST | Claim a task |
| `/api/agent/tasks/{id}/complete` | POST | Submit completed report |
| `/api/agent/tasks/{id}/fail` | POST | Mark task failed |

## External Credentials

- **Tushare Token:** `e637c3252c1aadecdc8a215a59abd44959e70efa5bfe1b36d83447fa`
  - File: `/root/.openclaw/workspace/stock-analyst/.env` (legacy) — TODO: move to project `.env`
- **Sina API:** No auth needed. Used for real-time price snapshots.

## Development Workflow

### Starting Services
```bash
cd /root/data/FinanceDashboard/backend
source venv/bin/activate
nohup uvicorn main:app --host 0.0.0.0 --port 8000 > /tmp/uvicorn.log 2>&1 &

cd /root/data/FinanceDashboard/frontend
nohup npx vite --host 0.0.0.0 --port 80 > /tmp/vite.log 2>&1 &
```

### Adding a New Stock for Analysis
1. User submits via frontend (`/requests`) or tells agent directly
2. Agent calls `POST /api/requests` with code/name/sector/type
3. Agent polls `GET /api/agent/tasks`, claims task
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

- **Tencent Cloud firewall** may block ports 80/8000 from public internet. ufw rules are set, but security group needs manual config in Tencent console.
- **Non-trading hours:** Sina API returns last close price (not stale, just not updating).

## Open TODOs

- [ ] Move `.env` from legacy path to `/root/data/FinanceDashboard/.env`
- [ ] Frontend Markdown rendering: add marked.js for proper tables/code blocks
- [ ] Add stock code validation/normalization (A-share format auto-correction)
- [ ] Consider adding cron for periodic price refresh (currently only manual + frontend poll)
- [ ] Test end-to-end: web submit request → agent claim → analysis → report display
- [ ] Add search/filter to Dashboard

## How to Update This File

When you make a significant change (architecture, new endpoint, credential rotation, deployment change), update this file. Future agents read this first.
