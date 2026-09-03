from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Literal
import asyncio
import json
import os
import re
import subprocess
import time
import traceback
import uuid
import urllib.request
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone, timedelta
import auth
from providers import router as providers_router
from subsystems.backtest.routes import router as backtest_router
from subsystems.anomaly.routes import router as anomaly_router

# ─── 定时任务（价格刷新 / 异动扫描） ───────────────────────────
SCHEDULER_TASKS = ("price_refresh", "anomaly_scan")

_scheduler_state = {
    "price_refresh": {"last_run": None, "last_result": "", "last_error": "", "next_run_at": None, "running": False},
    "anomaly_scan": {"last_run": None, "last_result": "", "last_error": "", "next_run_at": None, "running": False},
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动时拉起后台定时任务，关闭时优雅取消。"""
    task = asyncio.create_task(_scheduler_loop())
    print("[scheduler] 后台定时任务已启动")
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        print("[scheduler] 后台定时任务已停止")


app = FastAPI(title="Stock Analyst API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(backtest_router)
app.include_router(anomaly_router)
app.include_router(providers_router)

# GET 但实际会改动数据的接口：未登录一律禁止（不参与"未登录只读"）
AUTH_REQUIRED_GETS = {"/api/prices/refresh", "/api/dashboard/refresh"}


@app.middleware("http")
async def permission_control(request: Request, call_next):
    """全局权限控制：
    - /api/auth/* 与 /api/health 公开
    - /api/agent/* 需要登录或 X-API-Key（Agent 接口，不对外开放）
    - 其余读接口：allow_anonymous_read=true 时未登录可读；false 时需登录
    - 所有写接口：必须登录或 X-API-Key
    """
    path = request.url.path
    if not path.startswith("/api"):
        return await call_next(request)

    method = request.method.upper()
    if path.startswith("/api/auth") or path == "/api/health" or method == "OPTIONS":
        return await call_next(request)

    user = auth.get_current_user(request)
    if user:
        return await call_next(request)

    if path.startswith("/api/agent"):
        return JSONResponse({"detail": "需要登录或 API Key"}, status_code=401)

    if method in ("GET", "HEAD"):
        if path in AUTH_REQUIRED_GETS:
            return JSONResponse({"detail": "需要登录"}, status_code=401)
        if auth.load_config().get("allow_anonymous_read", False):
            return await call_next(request)
        return JSONResponse({"detail": "需要登录"}, status_code=401)

    return JSONResponse({"detail": "需要登录后才能进行写操作"}, status_code=401)

# ─── 数据文件防护 ─────────────────────────────────────
# 原则：任何一个数据文件损坏/格式异常，都不能让整个接口 500。
# 读取一律走 _safe_json_load（出错返回默认值并打日志），
# 写入一律走 _atomic_json_dump（临时文件 + os.replace，杜绝半截文件）。

def _safe_json_load(path: str, default):
    """读取 JSON 文件；损坏/编码错误/类型不符时返回 default，绝不抛异常。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if default is not None and not isinstance(data, type(default)):
            print(f"[data-guard] {os.path.basename(path)} 类型不符(期望 {type(default).__name__})，使用默认值")
            return default
        return data
    except Exception as e:
        print(f"[data-guard] 读取 {path} 失败: {type(e).__name__}: {e}，使用默认值")
        return default


def _atomic_json_dump(path: str, data):
    """原子写 JSON：先写同目录临时文件再 os.replace，避免写盘半截留下损坏文件。"""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """兜底：任何未处理异常返回结构化 500 并打印堆栈，而不是让连接直接断掉。"""
    traceback.print_exc()
    return JSONResponse(
        {"detail": f"服务器内部错误: {type(exc).__name__}: {exc}"},
        status_code=500,
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
    """Load cached report index. Rebuild from disk if missing/corrupt."""
    if os.path.exists(REPORTS_CACHE_FILE):
        cache = _safe_json_load(REPORTS_CACHE_FILE, {})
        if cache:
            return cache
    # Missing or corrupt: rebuild from disk
    cache = _build_reports_cache()
    _save_reports_cache(cache)
    return cache

def _save_reports_cache(cache: dict):
    _atomic_json_dump(REPORTS_CACHE_FILE, cache)

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
    dashboard = _safe_json_load(DASHBOARD_FILE, {"prices": {}, "last_update": None})
    if "prices" not in dashboard:
        dashboard["prices"] = {}
    for code, data in prices.items():
        dashboard["prices"][code] = data
    dashboard["last_update"] = _now()
    _atomic_json_dump(DASHBOARD_FILE, dashboard)


# ─── 定时任务实现 ─────────────────────────────────────────────

_INTERVAL_KEYS = {
    "price_refresh": "price_refresh_interval_min",
    "anomaly_scan": "anomaly_scan_interval_min",
}


def _summarize_result(result) -> str:
    if isinstance(result, dict):
        parts = []
        for key in ("updated", "stocks_found", "sectors_found", "message"):
            if key in result:
                parts.append(f"{key}={result[key]}")
        return ", ".join(parts) if parts else str(result)[:200]
    return str(result)[:200]


def _run_price_refresh_job() -> dict:
    codes = _get_stock_codes()
    if not codes:
        return {"updated": 0, "message": "没有跟踪的股票"}
    prices = _fetch_prices_sina(codes)
    _update_dashboard_prices(prices)
    return {"updated": len(prices), "message": f"已更新 {len(prices)} 只股票价格"}


def _run_anomaly_scan_job() -> dict:
    from subsystems.anomaly.core import run_daily_scan
    return run_daily_scan(trade_date=None)


_JOBS = {
    "price_refresh": _run_price_refresh_job,
    "anomaly_scan": _run_anomaly_scan_job,
}


async def _scheduler_loop():
    """每 10 秒检查一次配置；按间隔触发任务（独立线程执行，不阻塞事件循环）。"""
    while True:
        try:
            cfg = auth.load_config()
            now = time.monotonic()
            for name in SCHEDULER_TASKS:
                interval = int(cfg.get(_INTERVAL_KEYS[name]) or 0)
                state = _scheduler_state[name]
                if interval <= 0:
                    state["_next_run"] = None
                    state["_interval"] = None
                    state["next_run_at"] = None
                    state["running"] = False
                    continue
                if state.get("_next_run") is None or interval != state.get("_interval"):
                    state["_interval"] = interval
                    state["_next_run"] = now + interval * 60
                    state["next_run_at"] = (datetime.now() + timedelta(seconds=interval * 60)).isoformat(timespec="seconds")
                if state.get("_next_run", 0) <= now and not state.get("running"):
                    state["running"] = True
                    state["_next_run"] = now + interval * 60
                    state["next_run_at"] = (datetime.now() + timedelta(seconds=interval * 60)).isoformat(timespec="seconds")
                    try:
                        result = await asyncio.to_thread(_JOBS[name])
                        state["last_result"] = _summarize_result(result)
                        state["last_error"] = ""
                    except Exception as e:
                        state["last_error"] = f"{type(e).__name__}: {e}"
                    state["last_run"] = datetime.now().isoformat(timespec="seconds")
                    state["running"] = False
        except Exception as e:
            print(f"[scheduler] 调度循环异常: {e}")
        await asyncio.sleep(10)

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
    """Scan reports directory for report files. First source of truth.
    文件名格式异常（日期段不是8位数字）时仍收录，但 created_at 置空，
    避免非法日期串流入 fromisoformat 导致详情页 500。"""
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
            rdate = parts[-1]
            if len(rdate) == 8 and rdate.isdigit():
                rdate = f"{rdate[:4]}-{rdate[4:6]}-{rdate[6:]}"
            else:
                print(f"[data-guard] {code}/reports/{fname} 文件名日期段异常，created_at 置空")
                rdate = ""
        else:
            rtype = "full"
            rdate = ""
        reports.append({
            "id": fname[:-3],
            "filename": fname,
            "type": rtype,
            "created_at": rdate
        })
    return reports

def _last_analysis(reports: list) -> str:
    """Get last fundamental analysis date from scanned reports."""
    dates = [r["created_at"] for r in reports if r["type"] in ("fundamental", "full") and r["created_at"]]
    return max(dates) if dates else None

def _notes_path(code: str) -> str:
    return os.path.join(_stock_dir(code), "notes.md")

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _load_meta(code: str) -> dict:
    """Load meta.json (static) + state.json (mutable), merge and return.
    Ensures all expected fields exist with sensible defaults to prevent downstream crashes.
    单个文件损坏时降级为默认值，绝不抛 JSON 解析异常。"""
    meta_path = _meta_path(code)
    if not os.path.exists(meta_path):
        raise HTTPException(404, f"Stock {code} not found")
    static = _safe_json_load(meta_path, {})

    state_path = _state_path(code)
    mutable = {}
    if os.path.exists(state_path):
        mutable = _safe_json_load(state_path, {})

    merged = {**static, **mutable}

    # code/name 兜底：缺失时用目录名，避免下游 KeyError 拖垮整个列表接口
    merged.setdefault("code", code)
    merged.setdefault("name", merged["code"])

    # ─── Field normalization / crash prevention ────────────────────
    # Ensure tags is always a dict (legacy used list or omitted)
    if not isinstance(merged.get("tags"), dict):
        merged["tags"] = {}

    # Ensure collection/object fields always match downstream expectations.
    if not isinstance(merged.get("notes"), list):
        merged["notes"] = []
    if not isinstance(merged.get("holdings"), dict):
        merged["holdings"] = {}
    if not isinstance(merged.get("price_marks"), list):
        merged["price_marks"] = []

    # Common optional fields that downstream expects
    merged.setdefault("status", "unassessed")
    merged.setdefault("sector", "")
    return merged


def _get_latest_note(code: str) -> Optional[dict]:
    """Get the latest note from notes.md. 文件读取失败（编码损坏等）返回 None。"""
    path = _notes_path(code)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
    except Exception as e:
        print(f"[data-guard] 读取 {path} 失败: {type(e).__name__}: {e}")
        return None
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
    Reports and cache are derived from disk scans - never saved here.
    Also migrates any top-level dimensions to tags for schema consistency."""
    static_fields = {"code", "name", "sector", "type", "added_at"}
    # Never save reports/cache to state - they are derived from disk
    derive_fields = {"reports", "cache"}
    
    # Migrate top-level dimensions to tags if present
    if "dimensions" in meta and isinstance(meta["dimensions"], dict):
        tags = meta.setdefault("tags", {})
        for key in ["quality", "valuation", "timing", "risk", "verdict"]:
            if key in meta["dimensions"] and key not in tags:
                val = meta["dimensions"][key]
                if isinstance(val, (int, float)):
                    val = {1: "green", 0: "none", -1: "red"}.get(val, "none")
                if val in {"green", "yellow", "red", "none"}:
                    tags[key] = val
        # Remove stale top-level dimensions
        del meta["dimensions"]
    
    # Validate and fix tags values before saving
    if "tags" in meta and isinstance(meta["tags"], dict):
        tags = meta["tags"]
        # Fix watchlist: must be boolean, not empty string or None
        wl = tags.get("watchlist")
        if wl == "" or wl is None:
            tags["watchlist"] = False
        # Fix empty string dimension values
        valid_dims = {"green", "yellow", "red", "none"}
        for key in ["overall", "quality", "valuation", "timing", "risk", "verdict"]:
            if key in tags and tags[key] == "":
                tags[key] = "none"
            if key in tags and tags[key] not in valid_dims:
                # Map numeric values
                if isinstance(tags[key], (int, float)):
                    tags[key] = {1: "green", 0: "none", -1: "red"}.get(tags[key], "none")
                else:
                    tags[key] = "none"
    
    static = {k: v for k, v in meta.items() if k in static_fields}
    mutable = {k: v for k, v in meta.items() if k not in static_fields and k not in derive_fields}

    meta_path = _meta_path(code)
    os.makedirs(os.path.dirname(meta_path), exist_ok=True)
    _atomic_json_dump(meta_path, static)

    state_path = _state_path(code)
    _atomic_json_dump(state_path, mutable)


def _normalize_dimensions(meta: dict) -> dict:
    """Extract evaluation dimensions from meta tags (canonical) or top-level dimensions (legacy fallback)."""
    tags = meta.get("tags", {})
    # Legacy: top-level dimensions may exist from external scripts
    legacy_dims = meta.get("dimensions", {}) if isinstance(meta.get("dimensions"), dict) else {}
    dims = {}

    # Helper: get value from tags first, then legacy dims, then default
    def _get_dim(key, legacy_key=None, default="none"):
        if key in tags and tags[key]:
            return tags[key]
        lk = legacy_key or key
        if lk in legacy_dims and legacy_dims[lk]:
            val = legacy_dims[lk]
            # Map numeric values
            if isinstance(val, (int, float)):
                return {1: "green", 0: "none", -1: "red"}.get(val, default)
            return val if val in {"green", "yellow", "red", "none"} else default
        return default

    dims["quality"] = _get_dim("quality", "moat", "none")
    if dims["quality"] == "none" and "fundamental" in tags:
        dims["quality"] = tags["fundamental"]

    dims["valuation"] = _get_dim("valuation")

    dims["timing"] = _get_dim("timing", "technical")

    dims["risk"] = _get_dim("risk")

    dims["verdict"] = _get_dim("verdict", "overall", "none")
    if dims["verdict"] == "none" and "overall" in tags:
        dims["verdict"] = tags["overall"]

    return dims


def _load_tasks() -> list:
    if not os.path.exists(TASKS_FILE):
        return []
    tasks = _safe_json_load(TASKS_FILE, [])
    valid = [
        task for task in tasks
        if isinstance(task, dict)
        and isinstance(task.get("id"), str)
        and isinstance(task.get("status"), str)
    ]
    if len(valid) != len(tasks):
        print(f"[data-guard] _tasks.json 跳过 {len(tasks) - len(valid)} 条非法记录")
    return valid

def _save_tasks(tasks: list):
    _atomic_json_dump(TASKS_FILE, tasks)

def _load_dashboard() -> dict:
    if not os.path.exists(DASHBOARD_FILE):
        return {"prices": {}, "last_update": None}
    dashboard = _safe_json_load(DASHBOARD_FILE, {"prices": {}, "last_update": None})
    if not isinstance(dashboard.get("prices"), dict):
        dashboard["prices"] = {}
    else:
        dashboard["prices"] = {
            code: price
            for code, price in dashboard["prices"].items()
            if isinstance(code, str) and isinstance(price, dict)
        }
    return dashboard

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
    unread: Optional[bool] = None

class PriceMarkReq(BaseModel):
    label: str
    price: float
    type: Literal["target_buy", "stop_loss", "take_profit", "add", "reduce", "mark", "last_buy", "last_sell"] = "mark"

class StatusReq(BaseModel):
    status: Literal["unassessed", "tracking", "bullish", "neutral", "avoid", "no_interest", "blacklist", "waiting", "archive", "core_position"]

class HoldingsReq(BaseModel):
    cost: Optional[float] = None
    quantity: Optional[int] = None

class NoteReq(BaseModel):
    content: str

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
        code = meta.get("code", entry)
        p = prices.get(code, {})
        cached = cache.get(code, {})
        try:
            stocks.append({
                "code": code,
                "name": meta.get("name", code),
                "sector": meta.get("sector", ""),
                "tags": meta.get("tags", {}),
                "status": meta.get("status", "neutral"),
                "holdings": meta.get("holdings"),
                "dimensions": _normalize_dimensions(meta),
                "watchlist": meta.get("tags", {}).get("watchlist", False),
                "overall": meta.get("tags", {}).get("overall", "none"),
                "price_marks": meta.get("price_marks", []),
                "report_count": cached.get("report_count", 0),
                "last_analysis": cached.get("last_analysis"),
                "latest_note": _get_latest_note(entry),
                "last_price": p.get("price"),
                "change_pct": p.get("change_pct"),
                "price_updated": p.get("updated_at")
            })
        except Exception as e:
            # 单个股票数据异常只跳过该股票，不影响整个列表
            print(f"[data-guard] /api/stocks 跳过 {entry}: {type(e).__name__}: {e}")
            continue
    return stocks

@app.get("/api/stocks/{code}")
def get_stock(code: str):
    meta = _load_meta(code)
    meta.pop("daily_briefs", None)
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
    # Compute valid_until from report dates（日期串异常时跳过，不影响详情页）
    def _parse_dt(s):
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return None
    if last_fund:
        fund_dt = _parse_dt(last_fund)
        if fund_dt:
            meta["cache"]["fundamental"]["valid_until"] = (fund_dt + timedelta(days=90)).isoformat()
    if last_tech:
        tech_dt = _parse_dt(last_tech)
        if tech_dt:
            meta["cache"]["technical"]["valid_until"] = (tech_dt + timedelta(days=7)).isoformat()
    # Compute expired
    now = datetime.now(timezone.utc)
    for key in ["fundamental", "technical"]:
        vu = meta["cache"][key]["valid_until"]
        if not vu:
            meta["cache"][key]["expired"] = True
        else:
            vu_dt = _parse_dt(vu)
            if vu_dt is None:
                meta["cache"][key]["expired"] = True
                continue
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
    if req.unread is not None:
        meta["tags"]["unread"] = req.unread
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
    meta.setdefault("price_marks", []).append(mark)
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
    with open(path, "r", encoding="utf-8", errors="replace") as f:
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
    with open(path, "r", encoding="utf-8", errors="replace") as f:
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
    meta.setdefault("notes", []).insert(0, note_obj)
    _save_meta(code, meta)
    return note_obj

@app.delete("/api/stocks/{code}/notes/{note_time}")
def delete_note(code: str, note_time: str):
    """Delete note(s) by timestamp (notes.md entries with matching ## time header)."""
    path = _notes_path(code)
    if not os.path.exists(path):
        raise HTTPException(404, "Note not found")
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    # Rebuild file without entries matching note_time
    blocks = []
    current = None
    for line in content.splitlines():
        if line.startswith("## "):
            if current is not None:
                blocks.append(current)
            current = {"time": line[3:].strip(), "lines": []}
        elif current is not None:
            current["lines"].append(line)
    if current is not None:
        blocks.append(current)
    kept = [b for b in blocks if b["time"] != note_time]
    if len(kept) == len(blocks):
        raise HTTPException(404, "Note not found")
    with open(path, "w", encoding="utf-8") as f:
        for b in kept:
            f.write(f"## {b['time']}\n")
            body = "\n".join(b["lines"]).strip("\n")
            if body:
                f.write(body + "\n")
            f.write("\n")
    # Sync meta notes cache if present
    try:
        meta = _load_meta(code)
        if meta.get("notes"):
            meta["notes"] = [n for n in meta["notes"] if n.get("time") != note_time]
            _save_meta(code, meta)
    except Exception:
        pass
    return {"deleted": note_time}

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

    # Mark stock as unread - new analysis report not yet reviewed by user
    meta = _load_meta(code)
    meta.setdefault("tags", {})["unread"] = True
    _save_meta(code, meta)

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
        code = meta.get("code", entry)
        p = prices.get(code, {})
        current_price = p.get("price")
        cached = cache.get(code, {})

        try:
            # Calculate diffs for price marks（单个标记异常只跳过该标记）
            marks_with_diff = []
            for m in meta.get("price_marks", []):
                if not isinstance(m, dict):
                    continue
                diff = None
                diff_pct = None
                try:
                    mark_price = float(m.get("price"))
                except (TypeError, ValueError):
                    mark_price = None
                if current_price is not None and current_price > 0 and mark_price:
                    diff = current_price - mark_price
                    diff_pct = (diff / mark_price) * 100
                marks_with_diff.append({
                    **m,
                    "diff": diff,
                    "diff_pct": diff_pct
                })

            stocks.append({
                "code": code,
                "name": meta.get("name", code),
                "sector": meta.get("sector", ""),
                "tags": meta.get("tags", {}),
                "status": meta.get("status", "neutral"),
                "dimensions": _normalize_dimensions(meta),
                "watchlist": meta.get("tags", {}).get("watchlist", False),
                "overall": meta.get("tags", {}).get("overall", "none"),
                "price_marks": marks_with_diff,
                "report_count": cached.get("report_count", 0),
                "last_analysis": cached.get("last_analysis"),
                "latest_note": _get_latest_note(entry),
                "last_price": current_price,
                "change_pct": p.get("change_pct"),
                "price_updated": p.get("updated_at")
            })
        except Exception as e:
            # 单个股票数据异常只跳过该股票，不影响整个看板
            print(f"[data-guard] /api/dashboard 跳过 {entry}: {type(e).__name__}: {e}")
            continue
    
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


@app.get("/api/scheduler/status")
def scheduler_status():
    """定时任务运行状态（设置页展示：是否启用、间隔、上次/下次运行）。"""
    cfg = auth.load_config()
    tasks = {}
    for name in SCHEDULER_TASKS:
        interval = int(cfg.get(_INTERVAL_KEYS[name]) or 0)
        st = _scheduler_state[name]
        tasks[name] = {
            "enabled": interval > 0,
            "interval_min": interval,
            "running": bool(st.get("running")),
            "last_run": st.get("last_run"),
            "next_run": st.get("next_run_at"),
            "last_result": st.get("last_result", ""),
            "last_error": st.get("last_error", ""),
        }
    return {"tasks": tasks}


class TushareTestReq(BaseModel):
    token: Optional[str] = None


@app.post("/api/tushare/test")
def test_tushare(req: Optional[TushareTestReq] = None):
    """测试 Tushare token 连通性（不保存，仅验证）。"""
    token = ""
    if req and req.token:
        token = req.token.strip()
    if not token:
        token = (auth.load_config().get("tushare_token") or "").strip()
    if not token:
        token = os.environ.get("TUSHARE_TOKEN", "").strip()
    if not token:
        raise HTTPException(400, "未配置 Tushare token")
    try:
        import tushare as ts
        pro = ts.pro_api(token)
        today = datetime.now().strftime("%Y%m%d")
        df = pro.trade_cal(exchange="SSE", start_date=today, end_date=today)
        ok = df is not None and len(df) > 0
        return {"ok": ok, "message": "Tushare token 有效" if ok else "Tushare token 无效或权限不足"}
    except Exception as e:
        return {"ok": False, "message": f"Tushare 连接失败：{e}"}

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
    data = _safe_json_load(p, {"trades": [], "t_trades": [], "adj_events": [], "summary": {}})
    for key in ("trades", "t_trades", "adj_events"):
        values = data.get(key)
        if not isinstance(values, list):
            data[key] = []
            continue
        data[key] = [value for value in values if isinstance(value, dict)]
    if not isinstance(data.get("summary"), dict):
        data["summary"] = {}
    return data

def _save_holdings(code: str, data: dict):
    p = _holdings_path(code)
    _atomic_json_dump(p, data)

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
                same_day_buys = [
                    (i, p) for i, p in enumerate(positions)
                    if p["buy_date"] == sell_date and p["remaining"] > 0 and p["buy_time"] < sell_time
                ]
                same_day_buys.sort(key=lambda x: x[1]["buy_time"], reverse=True)

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

            # Step 1.5: 跨天最近批次优先 — 做T卖出日期最近的买入（非同日）
            if sell_qty > 0:
                recent_buys = [
                    (i, p) for i, p in enumerate(positions)
                    if p["buy_date"] != sell_date and p["remaining"] > 0
                ]
                recent_buys.sort(key=lambda x: x[1]["buy_date"], reverse=True)

                for idx, pos in recent_buys:
                    if sell_qty <= 0:
                        break
                    match_qty = min(sell_qty, pos["remaining"])
                    pos["remaining"] -= match_qty
                    sell_qty -= match_qty

                    profit = match_qty * (sell_price - pos["price"])
                    realized_pnl += profit

                    t_trades.append({
                        "id": f"tt_{uuid.uuid4().hex[:8]}",
                        "type": "正T(跨天)",
                        "buy_date": pos["buy_date"], "buy_time": pos["buy_time"], "buy_price": pos["price"],
                        "sell_date": sell_date, "sell_time": sell_time, "sell_price": sell_price,
                        "quantity": match_qty,
                        "profit": round(profit, 2),
                        "buy_trade_id": pos["from_trade"],
                        "sell_trade_id": trade_id,
                    })

            # Step 2: 底仓FIFO匹配（剩余部分）
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
            h = _safe_json_load(h_path, None)
            if not isinstance(h, dict):
                print(f"[data-guard] /api/holdings 跳过 {entry}: holdings.json 损坏")
                continue
            results.append({
                "code": entry,
                "quantity": h.get("summary", {}).get("total_quantity", 0),
                "avg_cost": h.get("summary", {}).get("avg_cost", 0),
                "realized_pnl": h.get("summary", {}).get("realized_pnl", 0),
            })
    return results

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
