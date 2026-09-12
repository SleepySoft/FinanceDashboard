# -*- coding: utf-8 -*-
"""powbox FastAPI 路由：challenge 签发与当前难度查询。

挂载方式（本项目见 main.py）：
    from powbox import routes as powbox_routes
    powbox_routes.init(get_current_user_fn=..., prefix="/api/pow")
    app.include_router(powbox_routes.router)

get_current_user_fn(request) -> Optional[str]：返回当前登录用户名，None 表示未登录。
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from . import pow


_get_user_fn = None
_anonymous_identity_fn = None


def init(get_current_user_fn, anonymous_identity_fn=None):
    global _get_user_fn, _anonymous_identity_fn
    _get_user_fn = get_current_user_fn
    _anonymous_identity_fn = anonymous_identity_fn


router = APIRouter(tags=["pow"])


def _require_user(request: Request) -> str:
    user = _get_user_fn(request) if _get_user_fn else None
    if not user:
        raise HTTPException(401, "需要登录")
    return user


class ChallengeReq(BaseModel):
    scope: str


@router.post("/challenge")
def create_challenge(req: ChallengeReq, request: Request, response: Response):
    user = _get_user_fn(request) if _get_user_fn else None
    if not user and _anonymous_identity_fn:
        user = _anonymous_identity_fn(req.scope, request, response)
    if not user:
        raise HTTPException(401, "需要登录")
    scope = (req.scope or "").strip()
    if not scope or len(scope) > 32 or not scope.replace("_", "").replace("-", "").isalnum():
        raise HTTPException(400, "scope 非法")
    return pow.issue_challenge(scope, user)


@router.get("/config")
def get_config(request: Request):
    """当前最低难度与参考耗时，供 POW 面板展示。"""
    user = _get_user_fn(request) if _get_user_fn else None
    if not user and not _anonymous_identity_fn:
        raise HTTPException(401, "需要登录")
    d = pow.current_difficulty()
    return {
        "min_difficulty": d,
        "bounds": [pow.MIN_DIFFICULTY, pow.current_max_difficulty()],
        "expected_hashes": 2 ** d,
        "challenge_ttl_sec": pow.DEFAULT_TTL_SEC,
    }
