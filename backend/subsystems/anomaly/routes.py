"""异动检测子系统 API 路由"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from dataclasses import asdict
import os
import json

from .core import (
    run_daily_scan, load_anomalies, save_anomalies,
    get_all_dates, get_daily_anomalies, aggregate_weekly,
    AnomalyDetector, TushareClient,
    ANOMALY_FILE, REPORTS_DIR,
)

router = APIRouter(prefix="/api/anomalies", tags=["anomaly"])


class AnomalyScanReq(BaseModel):
    date: Optional[str] = None
    sample_size: Optional[int] = None
    min_score: Optional[int] = 60


@router.get("/dates")
def list_anomaly_dates():
    """获取所有有异动记录的日期"""
    dates = get_all_dates()
    return {"dates": dates, "count": len(dates)}


@router.get("/{date}")
def get_anomalies_by_date(date: str):
    """获取指定日期的异动详情。支持特殊值 'latest'"""
    if date == "latest":
        if not os.path.exists(ANOMALY_FILE):
            return {"date": None, "stocks": [], "sectors": []}
        with open(ANOMALY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        daily = data.get("daily", {})
        for d in sorted(daily.keys(), reverse=True):
            record = daily[d]
            stocks = record.get("stocks", [])
            sectors = record.get("sectors", [])
            if stocks or sectors:
                return {"date": d, "stocks": stocks, "sectors": sectors}
        return {"date": None, "stocks": [], "sectors": []}

    data = get_daily_anomalies(date)
    return data


@router.get("/weekly/{date}")
def get_weekly_anomalies(date: str):
    """获取指定日期所在周的异动汇总"""
    weekly = aggregate_weekly(date)
    return weekly


@router.post("/scan")
def trigger_anomaly_scan(req: AnomalyScanReq = AnomalyScanReq()):
    """手动触发异动扫描"""
    try:
        result = run_daily_scan(
            trade_date=req.date,
            sample_size=req.sample_size
        )
        return result
    except Exception as e:
        raise HTTPException(500, f"Scan failed: {str(e)}")


@router.get("/latest")
def get_latest_anomalies():
    """获取最新有数据的异动"""
    if not os.path.exists(ANOMALY_FILE):
        return {"date": None, "stocks": [], "sectors": []}
    with open(ANOMALY_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    daily = data.get("daily", {})
    dates = sorted(daily.keys(), reverse=True)
    for d in dates:
        record = daily[d]
        stocks = record.get("stocks", [])
        sectors = record.get("sectors", [])
        if stocks or sectors:
            return {"date": d, "stocks": stocks, "sectors": sectors}
    return {"date": None, "stocks": [], "sectors": []}


@router.post("/{code}/add-to-dashboard")
def add_anomaly_to_dashboard(code: str):
    """将异动股票加入主看板（创建stock目录）"""
    code = code.upper().strip()

    # 项目数据目录
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '..', '..', 'data')
    stock_dir = os.path.join(data_dir, code)
    meta_file = os.path.join(stock_dir, "meta.json")

    # 检查是否已存在
    if os.path.exists(meta_file):
        return {"status": "exists", "message": f"{code} already in dashboard"}

    # 获取股票信息
    client = TushareClient()
    df = client.get_stock_basic()
    name = code
    sector = ""
    if df is not None:
        row = df[df["ts_code"] == code]
        if not row.empty:
            name = row.iloc[0].get("name", code)
            sector = row.iloc[0].get("industry", "")

    # 创建目录和 meta.json
    os.makedirs(stock_dir, exist_ok=True)
    os.makedirs(os.path.join(stock_dir, "reports"), exist_ok=True)
    meta = {
        "code": code,
        "name": name,
        "sector": sector,
        "added_at": datetime.now(timezone.utc).isoformat(),
        "status": "tracking",
    }
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    return {
        "status": "ok",
        "code": code,
        "name": name,
        "sector": sector,
        "message": f"Added {name}({code}) to dashboard"
    }


# ═══════════════════════════════════════════════════════
#  Plugin Management (插件管理)
# ═══════════════════════════════════════════════════════

@router.get("/plugins")
def list_plugins():
    """列出所有可用的异动检测插件"""
    from .plugins import DEFAULT_STOCK_PLUGINS, DEFAULT_SECTOR_PLUGINS

    def describe(cls):
        inst = cls()
        return {
            "name": inst.name,
            "description": inst.description,
            "version": getattr(inst, "version", "1.0"),
            "class": cls.__name__,
        }

    return {
        "stock_plugins": [describe(c) for c in DEFAULT_STOCK_PLUGINS],
        "sector_plugins": [describe(c) for c in DEFAULT_SECTOR_PLUGINS],
    }


@router.post("/scan/with-plugins")
def trigger_scan_with_plugins(req: dict):
    """
    使用指定插件组合执行扫描

    Request:
    {
        "date": "2024-01-15",
        "codes": ["000001.SZ"],
        "plugins": ["amplitude", "volume", "breakout"],
        "plugin_config": {
            "amplitude": {"threshold": 4.0},
            "volume": {"threshold": 1.5}
        }
    }
    """
    from .registry import PluginRegistry
    from .orchestrator import AnomalyOrchestrator
    from .plugins import (
        AmplitudeDetector, ChangeDetector, VolumeDetector,
        BreakoutDetector, MomentumDetector, SectorMomentumDetector,
    )

    date = req.get("date")
    codes = req.get("codes")
    plugin_names = req.get("plugins", [])
    plugin_config = req.get("plugin_config", {})

    # 插件名称到类的映射
    PLUGIN_MAP = {
        "amplitude": AmplitudeDetector,
        "change": ChangeDetector,
        "volume": VolumeDetector,
        "breakout": BreakoutDetector,
        "momentum": MomentumDetector,
        "sector_momentum": SectorMomentumDetector,
    }

    registry = PluginRegistry()
    # 注册指定的个股插件
    for name in plugin_names:
        if name in PLUGIN_MAP:
            registry.register(PLUGIN_MAP[name], config=plugin_config.get(name, {}))
    # 如果指定了板块插件或没指定任何插件，注册默认板块插件
    if "sector_momentum" in plugin_names or not any(p in PLUGIN_MAP for p in plugin_names if PLUGIN_MAP[p] == SectorMomentumDetector):
        registry.register(SectorMomentumDetector)

    if not registry.stock_plugins:
        return {"error": "No valid plugins specified"}

    orch = AnomalyOrchestrator(registry=registry)
    result = orch.scan(trade_date=date, codes=codes)

    return {
        "plugins_used": [p.name for p in registry.stock_plugins],
        "stock_anomalies": [asdict(s) for s in result.stock_anomalies],
        "sector_anomalies": [asdict(s) for s in result.sector_anomalies],
        "stock_count": len(result.stock_anomalies),
        "sector_count": len(result.sector_anomalies),
    }
