"""Unified price-level read/write model over marks, ladder plans and holdings facts."""

from __future__ import annotations

import math
import os
import uuid
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import auth
import ladder


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(BASE_DIR), "data")
LIFECYCLE_STATES = {"proposed", "active", "retired", "invalidated", "expired"}

router = APIRouter(prefix="/api/stocks", tags=["price-levels"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require_stock(code: str) -> None:
    if not os.path.isfile(os.path.join(DATA_DIR, code, "meta.json")):
        raise HTTPException(404, f"Stock {code} not found")


def _state_path(code: str) -> str:
    return os.path.join(DATA_DIR, code, "state.json")


def _holdings_path(code: str) -> str:
    return os.path.join(DATA_DIR, code, "holdings.json")


def _registry() -> tuple[list[dict], dict[str, dict]]:
    items = auth.get_price_level_types(auth.load_config())
    return items, {item["key"]: item for item in items}


def _load_state(code: str) -> dict:
    state = auth._load_json(_state_path(code), {})
    if not isinstance(state, dict):
        state = {}
    if not isinstance(state.get("price_marks"), list):
        state["price_marks"] = []
    return state


def _clean_price(value) -> float:
    try:
        price = float(value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(400, "price 需为数字") from exc
    if not math.isfinite(price) or price <= 0:
        raise HTTPException(400, "price 需为正数")
    return price


def _clean_state(value: str | None, default: str = "active") -> str:
    state = value or default
    if state not in LIFECYCLE_STATES:
        raise HTTPException(400, f"无效 state: {state}")
    return state


def _analysis_level(mark: dict, types: dict[str, dict]) -> dict | None:
    try:
        price = _clean_price(mark.get("price"))
    except HTTPException:
        return None
    type_key = str(mark.get("type") or "custom")
    type_meta = types.get(type_key)
    if not type_meta or type_meta["family"] != "analysis":
        type_key = "custom" if "custom" in types else "mark"
        type_meta = types.get(type_key, {"label": mark.get("label") or "标记"})
    storage_id = str(mark.get("id") or uuid.uuid4().hex[:8])
    return {
        "id": f"analysis:{storage_id}",
        "storage_id": storage_id,
        "family": "analysis",
        "type": type_key,
        "label": type_meta.get("label") or mark.get("label") or type_key,
        "price": price,
        "source": mark.get("source") if mark.get("source") in ("manual", "agent", "strategy", "system") else "manual",
        "state": mark.get("state") if mark.get("state") in LIFECYCLE_STATES else "active",
        "note": str(mark.get("note") or ""),
        "valid_from": mark.get("valid_from"),
        "valid_until": mark.get("valid_until"),
        "created_at": mark.get("created_at"),
        "updated_at": mark.get("updated_at") or mark.get("created_at"),
    }


def _plan_level(level: dict, types: dict[str, dict]) -> dict | None:
    try:
        price = _clean_price(level.get("price"))
    except HTTPException:
        return None
    side = level.get("side") if level.get("side") in ("buy", "sell") else "buy"
    type_key = str(level.get("type") or side)
    type_meta = types.get(type_key)
    if not type_meta or type_meta.get("family") != "plan" or type_meta.get("side") != side:
        type_key = side
        type_meta = types.get(type_key, {"label": "买入" if side == "buy" else "卖出"})
    storage_id = str(level.get("id"))
    lifecycle = level.get("lifecycle_state")
    if lifecycle not in LIFECYCLE_STATES:
        lifecycle = "active" if level.get("enabled", True) else "retired"
    return {
        "id": f"plan:{storage_id}",
        "storage_id": storage_id,
        "family": "plan",
        "type": type_key,
        "label": type_meta.get("label") or type_key,
        "price": price,
        "source": level.get("source") if level.get("source") in ("manual", "agent", "strategy") else "manual",
        "state": lifecycle,
        "note": str(level.get("note") or ""),
        "valid_from": level.get("valid_from"),
        "valid_until": level.get("valid_until"),
        "created_at": level.get("created_at"),
        "updated_at": level.get("updated_at") or level.get("created_at"),
        "plan": {"side": side, "qty": level.get("qty")},
        "proximity": {"state": level.get("state"), "diff_pct": level.get("diff_pct")},
    }


def _fact_levels(code: str, types: dict[str, dict]) -> list[dict]:
    data = auth._load_json(_holdings_path(code), {})
    if not isinstance(data, dict):
        return []
    trades = [item for item in data.get("trades", []) if isinstance(item, dict)]
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    facts = []
    definitions = (
        ("last_buy", next((item for item in reversed(trades) if item.get("type") == "buy"), None)),
        ("last_sell", next((item for item in reversed(trades) if item.get("type") == "sell"), None)),
    )
    for type_key, trade in definitions:
        if not trade:
            continue
        try:
            price = _clean_price(trade.get("price"))
        except HTTPException:
            continue
        facts.append({
            "id": f"fact:{type_key}", "storage_id": None, "family": "fact",
            "type": type_key, "label": types.get(type_key, {}).get("label", type_key),
            "price": price, "source": "system", "state": "active", "note": trade.get("note") or "",
            "valid_from": None, "valid_until": None, "created_at": None, "updated_at": None,
            "fact": {"trade_id": trade.get("id")},
        })
    avg_cost = summary.get("avg_cost")
    try:
        avg_cost = float(avg_cost)
    except (TypeError, ValueError):
        avg_cost = 0
    if math.isfinite(avg_cost) and avg_cost > 0 and summary.get("total_quantity", 0) > 0:
        facts.append({
            "id": "fact:average_cost", "storage_id": None, "family": "fact",
            "type": "average_cost", "label": types.get("average_cost", {}).get("label", "持仓成本"),
            "price": avg_cost, "source": "system", "state": "active", "note": "",
            "valid_from": None, "valid_until": None, "created_at": None, "updated_at": None,
            "fact": {"quantity": summary.get("total_quantity")},
        })
    return facts


def _payload(code: str) -> dict:
    type_list, types = _registry()
    state = _load_state(code)
    analysis = [item for mark in state["price_marks"] if isinstance(mark, dict)
                if (item := _analysis_level(mark, types)) is not None]
    ladder_payload = ladder._payload(code)
    plans = [item for level in ladder_payload["levels"]
             if (item := _plan_level(level, types)) is not None]
    levels = analysis + plans + _fact_levels(code, types)
    levels.sort(key=lambda item: (-item["price"], item["family"], item["label"]))
    return {
        "code": code,
        "current_price": ladder_payload.get("current_price"),
        "price_updated": ladder_payload.get("price_updated"),
        "types": type_list,
        "levels": levels,
    }


class PriceLevelCreate(BaseModel):
    family: Literal["analysis", "plan"]
    type: str
    price: float
    note: Optional[str] = ""
    qty: Optional[int] = None
    state: Optional[str] = None
    valid_from: Optional[str] = None
    valid_until: Optional[str] = None


class PriceLevelPatch(BaseModel):
    type: Optional[str] = None
    price: Optional[float] = None
    note: Optional[str] = None
    qty: Optional[int] = None
    state: Optional[str] = None
    valid_from: Optional[str] = None
    valid_until: Optional[str] = None


def _type_for(type_key: str, family: str) -> dict:
    _, types = _registry()
    item = types.get(type_key)
    if not item or item.get("family") != family:
        raise HTTPException(400, f"类型 {type_key!r} 不属于 {family}")
    return item


@router.get("/{code}/price-levels")
def list_price_levels(code: str):
    _require_stock(code)
    return _payload(code)


@router.post("/{code}/price-levels")
def create_price_level(code: str, req: PriceLevelCreate):
    _require_stock(code)
    type_meta = _type_for(req.type, req.family)
    price = _clean_price(req.price)
    lifecycle = _clean_state(req.state)
    now = _now()
    if req.family == "analysis":
        state = _load_state(code)
        state["price_marks"].append({
            "id": uuid.uuid4().hex[:8], "label": type_meta["label"], "price": price,
            "type": req.type, "source": "manual", "state": lifecycle,
            "note": (req.note or "")[:200], "valid_from": req.valid_from,
            "valid_until": req.valid_until, "created_at": now, "updated_at": now,
        })
        auth._save_json(_state_path(code), state)
    else:
        data = ladder._load(code)
        if len(data["levels"]) >= ladder.MAX_LEVELS:
            raise HTTPException(400, f"价格水位最多 {ladder.MAX_LEVELS} 条计划")
        level = ladder._clean_level({
            "side": type_meta["side"], "price": price, "qty": req.qty,
            "note": req.note or "", "enabled": lifecycle == "active",
        }, "manual")
        level.update({"type": req.type, "lifecycle_state": lifecycle,
                      "valid_from": req.valid_from, "valid_until": req.valid_until})
        data["levels"].append(level)
        ladder._save(code, data)
    return _payload(code)


def _split_level_id(level_id: str) -> tuple[str, str]:
    if ":" not in level_id:
        raise HTTPException(400, "无效价格水位 id")
    family, storage_id = level_id.split(":", 1)
    if family not in ("analysis", "plan", "fact") or not storage_id:
        raise HTTPException(400, "无效价格水位 id")
    return family, storage_id


@router.patch("/{code}/price-levels/{level_id}")
def update_price_level(code: str, level_id: str, req: PriceLevelPatch):
    _require_stock(code)
    family, storage_id = _split_level_id(level_id)
    if family == "fact":
        raise HTTPException(400, "事实水位由交易记录生成，不能直接修改")
    patch = req.model_dump(exclude_unset=True)
    if "state" in patch:
        patch["state"] = _clean_state(patch["state"])
    if "price" in patch:
        patch["price"] = _clean_price(patch["price"])
    if "type" in patch:
        type_meta = _type_for(patch["type"], family)
    else:
        type_meta = None
    if family == "analysis":
        state = _load_state(code)
        target = next((m for m in state["price_marks"] if isinstance(m, dict) and str(m.get("id")) == storage_id), None)
        if target is None:
            raise HTTPException(404, "价格水位不存在")
        if type_meta:
            target["type"] = patch["type"]
            target["label"] = type_meta["label"]
        for key in ("price", "note", "state", "valid_from", "valid_until"):
            if key in patch:
                target[key] = patch[key]
        target["updated_at"] = _now()
        auth._save_json(_state_path(code), state)
    else:
        data = ladder._load(code)
        target = next((lv for lv in data["levels"] if str(lv.get("id")) == storage_id), None)
        if target is None:
            raise HTTPException(404, "价格水位不存在")
        if target.get("source") != "manual":
            raise HTTPException(400, "策略或 AI 计划需通过对应来源更新")
        if type_meta:
            target["type"] = patch["type"]
            target["side"] = type_meta["side"]
        for key in ("price", "note", "qty", "valid_from", "valid_until"):
            if key in patch:
                target[key] = patch[key]
        if "state" in patch:
            target["lifecycle_state"] = patch["state"]
            target["enabled"] = patch["state"] == "active"
        target["updated_at"] = _now()
        ladder._save(code, data)
    return _payload(code)


@router.delete("/{code}/price-levels/{level_id}")
def delete_price_level(code: str, level_id: str):
    _require_stock(code)
    family, storage_id = _split_level_id(level_id)
    if family == "fact":
        raise HTTPException(400, "事实水位由交易记录生成，不能直接删除")
    if family == "analysis":
        state = _load_state(code)
        before = len(state["price_marks"])
        state["price_marks"] = [m for m in state["price_marks"] if str(m.get("id")) != storage_id]
        if len(state["price_marks"]) == before:
            raise HTTPException(404, "价格水位不存在")
        auth._save_json(_state_path(code), state)
    else:
        data = ladder._load(code)
        target = next((lv for lv in data["levels"] if str(lv.get("id")) == storage_id), None)
        if target is None:
            raise HTTPException(404, "价格水位不存在")
        if target.get("source") != "manual":
            raise HTTPException(400, "策略或 AI 计划需通过对应来源清除")
        data["levels"] = [lv for lv in data["levels"] if str(lv.get("id")) != storage_id]
        ladder._save(code, data)
    return _payload(code)
