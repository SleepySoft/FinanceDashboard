# -*- coding: utf-8 -*-
"""powbox — Hashcash 风格的工作量证明（POW），纯 stdlib，无项目耦合。

协议：
1. 服务端签发自包含 HMAC 签名的 challenge（无状态）：
   fd1.<scope>.<username>.<expiry_ts>.<random_hex>.<hmac_hex>
2. 客户端求解：sha256(challenge + ":" + sha256_hex(content) + ":" + nonce)
   的前 D 个 bit 全为 0。POW 与提交内容绑定——一份证明只对那份内容有效。
3. 提交 pow = {challenge, nonce, difficulty}；difficulty 是客户端实际求解的难度，
   服务端要求 difficulty ≥ 当前最低配置，且哈希前 difficulty 个 bit 确实为 0
   （用户主动报高难度只会更难伪造，无需信任客户端声明之外的任何信息）。

防重放不依赖历史记录：challenge 有效期短（默认 10 分钟），且 POW 绑定内容，
重放只能原样重复同一内容；业务层做幂等/去重（投票 upsert、消息同内容去重）。

复用方式：调用 init(secret_fn=..., difficulty_fn=...) 注入站点密钥与难度来源即可。
"""
import hashlib
import hmac
import secrets
import time

VERSION = "fd1"
DEFAULT_TTL_SEC = 600  # 10 分钟
MIN_DIFFICULTY = 8
MAX_DIFFICULTY = 28
DEFAULT_DIFFICULTY = 20

_secret_fn = lambda: ""
_difficulty_fn = lambda: DEFAULT_DIFFICULTY


def init(secret_fn=None, difficulty_fn=None):
    """注入站点钩子。secret_fn() -> str：HMAC 密钥来源；difficulty_fn() -> int：最低难度。"""
    global _secret_fn, _difficulty_fn
    if secret_fn is not None:
        _secret_fn = secret_fn
    if difficulty_fn is not None:
        _difficulty_fn = difficulty_fn


def current_difficulty() -> int:
    try:
        d = int(_difficulty_fn())
    except Exception:
        d = DEFAULT_DIFFICULTY
    return max(MIN_DIFFICULTY, min(MAX_DIFFICULTY, d))


def content_digest(content: str) -> str:
    """提交内容的承诺值：业务层把待提交内容规范化后传入。"""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _sign(payload: str) -> str:
    return hmac.new(_secret_fn().encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def issue_challenge(scope: str, username: str, ttl_sec: int = DEFAULT_TTL_SEC) -> dict:
    """签发 challenge。返回的 difficulty 为当前最低要求（客户端可在此基础上自行提高）。"""
    expiry = int(time.time()) + ttl_sec
    payload = f"{VERSION}.{scope}.{username}.{expiry}.{secrets.token_hex(12)}"
    return {
        "challenge": f"{payload}.{_sign(payload)}",
        "min_difficulty": current_difficulty(),
        "expires_at": expiry,
        "ttl_sec": ttl_sec,
    }


class PowError(Exception):
    """校验失败；message 可直接返回给客户端。"""


def _parse(challenge: str):
    parts = challenge.split(".")
    if len(parts) != 6 or parts[0] != VERSION:
        raise PowError("challenge 格式非法")
    _, scope, username, expiry, _, sig = parts
    payload = ".".join(parts[:5])
    if not hmac.compare_digest(sig, _sign(payload)):
        raise PowError("challenge 签名无效")
    try:
        expiry_ts = int(expiry)
    except ValueError:
        raise PowError("challenge 格式非法")
    if expiry_ts < time.time():
        raise PowError("challenge 已过期，请重新计算")
    return scope, username


def count_leading_zero_bits(digest: bytes) -> int:
    n = 0
    for b in digest:
        if b == 0:
            n += 8
            continue
        n += 8 - b.bit_length()
        break
    return n


def verify_pow(pow_obj: dict, content: str, scope: str, username: str) -> int:
    """校验 POW，成功返回实际难度（可记录为可信度）；失败抛 PowError。"""
    if not isinstance(pow_obj, dict):
        raise PowError("缺少 POW")
    challenge = pow_obj.get("challenge")
    if not isinstance(challenge, str) or not challenge:
        raise PowError("缺少 POW challenge")
    try:
        nonce = int(pow_obj.get("nonce"))
        difficulty = int(pow_obj.get("difficulty"))
    except (TypeError, ValueError):
        raise PowError("POW 参数非法")
    if nonce < 0 or not (MIN_DIFFICULTY <= difficulty <= MAX_DIFFICULTY):
        raise PowError("POW 参数非法")

    ch_scope, ch_user = _parse(challenge)
    if ch_scope != scope:
        raise PowError("POW 用途不匹配")
    if ch_user != username:
        raise PowError("POW 与当前用户不匹配")
    if difficulty < current_difficulty():
        raise PowError(f"POW 难度不足：当前最低要求 {current_difficulty()} bit")

    material = f"{challenge}:{content_digest(content)}:{nonce}"
    digest = hashlib.sha256(material.encode("utf-8")).digest()
    if count_leading_zero_bits(digest) < difficulty:
        raise PowError("POW 校验失败：哈希不满足难度要求")
    return difficulty
