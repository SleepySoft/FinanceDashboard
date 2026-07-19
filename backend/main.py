from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Literal
import json
import os
import uuid
import subprocess
from datetime import datetime, timezone, timedelta

app = FastAPI(title="Stock Analyst API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(os.path.dirname(BASE_DIR), "data")
TASKS_FILE = os.path.join(REPORTS_DIR, "_tasks.json")
DASHBOARD_FILE = os.path.join(REPORTS_DIR, "_dashboard.json")

os.makedirs(REPORTS_DIR, exist_ok=True)

# ─── Price Refresh Helper ───────────────────────────
# Real-time prices: backend calls Sina API directly (fast, no agent dependency)
# Analysis data: agent uses kimi_finance (deep financials, technicals)

def _get_stock_codes() -> list:
    """Get all stock codes from the reports directory."""
    codes = []
    for entry in os.listdir(REPORTS_DIR):
        if entry.startswith("_"):
            continue
        meta_path = os.path.join(REPORTS_DIR, entry, "meta.json")
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                codes.append(meta["code"])
            except:
                pass
    return codes

def _fetch_prices_sina(codes: list) -> dict:
    """Fetch real-time prices from Sina Finance API."""
    if not codes:
        return {}
    
    sina_codes = []
    for c in codes:
        c = c.upper().strip()
        if ".SZ" in c:
            num = c.replace(".SZ", "").replace(".", "").replace("-", "")
            sina_codes.append("sz" + num)
        elif ".SH" in c:
            num = c.replace(".SH", "").replace(".", "").replace("-", "")
            sina_codes.append("sh" + num)
        elif ".BJ" in c:
            num = c.replace(".BJ", "").replace(".", "").replace("-", "")
            sina_codes.append("bj" + num)
        else:
            sina_codes.append("sz" + c.replace(".", "").replace("-", ""))
    
    try:
        import urllib.request
        url = f"https://hq.sinajs.cn/list={','.join(sina_codes)}"
        req = urllib.request.Request(url, headers={"Referer": "https://finance.sina.com.cn"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read().decode("gbk")
        
        prices = {}
        for line in data.strip().split(";"):
            line = line.strip()
            if not line or "=" not in line:
                continue
            parts = line.split("=")
            if len(parts) < 2:
                continue
            code_key = parts[0].split("_")[-1]
            raw = parts[1].strip('"')
            if not raw or raw == "" or raw.startswith("FAILED"):
                continue
            fields = raw.split(",")
            if len(fields) < 5:
                continue
            try:
                current = float(fields[3])
                prev_close = float(fields[2])
                change_pct = ((current - prev_close) / prev_close) * 100 if prev_close > 0 else 0
                if code_key.startswith("sz"):
                    our_code = code_key[2:] + ".SZ"
                elif code_key.startswith("sh"):
                    our_code = code_key[2:] + ".SH"
                elif code_key.startswith("bj"):
                    our_code = code_key[2:] + ".BJ"
                else:
                    our_code = code_key.upper()
                prices[our_code] = {
                    "price": current,
                    "change_pct": round(change_pct, 2),
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }
            except (ValueError, IndexError):
                continue
        return prices
    except Exception as e:
        print(f"Price fetch error: {e}")
        return {}

def _update_dashboard_prices(prices: dict):
    """Update _dashboard.json with new prices."""
    dashboard = {"prices": {}, "last_update": _now()}
    if os.path.exists(DASHBOARD_FILE):
        try:
            with open(DASHBOARD_FILE, "r", encoding="utf-8") as f:
                dashboard = json.load(f)
        except:
            pass
    if "prices" not in dashboard:
        dashboard["prices"] = {}
    for code, data in prices.items():
        dashboard["prices"][code] = data
    dashboard["last_update"] = _now()
    with open(DASHBOARD_FILE, "w", encoding="utf-8") as f:
        json.dump(dashboard, f, ensure_ascii=False, indent=2)

# ─── Helpers ──────────────────────────────────────────

def _stock_dir(code: str) -> str:
    return os.path.join(REPORTS_DIR, code)

def _meta_path(code: str) -> str:
    return os.path.join(_stock_dir(code), "meta.json")

def _reports_dir(code: str) -> str:
    return os.path.join(_stock_dir(code), "reports")

def _notes_path(code: str) -> str:
    return os.path.join(_stock_dir(code), "notes.md")

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _load_meta(code: str) -> dict:
    path = _meta_path(code)
    if not os.path.exists(path):
        raise HTTPException(404, f"Stock {code} not found")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _save_meta(code: str, meta: dict):
    path = _meta_path(code)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

def _load_tasks() -> list:
    if not os.path.exists(TASKS_FILE):
        return []
    with open(TASKS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def _save_tasks(tasks: list):
    with open(TASKS_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)

def _load_dashboard() -> dict:
    if not os.path.exists(DASHBOARD_FILE):
        return {"prices": {}, "last_update": None}
    with open(DASHBOARD_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def _init_stock(code: str, name: str = "", sector: str = "") -> dict:
    d = _stock_dir(code)
    os.makedirs(os.path.join(d, "reports"), exist_ok=True)
    meta = {
        "code": code,
        "name": name or code,
        "sector": sector,
        "added_at": _now(),
        "tags": {"overall": "none", "watchlist": False},
        "price_marks": [],
        "notes": [],
        "cache": {
            "fundamental": {"last": None, "valid_until": None},
            "technical": {"last": None, "valid_until": None}
        },
        "reports": []
    }
    _save_meta(code, meta)
    open(os.path.join(d, "notes.md"), "a").close()
    return meta

# ─── Models ───────────────────────────────────────────

class SubmitRequestReq(BaseModel):
    code: str
    name: str = ""
    sector: str = ""
    note: str = ""
    type: Literal["fundamental", "technical", "full"] = "full"

class TagUpdateReq(BaseModel):
    overall: Optional[Literal["green", "yellow", "red", "none"]] = None
    watchlist: Optional[bool] = None

class PriceMarkReq(BaseModel):
    label: str
    price: float
    type: Literal["buy", "sell", "stop", "target", "other"] = "other"

class NoteReq(BaseModel):
    content: str

class AgentTaskCompleteReq(BaseModel):
    report_path: Optional[str] = None
    summary: Optional[str] = None
    report_type: Literal["fundamental", "technical", "full"] = "full"

class AgentTaskFailReq(BaseModel):
    reason: str

# ─── Request Pool (Pending Requests) ───────────────────

@app.get("/api/requests")
def list_requests():
    """List pending requests (submitted by user, not yet analyzed)"""
    tasks = _load_tasks()
    pending = [t for t in tasks if t["status"] in ("pending", "failed")]
    return pending

@app.post("/api/requests")
def submit_request(req: SubmitRequestReq):
    """Submit a stock analysis request to the pool"""
    code = req.code.upper().strip()
    task_id = str(uuid.uuid4())[:12]
    task = {
        "id": task_id,
        "code": code,
        "name": req.name or code,
        "sector": req.sector,
        "note": req.note,
        "type": req.type,
        "status": "pending",
        "created_at": _now(),
        "claimed_at": None,
        "completed_at": None,
        "result": None,
        "error": None
    }
    tasks = _load_tasks()
    tasks.append(task)
    _save_tasks(tasks)
    return task

@app.delete("/api/requests/{task_id}")
def delete_request(task_id: str):
    """Delete a request from the pool"""
    tasks = _load_tasks()
    tasks = [t for t in tasks if t["id"] != task_id]
    _save_tasks(tasks)
    return {"ok": True}

# ─── Stock Endpoints (Analyzed stocks only) ───────────

@app.get("/api/stocks")
def list_stocks():
    """List analyzed stocks only (have meta.json)"""
    dashboard = _load_dashboard()
    prices = dashboard.get("prices", {})
    stocks = []
    for entry in os.listdir(REPORTS_DIR):
        if entry.startswith("_"):
            continue
        meta_path = os.path.join(REPORTS_DIR, entry, "meta.json")
        if os.path.exists(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            code = meta["code"]
            p = prices.get(code, {})
            stocks.append({
                "code": code,
                "name": meta["name"],
                "sector": meta.get("sector", ""),
                "tags": meta["tags"],
                "watchlist": meta["tags"].get("watchlist", False),
                "overall": meta["tags"].get("overall", "none"),
                "price_marks": meta.get("price_marks", []),
                "report_count": len(meta.get("reports", [])),
                "last_analysis": meta["cache"]["fundamental"]["last"],
                "last_price": p.get("price"),
                "change_pct": p.get("change_pct"),
                "price_updated": p.get("updated_at")
            })
    return stocks

@app.get("/api/stocks/{code}")
def get_stock(code: str):
    meta = _load_meta(code)
    now = datetime.now(timezone.utc)
    for key in ["fundamental", "technical"]:
        vu = meta["cache"][key]["valid_until"]
        meta["cache"][key]["expired"] = not vu or datetime.fromisoformat(vu) < now
    latest = None
    if meta["reports"]:
        latest = meta["reports"][-1]
    # Inject current price
    dashboard = _load_dashboard()
    prices = dashboard.get("prices", {})
    p = prices.get(code, {})
    meta["last_price"] = p.get("price")
    meta["change_pct"] = p.get("change_pct")
    return {**meta, "latest_report": latest}

@app.patch("/api/stocks/{code}/tags")
def update_tags(code: str, req: TagUpdateReq):
    meta = _load_meta(code)
    if req.overall is not None:
        meta["tags"]["overall"] = req.overall
    if req.watchlist is not None:
        meta["tags"]["watchlist"] = req.watchlist
    _save_meta(code, meta)
    return meta["tags"]

@app.post("/api/stocks/{code}/price-marks")
def add_price_mark(code: str, req: PriceMarkReq):
    meta = _load_meta(code)
    mark = {
        "id": str(uuid.uuid4())[:8],
        "label": req.label,
        "price": req.price,
        "type": req.type,
        "created_at": _now()
    }
    meta["price_marks"].append(mark)
    _save_meta(code, meta)
    return mark

@app.delete("/api/stocks/{code}/price-marks/{mark_id}")
def delete_price_mark(code: str, mark_id: str):
    meta = _load_meta(code)
    meta["price_marks"] = [m for m in meta["price_marks"] if m["id"] != mark_id]
    _save_meta(code, meta)
    return {"ok": True}

@app.get("/api/stocks/{code}/reports")
def list_reports(code: str):
    meta = _load_meta(code)
    return meta.get("reports", [])

@app.get("/api/stocks/{code}/reports/{report_id}")
def get_report(code: str, report_id: str):
    meta = _load_meta(code)
    rpt = next((r for r in meta["reports"] if r["id"] == report_id), None)
    if not rpt:
        raise HTTPException(404, "Report not found")
    path = os.path.join(_reports_dir(code), rpt["filename"])
    if not os.path.exists(path):
        raise HTTPException(404, "Report file missing")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    return {"meta": rpt, "content": content}

@app.get("/api/stocks/{code}/reports/{report_id}/raw")
def get_report_raw(code: str, report_id: str):
    from fastapi.responses import FileResponse
    meta = _load_meta(code)
    rpt = next((r for r in meta["reports"] if r["id"] == report_id), None)
    if not rpt:
        raise HTTPException(404, "Report not found")
    path = os.path.join(_reports_dir(code), rpt["filename"])
    return FileResponse(path, media_type="text/markdown")

@app.get("/api/stocks/{code}/notes")
def get_notes(code: str):
    path = _notes_path(code)
    if not os.path.exists(path):
        return {"notes": []}
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    entries = []
    current = {"time": None, "lines": []}
    for line in content.splitlines():
        if line.startswith("## "):
            if current["time"]:
                entries.append({
                    "time": current["time"],
                    "content": "\n".join(current["lines"]).strip()
                })
            current = {"time": line[3:].strip(), "lines": []}
        else:
            current["lines"].append(line)
    if current["time"]:
        entries.append({
            "time": current["time"],
            "content": "\n".join(current["lines"]).strip()
        })
    return {"notes": list(reversed(entries))}

@app.post("/api/stocks/{code}/notes")
def add_note(code: str, req: NoteReq):
    meta = _load_meta(code)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    entry = f"\n## {ts}\n\n{req.content}\n"
    path = _notes_path(code)
    with open(path, "a", encoding="utf-8") as f:
        f.write(entry)
    note_obj = {"time": ts, "content": req.content}
    meta["notes"].insert(0, note_obj)
    _save_meta(code, meta)
    return note_obj

# ─── Agent Endpoints (for AI polling) ──────────────────

@app.get("/api/agent/tasks")
def get_agent_tasks():
    """AI Agent polls this to see pending tasks"""
    tasks = _load_tasks()
    pending = [t for t in tasks if t["status"] == "pending"]
    return pending

@app.get("/api/agent/tasks/{task_id}")
def get_agent_task(task_id: str):
    """Get specific task details"""
    tasks = _load_tasks()
    task = next((t for t in tasks if t["id"] == task_id), None)
    if not task:
        raise HTTPException(404, "Task not found")
    return task

@app.post("/api/agent/tasks/{task_id}/claim")
def claim_task(task_id: str):
    tasks = _load_tasks()
    task = next((t for t in tasks if t["id"] == task_id), None)
    if not task:
        raise HTTPException(404, "Task not found")
    if task["status"] != "pending":
        raise HTTPException(409, "Task already claimed or done")
    task["status"] = "in_progress"
    task["claimed_at"] = _now()
    _save_tasks(tasks)
    return task

@app.post("/api/agent/tasks/{task_id}/complete")
def complete_task(task_id: str, req: AgentTaskCompleteReq):
    tasks = _load_tasks()
    task = next((t for t in tasks if t["id"] == task_id), None)
    if not task:
        raise HTTPException(404, "Task not found")
    task["status"] = "completed"
    task["completed_at"] = _now()
    task["result"] = {"report_path": req.report_path, "summary": req.summary}
    _save_tasks(tasks)
    
    # Create stock entry if not exists (now it's officially in the list)
    code = task["code"]
    if not os.path.exists(_meta_path(code)):
        _init_stock(code, task.get("name", code), task.get("sector", ""))
    
    meta = _load_meta(code)
    now = _now()
    report_entry = {
        "id": str(uuid.uuid4())[:8],
        "filename": os.path.basename(req.report_path) if req.report_path else None,
        "type": req.report_type,
        "created_at": now,
        "task_id": task_id
    }
    meta["reports"].append(report_entry)
    
    # Update cache based on report type
    if req.report_type in ("fundamental", "full"):
        meta["cache"]["fundamental"] = {
            "last": now,
            "valid_until": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        }
    if req.report_type in ("technical", "full"):
        meta["cache"]["technical"] = {
            "last": now,
            "valid_until": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        }
    _save_meta(code, meta)
    return task

@app.post("/api/agent/tasks/{task_id}/fail")
def fail_task(task_id: str, req: AgentTaskFailReq):
    tasks = _load_tasks()
    task = next((t for t in tasks if t["id"] == task_id), None)
    if not task:
        raise HTTPException(404, "Task not found")
    task["status"] = "failed"
    task["completed_at"] = _now()
    task["error"] = req.reason
    _save_tasks(tasks)
    return task

# ─── Dashboard ────────────────────────────────────────

@app.get("/api/dashboard")
def get_dashboard():
    """Return dashboard data with current prices and price mark diffs"""
    dashboard = _load_dashboard()
    prices = dashboard.get("prices", {})
    
    stocks = []
    for entry in os.listdir(REPORTS_DIR):
        if entry.startswith("_"):
            continue
        meta_path = os.path.join(REPORTS_DIR, entry, "meta.json")
        if os.path.exists(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            code = meta["code"]
            p = prices.get(code, {})
            current_price = p.get("price")
            
            # Calculate diffs for price marks
            marks_with_diff = []
            for m in meta.get("price_marks", []):
                diff = None
                diff_pct = None
                if current_price is not None and current_price > 0:
                    diff = current_price - m["price"]
                    diff_pct = (diff / m["price"]) * 100
                marks_with_diff.append({
                    **m,
                    "diff": diff,
                    "diff_pct": diff_pct
                })
            
            stocks.append({
                "code": code,
                "name": meta["name"],
                "sector": meta.get("sector", ""),
                "tags": meta["tags"],
                "watchlist": meta["tags"].get("watchlist", False),
                "overall": meta["tags"].get("overall", "none"),
                "price_marks": marks_with_diff,
                "report_count": len(meta.get("reports", [])),
                "last_analysis": meta["cache"]["fundamental"]["last"],
                "last_price": current_price,
                "change_pct": p.get("change_pct"),
                "price_updated": p.get("updated_at")
            })
    
    return {
        "stocks": stocks,
        "last_update": dashboard.get("last_update"),
        "price_data_time": _now()
    }

@app.get("/api/dashboard/refresh")
def refresh_dashboard():
    return {"message": "Dashboard refresh triggered"}

# ─── Price Refresh ───────────────────────────────────
# Real-time prices: fetched directly from Sina API by backend
# Agent uses kimi_finance for deep analysis (fundamentals/technicals), NOT for price refresh

@app.get("/api/prices/refresh")
def refresh_prices():
    """Fetch real-time prices from Sina Finance and update dashboard."""
    codes = _get_stock_codes()
    if not codes:
        return {"updated": 0, "prices": {}, "message": "No stocks tracked"}
    
    prices = _fetch_prices_sina(codes)
    _update_dashboard_prices(prices)
    return {
        "updated": len(prices),
        "prices": prices,
        "source": "sina",
        "message": f"Updated {len(prices)} stock prices from Sina Finance"
    }

# ─── Health ───────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok", "time": _now()}
