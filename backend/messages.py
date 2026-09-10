# -*- coding: utf-8 -*-
"""消息箱：登录用户给站主留言。POW 由 powbox 校验（scope=message）。

存储 data/_messages.json：{"messages": [{id, username, content, created_at, pow_difficulty}]}
防重放：POW 绑定内容 + 10 分钟 challenge 有效期；同用户同内容在有效期内重复提交视为重放拒绝。
"""
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import auth
from powbox import pow

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MESSAGES_FILE = os.path.join(os.path.dirname(BASE_DIR), "data", "_messages.json")

MAX_CONTENT_LEN = 2000

router = APIRouter(prefix="/api/messages", tags=["messages"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load() -> dict:
    data = auth._load_json(MESSAGES_FILE, {"messages": []})
    if not isinstance(data, dict) or not isinstance(data.get("messages"), list):
        return {"messages": []}
    data["messages"] = [m for m in data["messages"] if isinstance(m, dict) and m.get("id")]
    return data


def _save(data: dict):
    auth._save_json(MESSAGES_FILE, data)


class MessageReq(BaseModel):
    content: str
    pow: Optional[dict] = None


@router.get("")
def list_messages(username: str = Depends(auth.require_session)):
    """admin 看全部；普通用户只看自己发的。"""
    msgs = sorted(_load()["messages"], key=lambda m: m.get("created_at", ""), reverse=True)
    if auth.get_user_role(username) != "admin":
        msgs = [m for m in msgs if m.get("username") == username]
    return msgs


@router.post("")
def send_message(req: MessageReq, username: str = Depends(auth.require_session)):
    content = (req.content or "").strip()
    if not content:
        raise HTTPException(400, "消息内容不能为空")
    if len(content) > MAX_CONTENT_LEN:
        raise HTTPException(400, f"消息过长（≤{MAX_CONTENT_LEN} 字）")
    try:
        difficulty = pow.verify_pow(req.pow, content, scope="message", username=username)
    except pow.PowError as e:
        raise HTTPException(400, str(e))

    data = _load()
    # 重放去重：challenge 有效期内同用户同内容只受理一次
    cutoff = time.time() - pow.DEFAULT_TTL_SEC
    for m in data["messages"]:
        if m.get("username") != username or m.get("content") != content:
            continue
        try:
            ts = datetime.fromisoformat(m["created_at"].replace("Z", "+00:00")).timestamp()
        except Exception:
            continue
        if ts >= cutoff:
            raise HTTPException(400, "相同内容刚刚已发送过，请勿重复提交")
    msg = {
        "id": uuid.uuid4().hex[:12],
        "username": username,
        "content": content,
        "created_at": _now(),
        "pow_difficulty": difficulty,
    }
    data["messages"].append(msg)
    _save(data)
    return {"ok": True, "message": msg}


@router.delete("/{message_id}")
def delete_message(message_id: str, username: str = Depends(auth.require_admin)):
    data = _load()
    before = len(data["messages"])
    data["messages"] = [m for m in data["messages"] if m.get("id") != message_id]
    if len(data["messages"]) == before:
        raise HTTPException(404, "消息不存在")
    _save(data)
    return {"ok": True}
