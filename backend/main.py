from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List, Literal
import json
import os
import uuid
import subprocess
import urllib.request
import re
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
REPORTS_CACHE_FILE = os.path.join(REPORTS_DIR, "_reports_cache.json")

os.makedirs(REPORTS_DIR, exist_ok=True)

# ─── Reports Cache (program-managed, no hand-editing) ──
def _build_reports_cache() -> dict:
    """Full scan of all stocks' reports directories. Returns {code: {...}}"""
    cache = {}
    for entry in os.listdir(REPORTS_DIR):
        if entry.startswith("_"):
            continue
        meta_path = os.path.join(REPORTS_DIR, entry, "meta.json")
        if not os.path.exists(meta_path):
            continue
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            code = meta["code"]
            name = meta.get("name", code)
        except Exception:
            continue
        reports = _scan_reports(code)
        cache[code] = {
            "name": name,
            "report_count": len(reports),
            "last_analysis": _last_analysis(reports),
            "reports": reports,
            "updated_at": _now()
        }
    return cache

def _load_reports_cache() -> dict:
    """Load cached report index. Rebuild from disk if missing."""
    if os.path.exists(REPORTS_CACHE_FILE):
        try:
            with open(REPORTS_CACHE_FILE, "r", encoding="utf-8") as f:
                cache = json.load(f)
            if cache:
                return cache
        except Exception:
            pass
    # Missing or corrupt: rebuild from disk
    cache = _build_reports_cache()
    _save_reports_cache(cache)
    return cache

def _save_reports_cache(cache: dict):
    with open(REPORTS_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def _update_reports_cache(code: str, name: str = ""):
    """Incrementally update cache for one stock after new report written."""
    cache = _load_reports_cache()
    reports = _scan_reports(code)
    cache[code] = {
        "name": name or cache.get(code, {}).get("name", code),
        "report_count": len(reports),
        "last_analysis": _last_analysis(reports),
        "reports": reports,
        "updated_at": _now()
    }
    _save_reports_cache(cache)

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
        state_path = os.path.join(REPORTS_DIR, entry, "state.json")
        if os.path.exists(meta_path) or os.path.exists(state_path):
            try:
                meta = _load_meta(entry)
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
                name = fields[0]
                open_p = float(fields[1]) if len(fields) > 1 else 0
                prev_close = float(fields[2])
                current = float(fields[3])
                high = float(fields[4]) if len(fields) > 4 else current
                low = float(fields[5]) if len(fields) > 5 else current
                volume = float(fields[8]) if len(fields) > 8 else 0
                amount = float(fields[9]) if len(fields) > 9 else 0
                change_pct = ((current - prev_close) / prev_close) * 100 if prev_close > 0 else 0
                amplitude = ((high - low) / prev_close) * 100 if prev_close > 0 else 0
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
                    "open": open_p,
                    "high": high,
                    "low": low,
                    "prev_close": prev_close,
                    "change_pct": round(change_pct, 2),
                    "amplitude": round(amplitude, 2),
                    "volume": volume,
                    "amount": amount,
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

def _state_path(code: str) -> str:
    return os.path.join(_stock_dir(code), "state.json")

def _reports_dir(code: str) -> str:
    return os.path.join(_stock_dir(code), "reports")

def _scan_reports(code: str) -> list:
    """Scan reports directory for report files. First source of truth."""
    d = _reports_dir(code)
    if not os.path.exists(d):
        return []
    reports = []
    for fname in sorted(os.listdir(d)):
        if not fname.endswith(".md"):
            continue
        parts = fname.replace(".md", "").split("_")
        if len(parts) >= 2:
            rtype = parts[0]
            rdate = parts[1]
            if len(rdate) == 8:
                rdate = f"{rdate[:4]}-{rdate[4:6]}-{rdate[6:]}"
        else:
            rtype = "full"
            rdate = ""
        reports.append({
            "id": f"{rtype}_{parts[1]}",
            "filename": fname,
            "type": rtype,
            "created_at": rdate
        })
    return reports

def _last_analysis(reports: list) -> str:
    """Get last fundamental analysis date from scanned reports."""
    dates = [r["created_at"] for r in reports if r["type"] in ("fundamental", "full")]
    return max(dates) if dates else None

def _notes_path(code: str) -> str:
    return os.path.join(_stock_dir(code), "notes.md")

def _briefs_path(code: str) -> str:
    return os.path.join(_stock_dir(code), "briefs.json")

def _load_briefs(code: str) -> list:
    path = _briefs_path(code)
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _save_briefs(code: str, briefs: list):
    path = _briefs_path(code)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(briefs, f, ensure_ascii=False, indent=2)

def _generate_brief_text(data: dict) -> tuple:
    """Generate daily brief text. Returns (text, has_value)."""
    change = data.get("change_pct", 0)
    amplitude = data.get("amplitude", 0)
    open_p = data.get("open", 0)
    high = data.get("high", 0)
    low = data.get("low", 0)
    price = data.get("price", 0)
    prev = data.get("prev_close", 0)
    
    # Skip if nothing interesting happened
    if abs(change) < 1.0 and amplitude < 2.0:
        return "", False
    
    segments = []
    
    # Opening behavior
    gap = ((open_p - prev) / prev * 100) if prev > 0 else 0
    if gap > 1.5:
        segments.append("高开")
    elif gap < -1.5:
        segments.append("低开")
    elif gap > 0:
        segments.append("小幅高开")
    elif gap < 0:
        segments.append("小幅低开")
    else:
        segments.append("平开")
    
    # Intraday behavior
    if abs(change) > 3 and amplitude < abs(change) + 0.5:
        segments.append("后单边上行" if change > 0 else "后单边下行")
    elif price > open_p and price > prev:
        segments.append("后震荡走高")
    elif price < open_p and price < prev:
        segments.append("后震荡走低")
    elif high - price > price - low and change > 0:
        segments.append("冲高回落")
    elif price - low > high - price and change < 0:
        segments.append("探底回升")
    else:
        segments.append("全天震荡")
    
    # Result
    if abs(change) >= 3:
        segments.append(f"，收{'涨' if change > 0 else '跌'}{abs(change):.1f}%")
    elif abs(change) >= 1.5:
        segments.append(f"，收{'涨' if change > 0 else '跌'}{abs(change):.1f}%")
    else:
        segments.append(f"，微{'涨' if change > 0 else '跌'}{abs(change):.1f}%")
    
    # Volume/activity hint
    if amplitude > 5:
        segments.append("，振幅较大")
    
    text = "".join(segments)
    # Clean up double commas
    text = text.replace("，，", "，")
    
    # Cap at ~100 chars
    if len(text) > 100:
        text = text[:100] + "…"
    
    return text, True

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _load_meta(code: str) -> dict:
    """Load meta.json (static) + state.json (mutable), merge and return."""
    meta_path = _meta_path(code)
    if not os.path.exists(meta_path):
        raise HTTPException(404, f"Stock {code} not found")
    with open(meta_path, "r", encoding="utf-8") as f:
        static = json.load(f)

    state_path = _state_path(code)
    mutable = {}
    if os.path.exists(state_path):
        with open(state_path, "r", encoding="utf-8") as f:
            mutable = json.load(f)
    else:
        # Legacy: only meta.json exists (pre-migration) – read everything
        # This branch can be removed once migration is done everywhere
        pass

    merged = {**static, **mutable}
    # Legacy: notes may be a string instead of array
    if "notes" in merged and isinstance(merged["notes"], str):
        merged["notes"] = []
    return merged


def _get_latest_note(code: str) -> Optional[dict]:
    """Get the latest note from notes.md."""
    path = _notes_path(code)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        content = f.read().strip()
    if not content:
        return None
    # Parse the first entry (most recent, since we prepend)
    # Actually notes.md is append-only, so last entry is most recent
    lines = content.splitlines()
    current_time = None
    current_lines = []
    for line in lines:
        if line.startswith("## "):
            current_time = line[3:].strip()
            current_lines = []
        else:
            current_lines.append(line)
    if current_time and current_lines:
        return {"time": current_time, "content": "\n".join(current_lines).strip()}
    return None

def _save_meta(code: str, meta: dict):
    """Split fields into meta.json (static) and state.json (mutable).
    Reports and cache are derived from disk scans - never saved here."""
    static_fields = {"code", "name", "sector", "type", "added_at"}
    # Never save reports/cache to state - they are derived from disk
    derive_fields = {"reports", "cache"}
    static = {k: v for k, v in meta.items() if k in static_fields}
    mutable = {k: v for k, v in meta.items() if k not in static_fields and k not in derive_fields}

    meta_path = _meta_path(code)
    os.makedirs(os.path.dirname(meta_path), exist_ok=True)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(static, f, ensure_ascii=False, indent=2)

    state_path = _state_path(code)
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(mutable, f, ensure_ascii=False, indent=2)


def _normalize_dimensions(meta: dict) -> dict:
    """Extract evaluation dimensions from meta tags (new or legacy format)."""
    tags = meta.get("tags", {})
    dims = {}

    # New format: direct dimension fields
    if "quality" in tags:
        dims["quality"] = tags["quality"]
    else:
        # Legacy fallback: derive from moat / fundamental
        dims["quality"] = tags.get("moat") or tags.get("fundamental") or "none"

    dims["valuation"] = tags.get("valuation", "none")

    if "timing" in tags:
        dims["timing"] = tags["timing"]
    else:
        dims["timing"] = tags.get("technical", "none")

    dims["risk"] = tags.get("risk", "none")

    if "verdict" in tags:
        dims["verdict"] = tags["verdict"]
    else:
        dims["verdict"] = tags.get("overall", "none")

    return dims


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

def _fetch_stock_name(code: str) -> str:
    """Fetch stock name from Sina API."""
    try:
        num = code.split(".")[0]
        exchange = code.split(".")[1].upper()
        if exchange == "SZ":
            sina_code = "sz" + num
        elif exchange == "SH":
            sina_code = "sh" + num
        elif exchange == "BJ":
            sina_code = "bj" + num
        else:
            return code
        url = f"https://hq.sinajs.cn/list={sina_code}"
        req = urllib.request.Request(url, headers={"Referer": "https://finance.sina.com.cn"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = resp.read().decode("gb2312", errors="ignore")
        match = re.search(r'"([^,]+),', data)
        if match:
            return match.group(1)
    except Exception:
        pass
    return code

def _init_stock(code: str, name: str = "", sector: str = "") -> dict:
    """Initialize stock directory. If already exists, only update name/sector if provided."""
    d = _stock_dir(code)
    meta_path = _meta_path(code)
    
    # If already initialized, only update name/sector if explicitly provided
    if os.path.exists(meta_path):
        existing = _load_meta(code)
        updated = False
        if name and existing.get("name") != name:
            existing["name"] = name
            updated = True
        if sector and existing.get("sector") != sector:
            existing["sector"] = sector
            updated = True
        if updated:
            _save_meta(code, existing)
        return existing
    
    # New stock initialization
    if not name:
        name = _fetch_stock_name(code)
    os.makedirs(os.path.join(d, "reports"), exist_ok=True)

    static = {
        "code": code,
        "name": name,
        "sector": sector,
        "added_at": _now(),
    }
    _save_meta(code, {
        **static,
        "tags": {"overall": "none", "watchlist": False},
        "price_marks": [],
        "daily_briefs": [],
        "notes": [],
        "cache": {
            "fundamental": {"last": None, "valid_until": None},
            "technical": {"last": None, "valid_until": None}
        },
        "reports": []
    })
    open(os.path.join(d, "notes.md"), "a").close()
    return static

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
    type: Literal["target_buy", "stop_loss", "take_profit", "add", "reduce", "mark"] = "mark"

class StatusReq(BaseModel):
    status: Literal["tracking", "bullish", "neutral", "avoid", "no_interest", "blacklist", "waiting", "archive", "core_position"]

class HoldingsReq(BaseModel):
    cost: Optional[float] = None
    quantity: Optional[int] = None

class NoteReq(BaseModel):
    content: str

class DailyBriefReq(BaseModel):
    auto: bool = True  # if auto, skip if no value

class AgentTaskCompleteReq(BaseModel):
    report_path: Optional[str] = None
    summary: Optional[str] = None
    report_type: Literal["fundamental", "technical", "full"] = "full"
    reports: Optional[List[dict]] = None  # [{"path": str, "type": str}] for multiple reports

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

# ─── Daily Briefs ───────────────────────────────────────

@app.get("/api/stocks/{code}/briefs")
def get_briefs(code: str):
    """Get all daily briefs for a stock, newest first"""
    briefs = _load_briefs(code)
    return {"briefs": sorted(briefs, key=lambda x: x.get("date", ""), reverse=True)}

@app.post("/api/stocks/{code}/briefs")
def generate_brief(code: str, req: DailyBriefReq = DailyBriefReq()):
    """Generate today's brief based on current price data"""
    meta = _load_meta(code)
    dashboard = _load_dashboard()
    prices = dashboard.get("prices", {})
    data = prices.get(code.upper())
    
    if not data:
        raise HTTPException(400, "No price data available. Please refresh prices first.")
    
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    briefs = _load_briefs(code)
    
    # Check if already generated today
    existing = [b for b in briefs if b.get("date") == today]
    if existing:
        return {"brief": existing[0], "message": "Already generated today"}
    
    text, has_value = _generate_brief_text(data)
    
    if not has_value and req.auto:
        return {"brief": None, "message": "No significant movement today, skipped"}
    
    brief = {
        "id": str(uuid.uuid4())[:8],
        "date": today,
        "content": text,
        "has_value": has_value,
        "price": data.get("price"),
        "change_pct": data.get("change_pct"),
        "amplitude": data.get("amplitude"),
        "created_at": _now()
    }
    briefs.append(brief)
    _save_briefs(code, briefs)
    
    # Also update meta reference
    meta["daily_briefs"] = briefs
    _save_meta(code, meta)
    
    return {"brief": brief, "message": "Generated"}

@app.post("/api/briefs/batch")
def batch_generate_briefs():
    """Generate briefs for all tracked stocks. Called by cron."""
    codes = _get_stock_codes()
    if not codes:
        return {"processed": 0, "skipped": 0, "generated": 0, "message": "No stocks tracked"}
    
    # Refresh prices first
    prices = _fetch_prices_sina(codes)
    _update_dashboard_prices(prices)
    
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    generated = 0
    skipped = 0
    processed = 0
    
    for code in codes:
        code = code.upper().strip()
        data = prices.get(code)
        if not data:
            continue
        
        briefs = _load_briefs(code)
        existing = [b for b in briefs if b.get("date") == today]
        if existing:
            continue  # Already done today
        
        text, has_value = _generate_brief_text(data)
        processed += 1
        
        if not has_value:
            skipped += 1
            continue
        
        brief = {
            "id": str(uuid.uuid4())[:8],
            "date": today,
            "content": text,
            "has_value": has_value,
            "price": data.get("price"),
            "change_pct": data.get("change_pct"),
            "amplitude": data.get("amplitude"),
            "created_at": _now()
        }
        briefs.append(brief)
        _save_briefs(code, briefs)
        
        # Update meta
        meta = _load_meta(code)
        meta["daily_briefs"] = briefs
        _save_meta(code, meta)
        generated += 1
    
    return {
        "processed": processed,
        "skipped": skipped,
        "generated": generated,
        "message": f"Batch complete: {generated} generated, {skipped} skipped (no significant movement)"
    }

@app.delete("/api/stocks/{code}/briefs/{brief_id}")
def delete_brief(code: str, brief_id: str):
    briefs = _load_briefs(code)
    briefs = [b for b in briefs if b.get("id") != brief_id]
    _save_briefs(code, briefs)
    meta = _load_meta(code)
    meta["daily_briefs"] = briefs
    _save_meta(code, meta)
    return {"ok": True}

# ─── Stock Endpoints (Analyzed stocks only) ───────────

@app.get("/api/stocks")
def list_stocks():
    """List analyzed stocks (reports from cache for performance)."""
    dashboard_data = _load_dashboard()
    prices = dashboard_data.get("prices", {})
    cache = _load_reports_cache()
    stocks = []
    for entry in os.listdir(REPORTS_DIR):
        if entry.startswith("_"):
            continue
        meta_path = os.path.join(REPORTS_DIR, entry, "meta.json")
        if not os.path.exists(meta_path):
            continue
        try:
            meta = _load_meta(entry)
        except Exception:
            continue
        code = meta["code"]
        p = prices.get(code, {})
        cached = cache.get(code, {})
        stocks.append({
            "code": code,
            "name": meta["name"],
            "sector": meta.get("sector", ""),
            "tags": meta["tags"],
            "status": meta.get("status", "neutral"),
            "holdings": meta.get("holdings"),
            "dimensions": _normalize_dimensions(meta),
            "watchlist": meta["tags"].get("watchlist", False),
            "overall": meta["tags"].get("overall", "none"),
            "price_marks": meta.get("price_marks", []),
            "report_count": cached.get("report_count", 0),
            "last_analysis": cached.get("last_analysis"),
            "latest_note": _get_latest_note(entry),
            "last_price": p.get("price"),
            "change_pct": p.get("change_pct"),
            "price_updated": p.get("updated_at")
        })
    return stocks

@app.get("/api/stocks/{code}")
def get_stock(code: str):
    meta = _load_meta(code)
    # Derive reports from disk scan (first source of truth)
    reports = _scan_reports(code)
    meta["reports"] = reports
    # Build cache from scanned reports
    last_fund = _last_analysis(reports)
    last_tech = None
    tech_dates = [r["created_at"] for r in reports if r["type"] in ("technical", "full")]
    if tech_dates:
        last_tech = max(tech_dates)
    meta["cache"] = {
        "fundamental": {"last": last_fund, "valid_until": None},
        "technical": {"last": last_tech, "valid_until": None}
    }
    # Compute valid_until from report dates
    if last_fund:
        fund_dt = datetime.fromisoformat(last_fund.replace("Z", "+00:00"))
        meta["cache"]["fundamental"]["valid_until"] = (fund_dt + timedelta(days=90)).isoformat()
    if last_tech:
        tech_dt = datetime.fromisoformat(last_tech.replace("Z", "+00:00"))
        meta["cache"]["technical"]["valid_until"] = (tech_dt + timedelta(days=7)).isoformat()
    # Compute expired
    now = datetime.now(timezone.utc)
    for key in ["fundamental", "technical"]:
        vu = meta["cache"][key]["valid_until"]
        if not vu:
            meta["cache"][key]["expired"] = True
        else:
            vu_dt = datetime.fromisoformat(vu)
            if vu_dt.tzinfo is None:
                vu_dt = vu_dt.replace(tzinfo=timezone.utc)
            meta["cache"][key]["expired"] = vu_dt < now
    latest = None
    if reports:
        latest = reports[-1]
    # Inject current price
    dashboard = _load_dashboard()
    prices = dashboard.get("prices", {})
    p = prices.get(code, {})
    meta["last_price"] = p.get("price")
    meta["change_pct"] = p.get("change_pct")
    meta["daily_briefs"] = _load_briefs(code)
    meta["status"] = meta.get("status", "neutral")
    meta["holdings"] = meta.get("holdings")
    meta["dimensions"] = _normalize_dimensions(meta)
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

@app.patch("/api/stocks/{code}/status")
def update_status(code: str, req: StatusReq):
    meta = _load_meta(code)
    meta["status"] = req.status
    _save_meta(code, meta)
    return {"status": meta["status"]}

@app.patch("/api/stocks/{code}/holdings")
def update_holdings(code: str, req: HoldingsReq):
    meta = _load_meta(code)
    meta["holdings"] = {"cost": req.cost, "quantity": req.quantity}
    _save_meta(code, meta)
    return meta["holdings"]

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
    return _scan_reports(code)

@app.get("/api/stocks/{code}/reports/{report_id}")
def get_report(code: str, report_id: str):
    reports = _scan_reports(code)
    rpt = next((r for r in reports if r["id"] == report_id), None)
    if not rpt:
        raise HTTPException(404, "Report not found")
    filename = rpt.get("filename", report_id + ".md")
    path = os.path.join(_reports_dir(code), filename)
    if not os.path.exists(path):
        raise HTTPException(404, "Report file missing")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    return {"meta": rpt, "content": content}

@app.get("/api/stocks/{code}/reports/{report_id}/raw")
def get_report_raw(code: str, report_id: str):
    from fastapi.responses import FileResponse
    reports = _scan_reports(code)
    rpt = next((r for r in reports if r["id"] == report_id), None)
    if not rpt:
        raise HTTPException(404, "Report not found")
    path = os.path.join(_reports_dir(code), rpt["filename"])
    return FileResponse(path, media_type="text/markdown")

@app.delete("/api/stocks/{code}/reports/{report_id}")
def delete_report(code: str, report_id: str):
    """Delete a report file and update cache."""
    reports = _scan_reports(code)
    rpt = next((r for r in reports if r["id"] == report_id), None)
    if not rpt:
        raise HTTPException(404, "Report not found")
    path = os.path.join(_reports_dir(code), rpt["filename"])
    if os.path.exists(path):
        os.remove(path)
    # Update cache
    _update_reports_cache(code)
    return {"deleted": report_id}

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
    task["result"] = {"report_path": req.report_path, "summary": req.summary, "reports": req.reports}
    _save_tasks(tasks)
    
    # Create stock entry if not exists
    code = task["code"]
    name = task.get("name", code)
    if not os.path.exists(_meta_path(code)) and not os.path.exists(_state_path(code)):
        _init_stock(code, name, task.get("sector", ""))
    
    # Update reports cache (program-managed, no hand-editing)
    _update_reports_cache(code, name)
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
    """Return dashboard data with current prices and price mark diffs.
    Reports info from cache (performance); details scan disk."""
    dashboard = _load_dashboard()
    prices = dashboard.get("prices", {})
    cache = _load_reports_cache()

    stocks = []
    for entry in os.listdir(REPORTS_DIR):
        if entry.startswith("_"):
            continue
        meta_path = os.path.join(REPORTS_DIR, entry, "meta.json")
        if not os.path.exists(meta_path):
            continue
        try:
            meta = _load_meta(entry)
        except Exception:
            continue
        code = meta["code"]
        p = prices.get(code, {})
        current_price = p.get("price")
        cached = cache.get(code, {})
        
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
            "status": meta.get("status", "neutral"),
            "dimensions": _normalize_dimensions(meta),
            "watchlist": meta["tags"].get("watchlist", False),
            "overall": meta["tags"].get("overall", "none"),
            "price_marks": marks_with_diff,
            "report_count": cached.get("report_count", 0),
            "last_analysis": cached.get("last_analysis"),
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

# ═══════════════════════════════════════════════════════
#  Holdings & T-Trade Management
# ═══════════════════════════════════════════════════════

import re
from collections import deque

FEE_RATE = 0.00025   # 万2.5
FEE_MIN = 5.00       # 最低5元

class TradeIn(BaseModel):
    date: str                    # YYYY-MM-DD
    time: Optional[str] = "15:00:00"  # HH:MM:SS
    type: Literal["buy", "sell"] # 买卖方向
    price: float
    quantity: int
    fee: Optional[float] = None  # 如不传，自动计算
    note: Optional[str] = ""
    idempotent_key: Optional[str] = None

class AdjustIn(BaseModel):
    date: str
    type: Literal["split", "bonus", "dividend"]  # 送转 / 分红
    ratio: Optional[float] = 1.0   # 送转比例，如10送3则ratio=1.3
    dividend_per_share: Optional[float] = 0.0  # 每股分红金额
    note: Optional[str] = ""

def _holdings_path(code: str) -> str:
    return os.path.join(_stock_dir(code), "holdings.json")

def _load_holdings(code: str) -> dict:
    p = _holdings_path(code)
    if not os.path.exists(p):
        return {"trades": [], "t_trades": [], "adj_events": [], "summary": {}}
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def _save_holdings(code: str, data: dict):
    p = _holdings_path(code)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _calc_fee(price: float, quantity: int) -> float:
    amount = price * quantity
    fee = amount * FEE_RATE
    return max(fee, FEE_MIN)

def _make_idempotent_key(trade: dict) -> str:
    """生成幂等键：日期_时间_价格_数量_方向"""
    return f"{trade['date']}_{trade.get('time','')}_{trade['price']:.3f}_{trade['quantity']}_{trade['type']}"

def _rebuild_holdings(data: dict) -> dict:
    """
    重建持仓：智能FIFO + 日内优先匹配
    核心逻辑：
    1. 按时间排序所有trades
    2. 买入：加入持仓队列，remaining=quantity
    3. 卖出：先尝试同日LIFO匹配（做T），剩余走底仓FIFO
    """
    trades = sorted(data.get("trades", []), key=lambda t: (t["date"], t.get("time", "")))
    adj_events = sorted(data.get("adj_events", []), key=lambda e: e["date"])

    # 持仓队列：每个元素是 {trade_id, date, time, price, quantity, remaining}
    lots = deque()  # FIFO队列
    t_trades = []
    realized_pnl = 0.0

    # 先处理除权调整，影响原始买入记录的价格和数量
    # 简化：除权只影响summary计算，不修改原始trade记录
    # 实际处理：在遍历trades时，根据日期前的adj_events调整lot

    # 为了简化，我们换一种方式：除权时直接修改已有的lot
    # 但重建时从头算更简单

    # 维护一个"有效持仓"列表
    positions = []  # 每个元素：{from_trade, buy_date, buy_time, price, quantity, remaining}

    for trade in trades:
        # 处理此trade之前的除权调整
        # 实际上除权已经发生在特定日期，我们需要在对应日期应用
        pass  # 简化：先不处理除权，因为除权事件很少，且主要是送转股影响数量和成本

    for trade in trades:
        t_type = trade["type"]
        qty = trade["quantity"]
        price = trade["price"]
        fee = trade.get("fee", 0)
        trade_id = trade.get("id", "")

        if t_type == "buy":
            positions.append({
                "from_trade": trade_id,
                "buy_date": trade["date"],
                "buy_time": trade.get("time", ""),
                "price": price,
                "quantity": qty,
                "remaining": qty,
            })

        elif t_type == "sell":
            sell_qty = qty
            sell_price = price
            sell_date = trade["date"]
            sell_time = trade.get("time", "")

            # Step 1: 日内LIFO匹配 — 同一天内，先买后卖
            if sell_qty > 0:
                # 找同一天、时间更早、remaining > 0 的买入，按时间倒序（LIFO）
                same_day_buys = [
                    (i, p) for i, p in enumerate(positions)
                    if p["buy_date"] == sell_date and p["remaining"] > 0 and p["buy_time"] < sell_time
                ]
                same_day_buys.sort(key=lambda x: x[1]["buy_time"], reverse=True)  # 时间倒序 = LIFO

                for idx, pos in same_day_buys:
                    if sell_qty <= 0:
                        break
                    match_qty = min(sell_qty, pos["remaining"])
                    pos["remaining"] -= match_qty
                    sell_qty -= match_qty

                    profit = match_qty * (sell_price - pos["price"])
                    realized_pnl += profit

                    t_trades.append({
                        "id": f"tt_{uuid.uuid4().hex[:8]}",
                        "type": "正T",
                        "buy_date": pos["buy_date"], "buy_time": pos["buy_time"], "buy_price": pos["price"],
                        "sell_date": sell_date, "sell_time": sell_time, "sell_price": sell_price,
                        "quantity": match_qty,
                        "profit": round(profit, 2),
                        "buy_trade_id": pos["from_trade"],
                        "sell_trade_id": trade_id,
                    })

            # Step 2: 跨天/底仓FIFO匹配
            if sell_qty > 0:
                for pos in positions:
                    if sell_qty <= 0:
                        break
                    if pos["remaining"] <= 0:
                        continue
                    match_qty = min(sell_qty, pos["remaining"])
                    pos["remaining"] -= match_qty
                    sell_qty -= match_qty

                    profit = match_qty * (sell_price - pos["price"])
                    realized_pnl += profit

                    # 判断是否是正T（虽然是FIFO，但如果是同一天且时间合理，已经在上面处理了）
                    # 这里主要是底仓卖出
                    t_trades.append({
                        "id": f"tt_{uuid.uuid4().hex[:8]}",
                        "type": "底仓卖出",
                        "buy_date": pos["buy_date"], "buy_price": pos["price"],
                        "sell_date": sell_date, "sell_time": sell_time, "sell_price": sell_price,
                        "quantity": match_qty,
                        "profit": round(profit, 2),
                        "buy_trade_id": pos["from_trade"],
                        "sell_trade_id": trade_id,
                    })

            # 如果还有剩余卖出量 → 超卖/反T
            if sell_qty > 0:
                # 记录为融券/反T
                t_trades.append({
                    "id": f"tt_{uuid.uuid4().hex[:8]}",
                    "type": "反T(超卖)",
                    "sell_date": sell_date, "sell_time": sell_time, "sell_price": sell_price,
                    "quantity": sell_qty,
                    "profit": None,
                    "status": "open",  # 待回补
                })

    # 处理反T回补
    open_shorts = [t for t in t_trades if t.get("type") == "反T(超卖)" and t.get("status") == "open"]
    if open_shorts:
        for short in open_shorts:
            needed = short["quantity"]
            short_price = short["sell_price"]
            # 找后续买入回补
            for trade in trades:
                if trade["type"] != "buy":
                    continue
                if trade["date"] < short["sell_date"]:
                    continue
                # 从positions中找这个买入对应的lot
                for pos in positions:
                    if pos["from_trade"] == trade.get("id", "") and pos["remaining"] > 0:
                        match_qty = min(needed, pos["remaining"])
                        pos["remaining"] -= match_qty
                        needed -= match_qty

                        profit = match_qty * (short_price - pos["price"])
                        realized_pnl += profit

                        short["status"] = "closed"
                        short["close_date"] = trade["date"]
                        short["close_price"] = pos["price"]
                        short["profit"] = round(profit, 2)

                        t_trades.append({
                            "id": f"tt_{uuid.uuid4().hex[:8]}",
                            "type": "反T回补",
                            "sell_price": short_price,
                            "buy_date": trade["date"], "buy_price": pos["price"],
                            "quantity": match_qty,
                            "profit": round(profit, 2),
                        })

                    if needed <= 0:
                        break
                if needed <= 0:
                    break

    # 计算Summary
    total_qty = sum(p["remaining"] for p in positions)
    total_cost = sum(p["price"] * p["remaining"] for p in positions)
    avg_cost = total_cost / total_qty if total_qty > 0 else 0

    # 找last trade / last buy / last sell
    last_trade = None
    last_buy_price = None
    last_sell_price = None
    if trades:
        lt = trades[-1]
        last_trade = {
            "date": lt["date"],
            "time": lt.get("time", ""),
            "type": lt["type"],
            "price": lt["price"],
            "quantity": lt["quantity"],
        }
        # 找最后一笔买入和最后一笔卖出
        buy_trades = [t for t in trades if t["type"] == "buy"]
        sell_trades = [t for t in trades if t["type"] == "sell"]
        if buy_trades:
            last_buy_price = buy_trades[-1]["price"]
        if sell_trades:
            last_sell_price = sell_trades[-1]["price"]

    data["t_trades"] = t_trades
    data["summary"] = {
        "total_quantity": total_qty,
        "avg_cost": round(avg_cost, 3) if total_qty > 0 else 0,
        "total_cost": round(total_cost, 2),
        "realized_pnl": round(realized_pnl, 2),
        "open_short": sum(t["quantity"] for t in t_trades if t.get("type") == "反T(超卖)" and t.get("status") == "open"),
        "last_trade": last_trade,
        "last_buy_price": last_buy_price,
        "last_sell_price": last_sell_price,
    }

    return data

# ─── Holdings API ────────────────────────────────────

@app.post("/api/holdings/{code}/trades")
def add_trade(code: str, req: TradeIn):
    """录入一笔成交，支持幂等"""
    _init_stock(code)  # 确保目录存在
    data = _load_holdings(code)

    trade = req.dict()
    if not trade.get("id"):
        trade["id"] = f"t_{uuid.uuid4().hex[:8]}"

    # 生成幂等键
    if not trade.get("idempotent_key"):
        trade["idempotent_key"] = _make_idempotent_key(trade)

    # 检查重复
    existing_keys = {t.get("idempotent_key", "") for t in data["trades"]}
    if trade["idempotent_key"] in existing_keys:
        return {"status": "skipped", "message": "Trade already exists", "id": trade["id"]}

    # 自动计算手续费
    if trade.get("fee") is None:
        trade["fee"] = round(_calc_fee(trade["price"], trade["quantity"]), 2)

    data["trades"].append(trade)

    # 重建持仓
    data = _rebuild_holdings(data)
    _save_holdings(code, data)

    return {"status": "ok", "id": trade["id"], "fee": trade["fee"], "summary": data["summary"]}

@app.get("/api/holdings/{code}/trades")
def get_holdings_trades(code: str):
    """获取某股票的所有交易记录（按时间顺序）"""
    data = _load_holdings(code)
    trades = sorted(data.get("trades", []), key=lambda x: (x.get("date", ""), x.get("time", "00:00:00")))
    return {"code": code, "trades": trades, "trade_count": len(trades)}

@app.get("/api/holdings/{code}")
def get_holdings(code: str):
    """获取某股票的持仓分析"""
    data = _load_holdings(code)
    if not data["trades"]:
        return {"code": code, "has_data": False, "message": "No trades recorded"}

    # 确保 summary 是最新的（兼容旧数据）
    summary = data.get("summary", {})
    needs_rebuild = not summary or "last_buy_price" not in summary
    if needs_rebuild:
        data = _rebuild_holdings(data)
        _save_holdings(code, data)

    return {
        "code": code,
        "has_data": True,
        "summary": data["summary"],
        "t_trades": data.get("t_trades", []),
        "trade_count": len(data["trades"]),
    }

@app.delete("/api/holdings/{code}/trades/{trade_id}")
def delete_trade(code: str, trade_id: str):
    """删除一笔成交并重建持仓"""
    data = _load_holdings(code)
    original_len = len(data["trades"])
    data["trades"] = [t for t in data["trades"] if t.get("id") != trade_id]
    if len(data["trades"]) == original_len:
        raise HTTPException(status_code=404, detail="Trade not found")

    data = _rebuild_holdings(data)
    _save_holdings(code, data)
    return {"status": "deleted", "summary": data["summary"]}

@app.post("/api/holdings/{code}/adjust")
def add_adjustment(code: str, req: AdjustIn):
    """录入除权调整（送转股/分红）"""
    _init_stock(code)
    data = _load_holdings(code)

    event = req.dict()
    event["id"] = f"adj_{uuid.uuid4().hex[:8]}"

    # 应用到现有持仓
    if req.type in ("split", "bonus") and req.ratio != 1.0:
        # 送转股：数量 × ratio，成本不变所以每股成本 ÷ ratio
        for t in data.get("trades", []):
            if t["type"] == "buy" and t["date"] < req.date:
                # 调整买入记录的数量和剩余
                t["quantity"] = int(round(t["quantity"] * req.ratio))
                # remaining 也需要调整，但重建时会重新算

    if req.type == "dividend" and req.dividend_per_share > 0:
        # 分红：从总成本中扣除
        # 这里只记录事件，实际成本调整在重建时处理
        pass

    data["adj_events"].append(event)
    data = _rebuild_holdings(data)
    _save_holdings(code, data)

    return {"status": "ok", "event": event, "summary": data["summary"]}

@app.get("/api/holdings")
def list_holdings():
    """列出所有有持仓记录的股票"""
    results = []
    for entry in os.listdir(REPORTS_DIR):
        if entry.startswith("_"):
            continue
        h_path = os.path.join(REPORTS_DIR, entry, "holdings.json")
        if os.path.exists(h_path):
            with open(h_path, "r", encoding="utf-8") as f:
                h = json.load(f)
            results.append({
                "code": entry,
                "quantity": h.get("summary", {}).get("total_quantity", 0),
                "avg_cost": h.get("summary", {}).get("avg_cost", 0),
                "realized_pnl": h.get("summary", {}).get("realized_pnl", 0),
            })
    return results

import anomaly as anomaly_module

# ═══════════════════════════════════════════════════════
#  Anomaly Detection (异动监控)
# ═══════════════════════════════════════════════════════

class AnomalyScanReq(BaseModel):
    date: Optional[str] = None          # YYYY-MM-DD, None=auto
    sample_size: Optional[int] = None   # 限制扫描数量（测试用）
    min_score: Optional[int] = 60       # 最低分数

@app.get("/api/anomalies")
def list_anomaly_dates():
    """获取所有有异动记录的日期"""
    dates = anomaly_module.get_all_dates()
    return {"dates": dates, "count": len(dates)}

@app.get("/api/anomalies/{date}")
def get_anomalies_by_date(date: str):
    """获取指定日期的异动详情。支持特殊值 'latest'"""
    if date == "latest":
        # 找到最近有数据的日期
        import json
        anomaly_file = os.path.join(REPORTS_DIR, "_anomalies.json")
        if not os.path.exists(anomaly_file):
            return {"date": None, "stocks": [], "sectors": []}
        with open(anomaly_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        daily = data.get("daily", {})
        for d in sorted(daily.keys(), reverse=True):
            record = daily[d]
            stocks = record.get("stocks", [])
            sectors = record.get("sectors", [])
            if stocks or sectors:
                return {"date": d, "stocks": stocks, "sectors": sectors}
        return {"date": None, "stocks": [], "sectors": []}
    data = anomaly_module.get_daily_anomalies(date)
    return data

@app.get("/api/anomalies/weekly/{date}")
def get_weekly_anomalies(date: str):
    """获取指定日期所在周的异动汇总"""
    weekly = anomaly_module.aggregate_weekly(date)
    return weekly

@app.post("/api/anomalies/scan")
def trigger_anomaly_scan(req: AnomalyScanReq = AnomalyScanReq()):
    """
    手动触发异动扫描。
    建议通过cron每日收盘后自动执行，这里提供手动触发入口。
    """
    try:
        result = anomaly_module.run_daily_scan(
            trade_date=req.date,
            sample_size=req.sample_size
        )
        return result
    except Exception as e:
        raise HTTPException(500, f"Scan failed: {str(e)}")

@app.post("/api/anomalies/{code}/add-to-dashboard")
def add_anomaly_to_dashboard(code: str):
    """
    将异动股票加入主看板（创建stock目录）。
    这样用户就可以对其进行深入分析了。
    """
    code = code.upper().strip()
    
    # 检查是否已存在（使用main.py自己的函数）
    if os.path.exists(_meta_path(code)):
        return {"status": "exists", "message": f"{code} already in dashboard"}
    
    # 初始化股票目录
    from anomaly import TushareClient
    client = TushareClient()
    df = client.get_stock_basic()
    name = code
    sector = ""
    if df is not None:
        row = df[df["ts_code"] == code]
        if not row.empty:
            name = row.iloc[0].get("name", code)
            sector = row.iloc[0].get("industry", "")
    
    _init_stock(code, name, sector)
    
    return {
        "status": "ok",
        "code": code,
        "name": name,
        "sector": sector,
        "message": f"Added {name}({code}) to dashboard"
    }

@app.get("/api/anomalies/latest")
def get_latest_anomalies():
    """Get latest date with actual anomaly data"""
    anomaly_file = os.path.join(REPORTS_DIR, "_anomalies.json")
    if not os.path.exists(anomaly_file):
        return {"date": None, "stocks": [], "sectors": []}
    with open(anomaly_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    daily = data.get("daily", {})
    dates = sorted(daily.keys(), reverse=True)
    for d in dates:
        record = daily[d]
        stocks = record.get("stocks", [])
        sectors = record.get("sectors", [])
        if stocks or sectors:
            return {"date": d, "stocks": stocks, "sectors": sectors}
    return {"date": None, "stocks": [], "sectors": []}

# ═══════════════════════════════════════════════════════
#  Report Status API (for AI agent self-check)
# ═══════════════════════════════════════════════════════

# 报告有效期（天）
# 技术分析时效短（市场变化快），财务分析时效长（基本面变化慢）
FUNDAMENTAL_VALIDITY_DAYS = 90
TECHNICAL_VALIDITY_DAYS = 7

def _scan_stock_reports(stock_dir: str):
    """
    扫描某只股票的reports目录，返回按类型聚合的报告信息。
    返回: {
        "fundamental": {"latest_date": "2026-07-21", "count": 2, "files": [...]},
        "technical": {"latest_date": null, "count": 0, "files": []},
        ...
    }
    """
    reports_dir = os.path.join(stock_dir, "reports")
    type_map = {}  # { "fundamental": {latest_date, count, files}, ... }

    if not os.path.exists(reports_dir):
        return type_map

    for fname in os.listdir(reports_dir):
        if not fname.endswith(".md"):
            continue
        # 文件名格式: fundamental_20260722.md, technical_20260721.md, etc.
        base = fname.replace(".md", "")
        parts = base.split("_")
        if len(parts) < 2:
            continue
        rtype = parts[0]
        date_str = parts[-1]
        if len(date_str) != 8 or not date_str.isdigit():
            continue
        iso_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"

        if rtype not in type_map:
            type_map[rtype] = {"latest_date": None, "count": 0, "files": []}
        type_map[rtype]["count"] += 1
        type_map[rtype]["files"].append({"filename": fname, "date": iso_date})
        if type_map[rtype]["latest_date"] is None or iso_date > type_map[rtype]["latest_date"]:
            type_map[rtype]["latest_date"] = iso_date

    return type_map

def _is_report_expired(report_date_str: Optional[str], report_type: str) -> bool:
    """判断报告是否过期。根据报告类型使用不同有效期。"""
    if not report_date_str:
        return True
    try:
        report_date = datetime.strptime(report_date_str, "%Y-%m-%d").date()
        days = (datetime.now(timezone.utc).date() - report_date).days
        if report_type == "fundamental":
            return days > FUNDAMENTAL_VALIDITY_DAYS
        elif report_type == "technical":
            return days > TECHNICAL_VALIDITY_DAYS
        else:
            return days > 30  # 默认30天
    except Exception:
        return True

@app.get("/api/reports/status")
def get_reports_status():
    """
    返回所有股票的分析报告状态，供AI自检使用。

    返回格式:
    {
      "total": 30,
      "analyzed": 22,
      "pending": 8,
      "latest_date": "2026-07-22",
      "stocks": {
        "300346.SZ": {
          "name": "南大光电",
          "sector": "电子化学品",
          "fundamental": "2026-07-21",
          "technical": "2026-07-20",
          "status": "analyzed"
        },
        ...
      }
    }

    status规则:
    - pending  = 没有任何报告
    - analyzed = 有报告且至少一份在30天有效期内
    - expired  = 有报告但全部超过30天
    """
    stocks_data = {}
    total = 0
    analyzed_count = 0
    pending_count = 0
    expired_count = 0
    global_latest = None

    for entry in os.listdir(REPORTS_DIR):
        # 匹配股票代码格式
        if not (entry.endswith(".SZ") or entry.endswith(".SH") or entry.endswith(".BJ") or entry.endswith(".HK")):
            continue

        stock_dir = os.path.join(REPORTS_DIR, entry)
        if not os.path.isdir(stock_dir):
            continue

        # 读取meta
        name = entry
        sector = ""
        meta_path = os.path.join(stock_dir, "meta.json")
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                name = meta.get("name", entry)
                sector = meta.get("sector", "")
            except Exception:
                pass

        # 扫描报告
        type_map = _scan_stock_reports(stock_dir)

        # 构建该股票的记录
        stock_rec = {"name": name, "sector": sector}
        has_any_report = False
        has_valid_report = False
        stock_latest = None

        for rtype in ["fundamental", "technical"]:
            info = type_map.get(rtype)
            if info and info["latest_date"]:
                has_any_report = True
                stock_rec[rtype] = info["latest_date"]
                if stock_latest is None or info["latest_date"] > stock_latest:
                    stock_latest = info["latest_date"]
                if not _is_report_expired(info["latest_date"], rtype):
                    has_valid_report = True
            else:
                stock_rec[rtype] = None

        # 确定状态
        if not has_any_report:
            stock_rec["status"] = "pending"
            pending_count += 1
        elif has_valid_report:
            stock_rec["status"] = "analyzed"
            analyzed_count += 1
        else:
            stock_rec["status"] = "expired"
            expired_count += 1

        # 更新全局最新日期
        if stock_latest:
            if global_latest is None or stock_latest > global_latest:
                global_latest = stock_latest

        stocks_data[entry] = stock_rec
        total += 1

    return {
        "total": total,
        "analyzed": analyzed_count,
        "pending": pending_count,
        "expired": expired_count,
        "latest_date": global_latest,
        "validity": {
            "fundamental_days": FUNDAMENTAL_VALIDITY_DAYS,
            "technical_days": TECHNICAL_VALIDITY_DAYS
        },
        "stocks": stocks_data
    }
