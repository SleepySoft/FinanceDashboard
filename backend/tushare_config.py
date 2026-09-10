# -*- coding: utf-8 -*-
"""统一的 Tushare token 读取

优先级：环境变量 TUSHARE_TOKEN → data/_secrets.json → data/_config.json（旧版遗留）→ 项目 .env
"""
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
CONFIG_FILE = os.path.join(PROJECT_ROOT, "data", "_config.json")
SECRETS_FILE = os.path.join(PROJECT_ROOT, "data", "_secrets.json")


def _token_from_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        return str(cfg.get("tushare_token", "") or "").strip()
    except Exception:
        return ""


def _token_from_dotenv() -> str:
    for env_path in (
        os.path.join(PROJECT_ROOT, ".env"),
        os.path.join(BASE_DIR, ".env"),
    ):
        if os.path.exists(env_path):
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip().startswith("TUSHARE_TOKEN="):
                            return line.strip().split("=", 1)[1].strip()
            except Exception:
                pass
    return ""


def get_tushare_token() -> str:
    token = os.environ.get("TUSHARE_TOKEN", "").strip()
    if token:
        return token
    for path in (SECRETS_FILE, CONFIG_FILE):
        token = _token_from_file(path)
        if token:
            return token
    return _token_from_dotenv()


def get_tushare_token_source() -> str:
    """返回当前 token 的来源：env（环境变量）/ config（配置文件或 .env）/ none。"""
    if os.environ.get("TUSHARE_TOKEN", "").strip():
        return "env"
    for path in (SECRETS_FILE, CONFIG_FILE):
        if _token_from_file(path):
            return "config"
    if _token_from_dotenv():
        return "config"
    return "none"
