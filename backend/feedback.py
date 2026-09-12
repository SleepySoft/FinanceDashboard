# -*- coding: utf-8 -*-
"""股票反馈：每股每人一票（赞同/反对 + 可选评论），POW 由 powbox 校验（scope=feedback）。

存储 data/{code}/feedback.json：{"votes": [{username, vote, comment, updated_at, pow_difficulty}]}
只保留每个用户的当前一票（upsert 覆盖），不记历史；改票即覆盖，天然幂等。
"""
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

import auth
from powbox import pow

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(BASE_DIR), "data")

MAX_COMMENT_LEN = 500

router = APIRouter(prefix="/api/stocks", tags=["feedback"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _feedback_path(code: str) -> str:
    return os.path.join(DATA_DIR, code, "feedback.json")


def _load(code: str) -> dict:
    data = auth._load_json(_feedback_path(code), {"votes": []})
    if not isinstance(data, dict) or not isinstance(data.get("votes"), list):
        return {"votes": []}
    data["votes"] = [v for v in data["votes"] if isinstance(v, dict) and v.get("username")]
    return data


def _save(code: str, data: dict):
    auth._save_json(_feedback_path(code), data)


def _require_stock(code: str):
    if not os.path.isfile(os.path.join(DATA_DIR, code, "meta.json")):
        raise HTTPException(404, f"Stock {code} not found")


def _viewer_is_admin(viewer: Optional[str]) -> bool:
    return bool(viewer and not viewer.startswith("guest:") and auth.get_user_role(viewer) == "admin")


def _summary(code: str, viewer: Optional[str]) -> dict:
    votes = _load(code)["votes"]
    votes = sorted(votes, key=lambda v: v.get("updated_at", ""), reverse=True)
    mine = next((v for v in votes if v["username"] == viewer), None) if viewer else None
    visibility = auth.load_config().get("comments_visibility", "public")
    if visibility == "admin" and not _viewer_is_admin(viewer):
        return {
            "up": 0,
            "down": 0,
            "entries": [],
            "my_vote": mine,
            "visibility": "admin",
        }
    return {
        "up": sum(1 for v in votes if v.get("vote") == "up"),
        "down": sum(1 for v in votes if v.get("vote") == "down"),
        "entries": votes,
        "my_vote": mine,
        "visibility": visibility,
    }


def _feedback_identity(request: Request) -> Optional[str]:
    username = auth.get_session_user(request)
    if username:
        return username
    if auth.load_config().get("comments_require_login", True):
        return None
    return auth.get_guest_identity(request)


@router.get("/{code}/feedback")
def get_feedback(code: str, request: Request):
    """读权限跟随全局规则；未登录游客在开启匿名评论后可见自己的投票。"""
    _require_stock(code)
    viewer = _feedback_identity(request)
    return _summary(code, viewer)


class FeedbackReq(BaseModel):
    vote: str
    comment: Optional[str] = ""
    pow: Optional[dict] = None


@router.post("/{code}/feedback")
def submit_feedback(code: str, req: FeedbackReq, request: Request, response: Response):
    _require_stock(code)
    username = auth.get_session_user(request)
    if not username:
        if auth.load_config().get("comments_require_login", True):
            raise HTTPException(401, "需要登录")
        username = auth.ensure_guest_identity(request, response)
    if req.vote not in ("up", "down"):
        raise HTTPException(400, "vote 只能是 up 或 down")
    comment = (req.comment or "").strip()
    if len(comment) > MAX_COMMENT_LEN:
        raise HTTPException(400, f"评论过长（≤{MAX_COMMENT_LEN} 字）")
    # POW 绑定内容：股票 + 票型 + 评论，换掉任何一项校验即失败
    bound = f"{code}|{req.vote}|{comment}"
    try:
        difficulty = pow.verify_pow(req.pow, bound, scope="feedback", username=username)
    except pow.PowError as e:
        raise HTTPException(400, str(e))

    data = _load(code)
    entry = next((v for v in data["votes"] if v["username"] == username), None)
    if entry is None:
        entry = {"username": username}
        data["votes"].append(entry)
    entry.update({
        "vote": req.vote,
        "comment": comment,
        "updated_at": _now(),
        "pow_difficulty": difficulty,
    })
    _save(code, data)
    return {"ok": True, **_summary(code, username)}


@router.delete("/{code}/feedback")
def withdraw_feedback(code: str, request: Request):
    """撤回自己的反馈（删自己的数据，无需 POW）。"""
    _require_stock(code)
    username = _feedback_identity(request)
    if not username:
        raise HTTPException(401, "需要登录")
    data = _load(code)
    before = len(data["votes"])
    data["votes"] = [v for v in data["votes"] if v["username"] != username]
    if len(data["votes"]) == before:
        raise HTTPException(404, "你还没有反馈过该股票")
    _save(code, data)
    return {"ok": True, **_summary(code, username)}


@router.delete("/{code}/feedback/all")
def clear_feedback(code: str, username: str = Depends(auth.require_admin)):
    """admin 清空当前股票的全部反馈。"""
    _require_stock(code)
    _save(code, {"votes": []})
    return {"ok": True, **_summary(code, username)}


@router.delete("/{code}/feedback/{name}")
def delete_feedback(code: str, name: str, username: str = Depends(auth.require_admin)):
    """admin 删除任意用户的反馈条目。"""
    _require_stock(code)
    data = _load(code)
    before = len(data["votes"])
    data["votes"] = [v for v in data["votes"] if v["username"] != name]
    if len(data["votes"]) == before:
        raise HTTPException(404, "该用户没有反馈记录")
    _save(code, data)
    return {"ok": True, **_summary(code, username)}
