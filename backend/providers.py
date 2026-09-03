# -*- coding: utf-8 -*-
"""交易数据网站跳转（文件驱动）

配置保存在 data/_providers.json，编辑文件即可增删网站或改 URL 模板；
支持 {symbol_*} 占位符，由后端根据股票代码自动推导。
"""
import json
import os
import re
import urllib.parse
from typing import Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(BASE_DIR), "data")
PROVIDERS_FILE = os.path.join(DATA_DIR, "_providers.json")

DEFAULT_PROVIDERS = [
    {
        "id": "eastmoney",
        "name": "东方财富",
        "icon": "📈",
        "links": {"quote": "https://quote.eastmoney.com/{symbol_eastmoney}.html"},
    },
    {
        "id": "sina",
        "name": "新浪财经",
        "icon": "📰",
        "links": {"quote": "https://finance.sina.com.cn/realstock/company/{symbol_sina}/nc.shtml"},
    },
    {
        "id": "xueqiu",
        "name": "雪球",
        "icon": "⛄",
        "links": {"quote": "https://xueqiu.com/S/{symbol_xueqiu}"},
    },
    {
        "id": "10jqka",
        "name": "同花顺",
        "icon": "🌸",
        "links": {"quote": "https://stockpage.10jqka.com.cn/{symbol_10jqka}/"},
    },
    {
        "id": "futu",
        "name": "富途牛牛",
        "icon": "🐂",
        "links": {"quote": "https://www.futunn.com/stock/{symbol_futu}"},
    },
    {
        "id": "tradingview",
        "name": "TradingView",
        "icon": "📊",
        "links": {
            "chart": "https://www.tradingview.com/chart/?symbol={symbol_escaped}",
            "symbol_page": "https://www.tradingview.com/symbols/{symbol_dash}/",
        },
    },
    {
        "id": "yahoo",
        "name": "Yahoo Finance",
        "icon": "💼",
        "links": {"quote": "https://finance.yahoo.com/quote/{symbol_yahoo}"},
    },
    {
        "id": "google",
        "name": "Google Finance",
        "icon": "🔍",
        "links": {"quote": "https://www.google.com/finance/quote/{symbol_google}"},
    },
]

DEFAULT_CONFIG = {"default_provider": "xueqiu", "providers": DEFAULT_PROVIDERS}

router = APIRouter(prefix="/api/providers", tags=["providers"])


def load_providers() -> dict:
    if os.path.exists(PROVIDERS_FILE):
        try:
            with open(PROVIDERS_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            if not isinstance(cfg, dict):
                raise TypeError("root must be an object")
            providers = []
            for provider in cfg.get("providers", []):
                if not isinstance(provider, dict) or not isinstance(provider.get("id"), str):
                    continue
                links = provider.get("links")
                if not isinstance(links, dict):
                    continue
                provider = {**provider, "links": {key: value for key, value in links.items() if isinstance(key, str) and isinstance(value, str)}}
                providers.append(provider)
            if providers:
                return {**cfg, "providers": providers}
        except Exception as exc:
            print(f"[data-guard] 读取 {PROVIDERS_FILE} 失败: {type(exc).__name__}: {exc}")
    save_providers(DEFAULT_CONFIG)
    return json.loads(json.dumps(DEFAULT_CONFIG))


def save_providers(cfg: dict):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = PROVIDERS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, PROVIDERS_FILE)


def symbol_vars(code: str) -> Dict[str, str]:
    """把股票代码（如 600519.SH / 002430.SZ / 00700.HK）转成各网站需要的 symbol 变体。"""
    raw = code.strip().upper()
    if "." in raw:
        num, suffix = raw.rsplit(".", 1)
    else:
        num, suffix = raw, "US"
    exch_map = {"SH": "SSE", "SZ": "SZSE", "BJ": "BJSE", "HK": "HKEX", "US": "NASDAQ"}
    exch = exch_map.get(suffix, suffix)
    symbol = f"{exch}:{num}"
    vars_ = {
        "symbol": symbol,
        "symbol_escaped": urllib.parse.quote(symbol, safe=""),
        "symbol_dash": symbol.replace(":", "-"),
        "symbol_lower": symbol.lower(),
        "symbol_upper": num.upper(),
    }
    if exch == "SSE":
        vars_["symbol_sina"] = "sh" + num
        vars_["symbol_eastmoney"] = "sh" + num
        vars_["symbol_xueqiu"] = "SH" + num
        vars_["symbol_10jqka"] = num
        vars_["symbol_yahoo"] = num + ".SS"
        vars_["symbol_google"] = num + ":SHA"
    elif exch == "SZSE":
        vars_["symbol_sina"] = "sz" + num
        vars_["symbol_eastmoney"] = "sz" + num
        vars_["symbol_xueqiu"] = "SZ" + num
        vars_["symbol_10jqka"] = num
        vars_["symbol_yahoo"] = num + ".SZ"
        vars_["symbol_google"] = num + ":SHE"
    elif exch == "BJSE":
        vars_["symbol_eastmoney"] = "bj" + num
        vars_["symbol_xueqiu"] = "BJ" + num
    elif exch == "HKEX":
        hk = num.zfill(5)
        vars_["symbol_eastmoney"] = "hk" + hk
        vars_["symbol_xueqiu"] = hk
        vars_["symbol_futu"] = hk + "-HK"
        vars_["symbol_yahoo"] = hk + ".HK"
        vars_["symbol_google"] = hk + ":HKG"
    elif exch in ("NASDAQ", "NYSE", "AMEX"):
        vars_["symbol_eastmoney"] = num.lower()
        vars_["symbol_futu"] = num + "-US"
        vars_["symbol_yahoo"] = num
        vars_["symbol_google"] = num + ":" + exch
    return vars_


def _placeholders(template: str) -> set:
    return set(re.findall(r"\{(\w+)\}", template))


def render_links(providers: List[dict], vars_: dict) -> list:
    links = []
    for p in providers:
        if not isinstance(p.get("links"), dict):
            continue
        for kind, tmpl in p["links"].items():
            # 模板需要的占位符在当前代码下不适用（如美股用不到 sh/sz）就跳过
            if not _placeholders(tmpl).issubset(vars_):
                continue
            links.append({
                "id": p["id"],
                "name": p.get("name", p["id"]),
                "icon": p.get("icon", ""),
                "kind": kind,
                "url": tmpl.format_map(vars_),
            })
    return links


@router.get("")
def list_providers():
    cfg = load_providers()
    providers = cfg.get("providers", [])
    default_id = cfg.get("default_provider")
    if default_id not in [p.get("id") for p in providers]:
        default_id = providers[0]["id"] if providers else None
    return {
        "default_provider": default_id,
        "providers": [
            {"id": p["id"], "name": p.get("name", p["id"]), "icon": p.get("icon", "")}
            for p in providers
        ],
    }


@router.get("/links/{code}")
def get_provider_links(code: str):
    cfg = load_providers()
    links = render_links(cfg.get("providers", []), symbol_vars(code))
    ids = [l["id"] for l in links]
    default_id = cfg.get("default_provider")
    if default_id not in ids:
        default_id = ids[0] if ids else None
    return {"code": code, "default_provider": default_id, "links": links}


class SetDefaultReq(BaseModel):
    provider: str


@router.patch("/default")
def set_default_provider(req: SetDefaultReq):
    cfg = load_providers()
    ids = [p.get("id") for p in cfg.get("providers", [])]
    if req.provider not in ids:
        raise HTTPException(400, f"Unknown provider: {req.provider}")
    cfg["default_provider"] = req.provider
    save_providers(cfg)
    return {"ok": True, "default_provider": req.provider}
