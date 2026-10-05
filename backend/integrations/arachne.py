"""FinanceDashboard bridge to the independently deployed Arachne service."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

from fastapi import APIRouter, HTTPException, Request, Response

import auth


router = APIRouter(prefix="/api/integrations/arachne", tags=["integrations"])


@router.get("/auth-scope")
def auth_scope(request: Request, response: Response):
    """Translate a FinanceDashboard login session into Arachne's scope model."""
    username = auth.get_session_user(request)
    scope = "read_write" if username else "read_only"
    response.headers["X-Arachne-Scope"] = scope
    return {"scope": scope, "authenticated": username is not None}


def _api_base() -> str:
    return os.getenv("ARACHNE_API_URL", "http://127.0.0.1:16060/api/v1").rstrip("/")


def _public_base() -> str:
    return os.getenv("ARACHNE_PUBLIC_BASE", "/arachne").rstrip("/")


def _timeout_seconds() -> float:
    try:
        return max(0.5, float(os.getenv("ARACHNE_TIMEOUT_SECONDS", "3")))
    except ValueError:
        return 3.0


def _normalize_stock_code(code: str) -> str:
    return re.sub(r"\s+", "", code).upper()


def _build_embed_url(company_id: str, company_name: str) -> str:
    query = urllib.parse.urlencode(
        {
            "seed": company_id,
            "engine": "arachne_flow",
            "task_type": "cross_graph_context",
            "scope": "factual_node",
            "title": company_name,
        }
    )
    return f"{_public_base()}/embed.html?{query}"


def _request_company(stock_code: str, company_name: str | None = None) -> dict | None:
    params = {"stock_code": stock_code}
    if company_name and company_name.strip():
        params["company_name"] = company_name.strip()
    query = urllib.parse.urlencode(params)
    url = f"{_api_base()}/companies/resolve/by-stock-code?{query}"
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=_timeout_seconds()) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        if exc.code == 409:
            raise HTTPException(status_code=409, detail="Arachne 中该证券代码对应多家公司") from exc
        raise HTTPException(status_code=502, detail=f"Arachne 返回 HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise HTTPException(status_code=503, detail="Arachne 服务暂不可用") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=502, detail="Arachne 返回了无效数据") from exc

    if not isinstance(payload, dict) or not payload.get("company_id"):
        raise HTTPException(status_code=502, detail="Arachne 公司响应缺少 company_id")
    return payload


@router.get("/stocks/{code}")
def resolve_stock(code: str, name: str | None = None):
    """Resolve a FinanceDashboard stock to an Arachne company and embed URL."""
    stock_code = _normalize_stock_code(code)
    company = _request_company(stock_code, name)
    if company is None:
        return {"available": True, "matched": False, "stock_code": stock_code}

    company_name = company.get("name_zh") or company.get("name_en") or company["company_id"]
    return {
        "available": True,
        "matched": True,
        "stock_code": stock_code,
        "company": company,
        "embed_url": _build_embed_url(company["company_id"], company_name),
    }
