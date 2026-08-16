# -*- coding: utf-8 -*-
"""
FinanceDashboard 认证模块

- 用户与密码哈希：data/_users.json（PBKDF2-HMAC-SHA256 + 随机盐）
- 会话：data/_sessions.json + HttpOnly Cookie（fd_session）
- 配置：data/_config.json
  - allow_anonymous_read: false=未登录完全看不到任何数据；true=未登录只读
  - session_ttl_hours: 会话有效期（小时）
  - api_key: Agent 访问密钥（请求头 X-API-Key），未配置则 Agent 接口也需要登录

首次运行：自动创建管理员账号。
  - 用户名取环境变量 FD_ADMIN_USERNAME（默认 admin）
  - 密码取环境变量 FD_ADMIN_PASSWORD；未设置则使用默认密码
    SleepySoft@299792458（登录后建议在「设置」中尽快修改）
  - Agent 访问密钥：未设置 FD_API_KEY 且 _config.json 无 api_key 时，
    首次访问自动生成并保存到 data/_config.json（打印到启动日志）。
"""
import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from tushare_config import get_tushare_token_source

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(BASE_DIR), "data")
USERS_FILE = os.path.join(DATA_DIR, "_users.json")
SESSIONS_FILE = os.path.join(DATA_DIR, "_sessions.json")
CONFIG_FILE = os.path.join(DATA_DIR, "_config.json")
# Agent 访问密钥落盘位置：项目根目录（本地 Agent 直接读取，不通过接口返回明文）
AGENT_TOKEN_FILE = os.path.join(os.path.dirname(BASE_DIR), "agent_token.txt")

SESSION_COOKIE = "fd_session"
API_KEY_HEADER = "x-api-key"
PBKDF2_ITERATIONS = 200_000
MIN_PASSWORD_LEN = 6
DEFAULT_ADMIN_PASSWORD = "SleepySoft@299792458"

DEFAULT_CONFIG = {
    "allow_anonymous_read": False,
    "session_ttl_hours": 24 * 7,
    "api_key": "",
    "tushare_token": "",
    "price_refresh_interval_min": 5,
    "anomaly_scan_interval_min": 0,
}

os.makedirs(DATA_DIR, exist_ok=True)


# ---------- 基础读写 ----------

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _load_json(path: str, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save_json(path: str, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---------- 密码 ----------

def _new_salt() -> str:
    return secrets.token_hex(16)


def _hash_password(password: str, salt: str) -> str:
    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), PBKDF2_ITERATIONS
    )
    return dk.hex()


def _verify_password(password: str, salt: str, expected_hash: str) -> bool:
    return hmac.compare_digest(_hash_password(password, salt), expected_hash)


# ---------- 用户 ----------

def _load_users() -> dict:
    users = _load_json(USERS_FILE, {"users": []})
    if not isinstance(users, dict) or not isinstance(users.get("users"), list):
        users = {"users": []}
    return users


def _save_users(users: dict):
    _save_json(USERS_FILE, users)


def _ensure_admin_user() -> dict:
    """首次运行时创建管理员账号。返回用户列表。"""
    users = _load_users()
    if users["users"]:
        return users

    username = os.environ.get("FD_ADMIN_USERNAME", "admin").strip() or "admin"
    password = os.environ.get("FD_ADMIN_PASSWORD", "") or DEFAULT_ADMIN_PASSWORD

    salt = _new_salt()
    user = {
        "username": username,
        "salt": salt,
        "password_hash": _hash_password(password, salt),
        "created_at": _now().isoformat(),
    }
    users["users"].append(user)
    _save_users(users)
    print(f"[auth] 首次运行：已创建管理员账号「{username}」")
    print(f"[auth] 初始密码：{password}（请登录后在「设置-修改密码」中尽快更换）")
    return users


# ---------- 配置 ----------

def load_config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    data = _load_json(CONFIG_FILE, None)
    if isinstance(data, dict):
        cfg.update(data)
    # 环境变量优先：FD_API_KEY 用于 Agent 访问
    env_key = os.environ.get("FD_API_KEY", "")
    if env_key:
        cfg["api_key"] = env_key
    return cfg


def save_config(cfg: dict):
    _save_json(CONFIG_FILE, cfg)


def _ensure_api_key():
    """首次运行时自动生成 Agent 访问密钥（未配置 FD_API_KEY / api_key 时）。"""
    if os.environ.get("FD_API_KEY", ""):
        return
    cfg = load_config()
    if cfg.get("api_key"):
        return
    cfg["api_key"] = secrets.token_urlsafe(24)
    save_config(cfg)
    _write_agent_token(cfg["api_key"])
    print(f"[auth] 已生成 Agent 访问密钥：{cfg['api_key']}")
    print(f"[auth] 已写入本地文件供 Agent 使用：{AGENT_TOKEN_FILE}")


def _write_agent_token(token: str) -> bool:
    """将 token 写入项目根目录 agent_token.txt，供本机 Agent 读取。
    该文件不通过任何 API 暴露，非本机无法读取。"""
    try:
        with open(AGENT_TOKEN_FILE, "w", encoding="utf-8") as f:
            f.write(token + "\n")
        if os.name == "posix":
            try:
                os.chmod(AGENT_TOKEN_FILE, 0o600)
            except Exception:
                pass
        return True
    except Exception as e:
        print(f"[auth] 写入 token 文件失败：{e}")
        return False


# ---------- 会话 ----------

def _load_sessions() -> dict:
    sessions = _load_json(SESSIONS_FILE, {})
    if not isinstance(sessions, dict):
        sessions = {}
    return sessions


def _save_sessions(sessions: dict):
    _save_json(SESSIONS_FILE, sessions)


def _purge_expired(sessions: dict):
    now = _now()
    for token in list(sessions):
        expires = sessions[token].get("expires_at")
        try:
            if datetime.fromisoformat(expires) <= now:
                del sessions[token]
        except Exception:
            del sessions[token]


def _create_session(username: str, ttl_hours: float) -> str:
    token = secrets.token_urlsafe(32)
    sessions = _load_sessions()
    _purge_expired(sessions)
    sessions[token] = {
        "username": username,
        "created_at": _now().isoformat(),
        "expires_at": (_now() + timedelta(hours=ttl_hours)).isoformat(),
    }
    _save_sessions(sessions)
    return token


def _revoke_other_sessions(username: str, keep_token: Optional[str]):
    sessions = _load_sessions()
    for token in list(sessions):
        if sessions[token].get("username") == username and token != keep_token:
            del sessions[token]
    _save_sessions(sessions)


# ---------- 认证判定 ----------

def _api_key_valid(request: Request) -> bool:
    key = request.headers.get(API_KEY_HEADER, "")
    if not key:
        return False
    expected = load_config().get("api_key", "")
    return bool(expected) and hmac.compare_digest(key, expected)


def get_session_user(request: Request) -> Optional[str]:
    """仅凭 Cookie 会话识别用户（用于 /api/auth/* 自身接口）。"""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    sessions = _load_sessions()
    sess = sessions.get(token)
    if not sess:
        return None
    try:
        expires = datetime.fromisoformat(sess["expires_at"])
    except Exception:
        return None
    if expires <= _now():
        del sessions[token]
        _save_sessions(sessions)
        return None
    return sess.get("username")


def get_current_user(request: Request) -> Optional[str]:
    """全局身份：Cookie 会话或 X-API-Key。Agent 使用 API Key 视为已认证。"""
    user = get_session_user(request)
    if user:
        return user
    if _api_key_valid(request):
        return "_agent"
    return None


def require_session(request: Request) -> str:
    user = get_session_user(request)
    if not user:
        raise HTTPException(401, "需要登录")
    return user


# ---------- API ----------

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginReq(BaseModel):
    username: str
    password: str


class ChangePasswordReq(BaseModel):
    old_password: str
    new_password: str


class ConfigUpdateReq(BaseModel):
    allow_anonymous_read: Optional[bool] = None
    session_ttl_hours: Optional[int] = None
    tushare_token: Optional[str] = None
    price_refresh_interval_min: Optional[int] = None
    anomaly_scan_interval_min: Optional[int] = None


def _config_payload(cfg: dict) -> dict:
    """对外暴露的配置视图（不含敏感明文 token）。"""
    token_source = get_tushare_token_source()
    return {
        "initialized": True,
        "allow_anonymous_read": cfg.get("allow_anonymous_read", False),
        "session_ttl_hours": cfg.get("session_ttl_hours", DEFAULT_CONFIG["session_ttl_hours"]),
        "api_key_configured": bool(cfg.get("api_key")),
        "tushare_token_configured": token_source != "none",
        "tushare_token_source": token_source,
        "price_refresh_interval_min": int(
            cfg.get("price_refresh_interval_min", DEFAULT_CONFIG["price_refresh_interval_min"]) or 0
        ),
        "anomaly_scan_interval_min": int(
            cfg.get("anomaly_scan_interval_min", DEFAULT_CONFIG["anomaly_scan_interval_min"]) or 0
        ),
    }


@router.get("/config")
def get_config(request: Request):
    """公开配置：登录页/前端引导依赖它判断是否需要登录。"""
    _ensure_admin_user()
    _ensure_api_key()
    cfg = load_config()
    return _config_payload(cfg)


@router.get("/me")
def me(request: Request):
    user = get_session_user(request)
    return {"authenticated": user is not None, "user": user}


@router.post("/login")
def login(req: LoginReq, response: Response):
    _ensure_admin_user()
    users = _load_users()
    user = next((u for u in users["users"] if u["username"] == req.username), None)
    if not user or not _verify_password(req.password, user["salt"], user["password_hash"]):
        raise HTTPException(401, "用户名或密码错误")

    cfg = load_config()
    ttl_hours = cfg.get("session_ttl_hours") or DEFAULT_CONFIG["session_ttl_hours"]
    token = _create_session(user["username"], ttl_hours)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(ttl_hours * 3600),
        httponly=True,
        samesite="lax",
        secure=os.environ.get("FD_COOKIE_SECURE", "").lower() in ("1", "true", "yes"),
        path="/",
    )
    return {"ok": True, "username": user["username"]}


@router.post("/logout")
def logout(request: Request, response: Response):
    """幂等登出：无需登录态。"""
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        sessions = _load_sessions()
        sessions.pop(token, None)
        _save_sessions(sessions)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@router.post("/change-password")
def change_password(req: ChangePasswordReq, request: Request, username: str = Depends(require_session)):
    users = _load_users()
    user = next((u for u in users["users"] if u["username"] == username), None)
    if not user:
        raise HTTPException(404, "用户不存在")
    if not _verify_password(req.old_password, user["salt"], user["password_hash"]):
        raise HTTPException(400, "原密码错误")
    if len(req.new_password) < MIN_PASSWORD_LEN:
        raise HTTPException(400, f"新密码至少 {MIN_PASSWORD_LEN} 位")
    if req.new_password == req.old_password:
        raise HTTPException(400, "新密码不能与原密码相同")

    user["salt"] = _new_salt()
    user["password_hash"] = _hash_password(req.new_password, user["salt"])
    user["password_changed_at"] = _now().isoformat()
    users.pop("initial_password", None)
    _save_users(users)
    # 修改密码后吊销该用户其他会话，仅保留当前会话
    _revoke_other_sessions(username, keep_token=request.cookies.get(SESSION_COOKIE))
    return {"ok": True}


@router.patch("/config")
def update_config(req: ConfigUpdateReq, username: str = Depends(require_session)):
    cfg = load_config()
    if req.allow_anonymous_read is not None:
        cfg["allow_anonymous_read"] = bool(req.allow_anonymous_read)
    if req.session_ttl_hours is not None:
        if not (1 <= req.session_ttl_hours <= 24 * 30):
            raise HTTPException(400, "session_ttl_hours 需在 1~720 之间")
        cfg["session_ttl_hours"] = req.session_ttl_hours
    if req.tushare_token is not None:
        cfg["tushare_token"] = req.tushare_token.strip()
    if req.price_refresh_interval_min is not None:
        if not (0 <= req.price_refresh_interval_min <= 1440):
            raise HTTPException(400, "price_refresh_interval_min 需在 0~1440 之间")
        cfg["price_refresh_interval_min"] = req.price_refresh_interval_min
    if req.anomaly_scan_interval_min is not None:
        if not (0 <= req.anomaly_scan_interval_min <= 1440):
            raise HTTPException(400, "anomaly_scan_interval_min 需在 0~1440 之间")
        cfg["anomaly_scan_interval_min"] = req.anomaly_scan_interval_min
    save_config(cfg)
    return _config_payload(cfg)


@router.post("/token/regenerate")
def regenerate_token(username: str = Depends(require_session)):
    """重新生成 Agent 访问密钥（旧密钥立即失效）。
    密钥只写入项目根目录 agent_token.txt，不通过接口返回明文，避免远程暴露。"""
    if os.environ.get("FD_API_KEY", ""):
        raise HTTPException(
            400,
            "当前通过环境变量 FD_API_KEY 配置密钥，请直接修改环境变量；或移除该变量后使用此功能",
        )
    token = secrets.token_urlsafe(24)
    cfg = load_config()
    cfg["api_key"] = token
    save_config(cfg)
    if not _write_agent_token(token):
        raise HTTPException(500, "Token 已更新，但写入项目根目录 agent_token.txt 失败，请检查目录权限")
    return {
        "ok": True,
        "path": AGENT_TOKEN_FILE,
        "message": f"已生成并保存到 {AGENT_TOKEN_FILE}，仅供本机 Agent 读取",
    }
