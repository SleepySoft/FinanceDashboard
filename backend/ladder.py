# -*- coding: utf-8 -*-
"""价格阶梯（交易价格辅助）：每只股票的买入/卖出计划价位 + 临近/触及提醒。

存储 data/{code}/ladder.json：
{
  "alert_threshold_pct": 2.0,           # 距离当前价 ≤ 该百分比视为「临近」
  "strategy": {"type": "grid", "params": {...}, "updated_at": ...} | null,
  "levels": [{"id", "side": buy|sell, "price", "qty", "note",
              "source": manual|strategy|agent, "enabled", "created_at", "updated_at"}]
}

三种录入来源共存、按 source 分区替换，互不覆盖：
- manual   用户在面板逐条增删改（PUT levels / POST·PATCH·DELETE level）
- strategy 内置策略计算（首期 grid 网格；重算只替换 strategy 档）
- agent    AI 通过 /api/agent/stocks/{code}/ladder 整体替换（如压力位/支撑位）

提醒语义（_decorate，基于 _dashboard.json 当前价）：
- buy : 当前价 ≤ 档位价 → triggered；高出档位 ≤ threshold% → near；否则 pending
- sell: 当前价 ≥ 档位价 → triggered；低于档位 ≤ threshold% → near；否则 pending
"""
import math
import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import auth

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(BASE_DIR), "data")
DASHBOARD_FILE = os.path.join(DATA_DIR, "_dashboard.json")

DEFAULT_THRESHOLD_PCT = 2.0
MAX_LEVELS = 100
MAX_NOTE_LEN = 100
SOURCES = ("manual", "strategy", "agent")

router = APIRouter(prefix="/api/stocks", tags=["ladder"])
agent_router = APIRouter(prefix="/api/agent/stocks", tags=["ladder-agent"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ladder_path(code: str) -> str:
    return os.path.join(DATA_DIR, code, "ladder.json")


def _require_stock(code: str):
    if not os.path.isfile(os.path.join(DATA_DIR, code, "meta.json")):
        raise HTTPException(404, f"Stock {code} not found")


def _load(code: str) -> dict:
    data = auth._load_json(_ladder_path(code), {})
    if not isinstance(data, dict):
        data = {}
    levels = data.get("levels")
    if not isinstance(levels, list):
        levels = []
    data["levels"] = [lv for lv in levels if isinstance(lv, dict) and lv.get("id")]
    strategy = data.get("strategy")
    if not isinstance(strategy, dict) or strategy.get("type") not in STRATEGIES:
        strategy = None
    data["strategy"] = strategy
    try:
        th = float(data.get("alert_threshold_pct", DEFAULT_THRESHOLD_PCT))
        data["alert_threshold_pct"] = th if math.isfinite(th) and 0 < th <= 50 else DEFAULT_THRESHOLD_PCT
    except (TypeError, ValueError):
        data["alert_threshold_pct"] = DEFAULT_THRESHOLD_PCT
    return data


def _save(code: str, data: dict):
    auth._save_json(_ladder_path(code), data)


def _dashboard_entry(code: str) -> dict:
    dash = auth._load_json(DASHBOARD_FILE, {})
    prices = dash.get("prices") if isinstance(dash, dict) else None
    entry = prices.get(code.upper()) if isinstance(prices, dict) else None
    return entry if isinstance(entry, dict) else {}


def _current_price(code: str) -> Optional[float]:
    price = _dashboard_entry(code).get("price")
    if isinstance(price, bool):
        return None
    try:
        value = float(price)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) and value > 0 else None


# ─── 策略 ─────────────────────────────────────────────────────

def _grid_levels(params: dict, current_price: Optional[float]) -> List[dict]:
    """网格：以基准价为中心，向下 N 档买入、向上 M 档卖出，等百分比步长。"""
    base = params.get("base_price")
    try:
        base = float(base) if base is not None else None
    except (TypeError, ValueError):
        base = None
    if base is None or not math.isfinite(base) or base <= 0:
        if current_price is None:
            raise HTTPException(400, "缺少基准价且当前无行情价格，请显式提供 base_price")
        base = current_price
    try:
        step_pct = float(params.get("step_pct", 3.0))
        up = int(params.get("up", 3))
        down = int(params.get("down", 3))
    except (TypeError, ValueError):
        raise HTTPException(400, "网格参数格式错误")
    if not (0.1 <= step_pct <= 50):
        raise HTTPException(400, "step_pct 需在 0.1~50 之间")
    if not (0 <= up <= 20) or not (0 <= down <= 20) or (up + down) == 0:
        raise HTTPException(400, "up/down 需在 0~20 之间且不能都为 0")
    qty = params.get("qty")
    if qty is not None:
        try:
            qty = int(qty)
        except (TypeError, ValueError):
            raise HTTPException(400, "qty 需为整数")
        if qty <= 0:
            qty = None

    levels = []
    for i in range(1, down + 1):
        levels.append({"side": "buy", "price": round(base * (1 - step_pct / 100) ** i, 3),
                       "qty": qty, "note": f"网格-{i}"})
    for i in range(1, up + 1):
        levels.append({"side": "sell", "price": round(base * (1 + step_pct / 100) ** i, 3),
                       "qty": qty, "note": f"网格+{i}"})
    return levels


STRATEGIES = {"grid": _grid_levels}


# ─── 校验与装饰 ───────────────────────────────────────────────

def _clean_level(raw: dict, source: str) -> dict:
    side = raw.get("side")
    if side not in ("buy", "sell"):
        raise HTTPException(400, "side 只能是 buy 或 sell")
    try:
        price = float(raw.get("price"))
    except (TypeError, ValueError):
        raise HTTPException(400, "price 需为数字")
    if not math.isfinite(price) or price <= 0:
        raise HTTPException(400, "price 需为正数")
    qty = raw.get("qty")
    if qty is not None:
        try:
            qty = int(qty)
        except (TypeError, ValueError):
            raise HTTPException(400, "qty 需为整数")
        if qty <= 0:
            qty = None
    note = str(raw.get("note") or "").strip()[:MAX_NOTE_LEN]
    now = _now()
    return {
        "id": uuid.uuid4().hex[:10],
        "side": side,
        "price": price,
        "qty": qty,
        "note": note,
        "source": source,
        "enabled": bool(raw.get("enabled", True)),
        "created_at": now,
        "updated_at": now,
    }


def _state_for(side: str, price: float, current: Optional[float], threshold: float) -> str:
    if current is None or current <= 0:
        return "unknown"
    if side == "buy":
        if current <= price:
            return "triggered"
        return "near" if (current - price) / current * 100 <= threshold else "pending"
    if current >= price:
        return "triggered"
    return "near" if (price - current) / current * 100 <= threshold else "pending"


def _decorate(level: dict, current: Optional[float], threshold: float) -> dict:
    out = dict(level)
    price = level.get("price")
    if current is not None and isinstance(price, (int, float)) and not isinstance(price, bool):
        out["diff_pct"] = round((price - current) / current * 100, 2)
        out["state"] = _state_for(level.get("side"), price, current, threshold) if level.get("enabled", True) else "disabled"
    else:
        out["diff_pct"] = None
        out["state"] = "unknown" if level.get("enabled", True) else "disabled"
    return out


def _payload(code: str) -> dict:
    data = _load(code)
    current = _current_price(code)
    threshold = data["alert_threshold_pct"]
    levels = sorted(data["levels"], key=lambda lv: lv.get("price") or 0, reverse=True)
    return {
        "code": code,
        "current_price": current,
        "price_updated": _dashboard_entry(code).get("updated_at"),
        "alert_threshold_pct": threshold,
        "strategy": data["strategy"],
        "levels": [_decorate(lv, current, threshold) for lv in levels],
    }


def hint(code: str, current_price: Optional[float]) -> Optional[dict]:
    """看板卡片用：最近的买/卖档位 + 触及计数。任何异常都返回 None，不拖垮看板。"""
    try:
        data = _load(code)
        levels = [lv for lv in data["levels"]
                  if lv.get("enabled", True) and isinstance(lv.get("price"), (int, float))]
        if not levels or current_price is None or current_price <= 0:
            return None
        threshold = data["alert_threshold_pct"]
        buys = [lv for lv in levels if lv.get("side") == "buy"]
        sells = [lv for lv in levels if lv.get("side") == "sell"]

        def brief(lv):
            return {
                "price": lv["price"],
                "diff_pct": round((lv["price"] - current_price) / current_price * 100, 2),
                "state": _state_for(lv["side"], lv["price"], current_price, threshold),
            }

        triggered = sum(1 for lv in levels
                        if _state_for(lv.get("side"), lv["price"], current_price, threshold) == "triggered")
        return {
            "next_buy": brief(max(buys, key=lambda lv: lv["price"])) if buys else None,
            "next_sell": brief(min(sells, key=lambda lv: lv["price"])) if sells else None,
            "triggered": triggered,
        }
    except Exception:
        return None


# ─── 请求模型 ─────────────────────────────────────────────────

class LevelIn(BaseModel):
    side: str
    price: float
    qty: Optional[int] = None
    note: Optional[str] = ""


class LevelPatch(BaseModel):
    side: Optional[str] = None
    price: Optional[float] = None
    qty: Optional[int] = None
    note: Optional[str] = None
    enabled: Optional[bool] = None


class LadderConfigReq(BaseModel):
    alert_threshold_pct: Optional[float] = None
    levels: Optional[List[LevelIn]] = None  # 提供时整体替换 manual 档


class StrategyReq(BaseModel):
    type: str
    params: Optional[dict] = None


class AgentLevelsReq(BaseModel):
    levels: List[LevelIn]


# ─── 用户路由（写权限由全局中间件控制：登录可写，只读账号 403） ───

@router.get("/{code}/ladder")
def get_ladder(code: str):
    _require_stock(code)
    return _payload(code)


@router.put("/{code}/ladder")
def put_ladder(code: str, req: LadderConfigReq):
    _require_stock(code)
    data = _load(code)
    if req.alert_threshold_pct is not None:
        if not math.isfinite(req.alert_threshold_pct) or not (0 < req.alert_threshold_pct <= 50):
            raise HTTPException(400, "alert_threshold_pct 需在 0~50 之间")
        data["alert_threshold_pct"] = req.alert_threshold_pct
    if req.levels is not None:
        if len(req.levels) > MAX_LEVELS:
            raise HTTPException(400, f"阶梯最多 {MAX_LEVELS} 条")
        kept = [lv for lv in data["levels"] if lv.get("source") != "manual"]
        kept.extend(_clean_level(lv.dict(), "manual") for lv in req.levels)
        data["levels"] = kept
    _save(code, data)
    return _payload(code)


@router.post("/{code}/ladder/levels")
def add_level(code: str, req: LevelIn):
    _require_stock(code)
    data = _load(code)
    if len(data["levels"]) >= MAX_LEVELS:
        raise HTTPException(400, f"阶梯最多 {MAX_LEVELS} 条")
    data["levels"].append(_clean_level(req.dict(), "manual"))
    _save(code, data)
    return _payload(code)


def _find_manual(data: dict, level_id: str) -> dict:
    for lv in data["levels"]:
        if lv.get("id") == level_id:
            if lv.get("source") != "manual":
                raise HTTPException(400, "策略/AI 生成的档位请用对应入口修改或清除")
            return lv
    raise HTTPException(404, "档位不存在")


@router.patch("/{code}/ladder/levels/{level_id}")
def update_level(code: str, level_id: str, req: LevelPatch):
    _require_stock(code)
    data = _load(code)
    lv = _find_manual(data, level_id)
    patch = {k: v for k, v in req.dict().items() if v is not None}
    if patch:
        merged = _clean_level({**lv, **patch}, "manual")
        merged["id"] = lv["id"]
        merged["created_at"] = lv.get("created_at") or merged["created_at"]
        lv.update(merged)
        lv["updated_at"] = _now()
        _save(code, data)
    return _payload(code)


@router.delete("/{code}/ladder/levels/{level_id}")
def delete_level(code: str, level_id: str):
    _require_stock(code)
    data = _load(code)
    _find_manual(data, level_id)
    data["levels"] = [lv for lv in data["levels"] if lv.get("id") != level_id]
    _save(code, data)
    return _payload(code)


@router.post("/{code}/ladder/strategy")
def apply_strategy(code: str, req: StrategyReq):
    _require_stock(code)
    gen = STRATEGIES.get(req.type)
    if gen is None:
        raise HTTPException(400, f"未知策略 {req.type}，可选：{', '.join(STRATEGIES)}")
    params = req.params or {}
    levels = gen(params, _current_price(code))
    data = _load(code)
    kept = [lv for lv in data["levels"] if lv.get("source") != "strategy"]
    kept.extend(_clean_level(lv, "strategy") for lv in levels)
    if len(kept) > MAX_LEVELS:
        raise HTTPException(400, f"阶梯最多 {MAX_LEVELS} 条")
    data["levels"] = kept
    data["strategy"] = {"type": req.type, "params": params, "updated_at": _now()}
    _save(code, data)
    return _payload(code)


@router.delete("/{code}/ladder/strategy")
def clear_strategy(code: str):
    _require_stock(code)
    data = _load(code)
    data["levels"] = [lv for lv in data["levels"] if lv.get("source") != "strategy"]
    data["strategy"] = None
    _save(code, data)
    return _payload(code)


# ─── Agent 路由（中间件强制 /api/agent/* 需登录或 X-API-Key） ────

@agent_router.get("/{code}/ladder")
def agent_get_ladder(code: str):
    _require_stock(code)
    return _payload(code)


@agent_router.put("/{code}/ladder")
def agent_put_ladder(code: str, req: AgentLevelsReq):
    """AI 整体替换 agent 档（如算出的压力位/支撑位），不影响 manual/strategy 档。"""
    _require_stock(code)
    if len(req.levels) > MAX_LEVELS:
        raise HTTPException(400, f"阶梯最多 {MAX_LEVELS} 条")
    data = _load(code)
    kept = [lv for lv in data["levels"] if lv.get("source") != "agent"]
    kept.extend(_clean_level(lv.dict(), "agent") for lv in req.levels)
    data["levels"] = kept
    _save(code, data)
    return _payload(code)


@agent_router.delete("/{code}/ladder")
def agent_clear_ladder(code: str):
    _require_stock(code)
    data = _load(code)
    data["levels"] = [lv for lv in data["levels"] if lv.get("source") != "agent"]
    _save(code, data)
    return _payload(code)
