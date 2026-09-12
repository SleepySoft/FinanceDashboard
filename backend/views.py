# -*- coding: utf-8 -*-
"""最后浏览时间：记录每个用户最后一次打开股票详情的时间。

存储 data/{code}/views.json：{"views": {username: iso_time}}
- POST /api/stocks/{code}/viewed 仅管理员可调用；非管理员的浏览不记录。
- 看板/详情接口仅对管理员返回 last_viewed；超过配置的 stale_view_days 未浏览时前端闪烁提醒。
"""
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

import auth

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(BASE_DIR), "data")

router = APIRouter(prefix="/api/stocks", tags=["views"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _views_path(code: str) -> str:
    return os.path.join(DATA_DIR, code, "views.json")


def _load(code: str) -> dict:
    data = auth._load_json(_views_path(code), {"views": {}})
    if not isinstance(data, dict) or not isinstance(data.get("views"), dict):
        return {"views": {}}
    data["views"] = {k: v for k, v in data["views"].items()
                     if isinstance(k, str) and isinstance(v, str)}
    return data


def last_viewed(code: str, username: Optional[str]) -> Optional[str]:
    """供看板/详情接口调用；仅管理员可见，任何异常返回 None，不拖垮主接口。"""
    if not username or username == "_agent":
        return None
    try:
        if auth.get_user_role(username) != "admin":
            return None
        return _load(code)["views"].get(username)
    except Exception:
        return None


@router.post("/{code}/viewed")
def mark_viewed(code: str, username: str = Depends(auth.require_admin)):
    if not os.path.isfile(os.path.join(DATA_DIR, code, "meta.json")):
        raise HTTPException(404, f"Stock {code} not found")
    data = _load(code)
    ts = _now()
    data["views"][username] = ts
    auth._save_json(_views_path(code), data)
    return {"ok": True, "last_viewed": ts}
