# -*- coding: utf-8 -*-
"""统一的 Tushare token 读取

优先级：环境变量 TUSHARE_TOKEN → data/_config.json 的 tushare_token → 项目 .env
"""
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
CONFIG_FILE = os.path.join(PROJECT_ROOT, "data", "_config.json")


def get_tushare_token() -> str:
    token = os.environ.get("TUSHARE_TOKEN", "").strip()
    if token:
        return token

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        token = str(cfg.get("tushare_token", "") or "").strip()
        if token:
            return token
    except Exception:
        pass

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
