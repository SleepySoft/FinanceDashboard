"""Stock reminders: per-stock persistence and global aggregation."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Literal, Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

import auth


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(BASE_DIR), "data")
LOCAL_TZ = ZoneInfo("Asia/Shanghai")
STATES = {"proposed", "active", "completed", "cancelled"}

stock_router = APIRouter(prefix="/api/stocks", tags=["reminders"])
global_router = APIRouter(prefix="/api/reminders", tags=["reminders"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _path(code: str) -> str:
    return os.path.join(DATA_DIR, code, "reminders.json")


def _require_stock(code: str) -> None:
    stock_dir = os.path.join(DATA_DIR, code)
    if not os.path.isfile(os.path.join(stock_dir, "meta.json")):
        raise HTTPException(404, f"Stock {code} not found")


def _parse_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise HTTPException(400, "remind_at 必须是带时区的 ISO 8601 时间") from exc
    if parsed.tzinfo is None:
        raise HTTPException(400, "remind_at 必须包含时区")
    return parsed.astimezone(timezone.utc)


def _load(code: str) -> dict:
    data = auth._load_json(_path(code), {"version": 1, "items": []})
    if not isinstance(data, dict):
        data = {"version": 1, "items": []}
    if not isinstance(data.get("items"), list):
        data["items"] = []
    return data


def _save(code: str, data: dict) -> None:
    os.makedirs(os.path.join(DATA_DIR, code), exist_ok=True)
    auth._save_json(_path(code), data)


def _stock_name(code: str) -> str:
    meta = auth._load_json(os.path.join(DATA_DIR, code, "meta.json"), {})
    return str(meta.get("name") or code) if isinstance(meta, dict) else code


def _display_state(item: dict, now: datetime | None = None) -> str:
    state = item.get("state")
    if state != "active":
        return state if state in STATES else "cancelled"
    now_local = (now or datetime.now(timezone.utc)).astimezone(LOCAL_TZ)
    due = _parse_time(item.get("remind_at", "")).astimezone(LOCAL_TZ)
    if due.date() < now_local.date():
        return "overdue"
    if due.date() == now_local.date():
        return "due_today" if due > now_local else "due_now"
    return "upcoming"


def _decorate(code: str, item: dict, name: str | None = None) -> dict:
    result = dict(item)
    result["code"] = code
    result["stock_name"] = name or _stock_name(code)
    try:
        result["display_state"] = _display_state(item)
    except HTTPException:
        result["display_state"] = "cancelled"
    return result


def _sort_key(item: dict):
    priority = {"overdue": 0, "due_now": 1, "due_today": 2, "proposed": 3,
                "upcoming": 4, "completed": 5, "cancelled": 6}
    return (priority.get(item.get("display_state"), 9), item.get("remind_at") or "")


class ReminderCreate(BaseModel):
    action: str = Field(min_length=1, max_length=500)
    remind_at: str

    @field_validator("action")
    @classmethod
    def clean_action(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("action 不能为空")
        return value

    @field_validator("remind_at")
    @classmethod
    def validate_time(cls, value: str) -> str:
        if _parse_time(value) <= datetime.now(timezone.utc):
            raise ValueError("提醒时间必须晚于当前时间")
        return value


class ReminderPatch(BaseModel):
    action: Optional[str] = Field(default=None, min_length=1, max_length=500)
    remind_at: Optional[str] = None
    state: Optional[Literal["proposed", "active", "completed", "cancelled"]] = None

    @field_validator("action")
    @classmethod
    def clean_action(cls, value: str | None):
        return value.strip() if value is not None else value

    @field_validator("remind_at")
    @classmethod
    def validate_time(cls, value: str | None):
        if value is not None:
            _parse_time(value)
        return value


class AgentReminderInput(ReminderCreate):
    pass


def replace_agent_proposals(
    code: str,
    task_id: str,
    items: list[AgentReminderInput],
    report_ids: list[str],
) -> int:
    """Idempotently replace still-proposed reminders from one analysis task."""
    data = _load(code)
    kept = [item for item in data["items"] if not (
        item.get("source") == "agent"
        and item.get("state") == "proposed"
        and isinstance(item.get("origin"), dict)
        and item["origin"].get("task_id") == task_id
    )]
    now = _now()
    for suggestion in items:
        kept.append({
            "id": f"rem_{uuid.uuid4().hex[:10]}",
            "action": suggestion.action,
            "remind_at": suggestion.remind_at,
            "state": "proposed",
            "source": "agent",
            "origin": {"task_id": task_id, "report_ids": report_ids},
            "created_by": "agent",
            "created_at": now,
            "updated_at": now,
            "completed_at": None,
        })
    data["items"] = kept
    _save(code, data)
    return len(items)


@stock_router.get("/{code}/reminders")
def list_stock_reminders(code: str, include_history: bool = False):
    _require_stock(code)
    items = [_decorate(code, item) for item in _load(code)["items"] if isinstance(item, dict)]
    if not include_history:
        items = [item for item in items if item.get("state") not in ("completed", "cancelled")]
    items.sort(key=_sort_key)
    return {"code": code, "items": items}


@stock_router.post("/{code}/reminders")
def create_stock_reminder(code: str, req: ReminderCreate, request: Request):
    _require_stock(code)
    if _parse_time(req.remind_at) <= datetime.now(timezone.utc):
        raise HTTPException(400, "提醒时间必须晚于当前时间")
    data = _load(code)
    now = _now()
    username = auth.get_current_user(request) or "unknown"
    item = {
        "id": f"rem_{uuid.uuid4().hex[:10]}", "action": req.action,
        "remind_at": req.remind_at, "state": "active", "source": "manual",
        "origin": None, "created_by": username, "created_at": now,
        "updated_at": now, "completed_at": None,
    }
    data["items"].append(item)
    _save(code, data)
    return _decorate(code, item)


@stock_router.patch("/{code}/reminders/{reminder_id}")
def update_stock_reminder(code: str, reminder_id: str, req: ReminderPatch):
    _require_stock(code)
    data = _load(code)
    item = next((entry for entry in data["items"] if isinstance(entry, dict) and entry.get("id") == reminder_id), None)
    if item is None:
        raise HTTPException(404, "提醒不存在")
    patch = req.model_dump(exclude_unset=True)
    target_time = patch.get("remind_at", item.get("remind_at"))
    target_state = patch.get("state", item.get("state"))
    if target_state == "active" and _parse_time(target_time) <= datetime.now(timezone.utc):
        raise HTTPException(400, "启用提醒前请将时间改到未来")
    for key in ("action", "remind_at", "state"):
        if key in patch:
            item[key] = patch[key]
    item["updated_at"] = _now()
    item["completed_at"] = _now() if item.get("state") == "completed" else None
    _save(code, data)
    return _decorate(code, item)


@stock_router.delete("/{code}/reminders/{reminder_id}")
def delete_stock_reminder(code: str, reminder_id: str):
    _require_stock(code)
    data = _load(code)
    kept = [item for item in data["items"] if not (isinstance(item, dict) and item.get("id") == reminder_id)]
    if len(kept) == len(data["items"]):
        raise HTTPException(404, "提醒不存在")
    data["items"] = kept
    _save(code, data)
    return {"deleted": reminder_id}


@global_router.get("")
def list_all_reminders(scope: str = "all", code: str = ""):
    allowed = {"all", "due", "upcoming", "proposed", "history"}
    if scope not in allowed:
        raise HTTPException(400, f"无效 scope: {scope}")
    items = []
    if not os.path.isdir(DATA_DIR):
        return {"items": [], "counts": {}}
    for entry in os.scandir(DATA_DIR):
        if not entry.is_dir() or entry.name.startswith("_") or (code and entry.name != code):
            continue
        path = _path(entry.name)
        if not os.path.isfile(path):
            continue
        name = _stock_name(entry.name)
        items.extend(_decorate(entry.name, item, name) for item in _load(entry.name)["items"] if isinstance(item, dict))
    counts = {
        "due": sum(item["display_state"] in ("overdue", "due_now", "due_today") for item in items),
        "proposed": sum(item.get("state") == "proposed" for item in items),
        "upcoming": sum(item["display_state"] == "upcoming" for item in items),
        "history": sum(item.get("state") in ("completed", "cancelled") for item in items),
    }
    if scope == "due":
        items = [item for item in items if item["display_state"] in ("overdue", "due_now", "due_today")]
    elif scope == "upcoming":
        items = [item for item in items if item["display_state"] == "upcoming"]
    elif scope == "proposed":
        items = [item for item in items if item.get("state") == "proposed"]
    elif scope == "history":
        items = [item for item in items if item.get("state") in ("completed", "cancelled")]
    items.sort(key=_sort_key)
    return {"items": items, "counts": counts, "timezone": "Asia/Shanghai"}
