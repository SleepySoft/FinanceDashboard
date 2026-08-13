"""回测系统 API 路由"""
from fastapi import APIRouter, HTTPException
from typing import Optional
import json
import os
import uuid
from datetime import datetime, timezone

from strategy.models import CreateStrategyReq, BacktestRunReq, BacktestFrameReq
from strategy.registry import get_registry
from backtest.engine import BacktestEngine, BacktestConfig
from backtest.data_provider import get_data_source
from backtest.cache import BacktestCache

router = APIRouter(prefix="/api/backtest", tags=["backtest"])

# 全局实例
cache = BacktestCache()

# ─── 策略管理 ────────────────────────────────────────

@router.get("/strategies")
def list_strategies():
    """列出所有策略（内置 + 自定义）"""
    registry = get_registry()
    return {"strategies": registry.list_all()}


@router.post("/strategies")
def create_strategy(req: CreateStrategyReq):
    """创建自定义策略"""
    registry = get_registry()
    strategy_id = req.name.lower().replace(' ', '_').replace('-', '_')

    # 检查是否已存在
    if registry.get(strategy_id):
        raise HTTPException(409, f"Strategy '{strategy_id}' already exists")

    # 保存策略源码
    registry.save_custom(strategy_id, req.source)

    # 保存元数据
    strategies_file = '/root/data/FinanceDashboard/data/_strategies.json'
    strategies = {}
    if os.path.exists(strategies_file):
        with open(strategies_file, 'r', encoding='utf-8') as f:
            strategies = json.load(f)

    strategies[strategy_id] = {
        'id': strategy_id,
        'name': req.name,
        'description': req.description,
        'notes': req.notes,
        'type': 'custom',
        'params': [p.dict() for p in req.params],
        'tags': req.tags,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'updated_at': datetime.now(timezone.utc).isoformat(),
    }

    with open(strategies_file, 'w', encoding='utf-8') as f:
        json.dump(strategies, f, ensure_ascii=False, indent=2)

    return {"id": strategy_id, "status": "created"}


@router.get("/strategies/{strategy_id}")
def get_strategy(strategy_id: str):
    """获取策略详情"""
    registry = get_registry()
    cls = registry.get(strategy_id)
    if not cls:
        raise HTTPException(404, "Strategy not found")

    instance = cls()
    info = instance.to_dict()
    info['id'] = strategy_id
    info['type'] = 'builtin' if registry._is_builtin(strategy_id) else 'custom'

    # 读取笔记
    strategies_file = '/root/data/FinanceDashboard/data/_strategies.json'
    if os.path.exists(strategies_file):
        with open(strategies_file, 'r', encoding='utf-8') as f:
            strategies = json.load(f)
        if strategy_id in strategies:
            info['notes'] = strategies[strategy_id].get('notes', '')

    return info


@router.put("/strategies/{strategy_id}")
def update_strategy(strategy_id: str, req: CreateStrategyReq):
    """更新自定义策略"""
    registry = get_registry()
    if registry._is_builtin(strategy_id):
        raise HTTPException(403, "Cannot modify built-in strategy")

    registry.save_custom(strategy_id, req.source)

    strategies_file = '/root/data/FinanceDashboard/data/_strategies.json'
    strategies = {}
    if os.path.exists(strategies_file):
        with open(strategies_file, 'r', encoding='utf-8') as f:
            strategies = json.load(f)

    strategies[strategy_id] = {
        'id': strategy_id,
        'name': req.name,
        'description': req.description,
        'notes': req.notes,
        'type': 'custom',
        'params': [p.dict() for p in req.params],
        'tags': req.tags,
        'updated_at': datetime.now(timezone.utc).isoformat(),
    }

    with open(strategies_file, 'w', encoding='utf-8') as f:
        json.dump(strategies, f, ensure_ascii=False, indent=2)

    return {"id": strategy_id, "status": "updated"}


@router.delete("/strategies/{strategy_id}")
def delete_strategy(strategy_id: str):
    """删除自定义策略"""
    registry = get_registry()
    if registry._is_builtin(strategy_id):
        raise HTTPException(403, "Cannot delete built-in strategy")

    registry.delete_custom(strategy_id)

    strategies_file = '/root/data/FinanceDashboard/data/_strategies.json'
    if os.path.exists(strategies_file):
        with open(strategies_file, 'r', encoding='utf-8') as f:
            strategies = json.load(f)
        strategies.pop(strategy_id, None)
        with open(strategies_file, 'w', encoding='utf-8') as f:
            json.dump(strategies, f, ensure_ascii=False, indent=2)

    return {"status": "deleted"}


@router.get("/strategies/{strategy_id}/source")
def get_strategy_source(strategy_id: str):
    """获取策略源码"""
    registry = get_registry()
    cls = registry.get(strategy_id)
    if not cls:
        raise HTTPException(404, "Strategy not found")

    try:
        source = cls().get_source_code()
    except Exception:
        source = ""

    return {"id": strategy_id, "source": source}


# ─── 回测执行 ────────────────────────────────────────

@router.post("/run")
def run_backtest(req: BacktestRunReq):
    """执行回测"""
    registry = get_registry()
    strategy_cls = registry.get(req.strategy_id)
    if not strategy_cls:
        raise HTTPException(404, f"Strategy '{req.strategy_id}' not found")

    # 构建配置
    config = BacktestConfig()
    if req.config:
        for k, v in req.config.items():
            if hasattr(config, k):
                setattr(config, k, v)

    # 检查缓存
    cache_key = None
    if req.use_cache:
        cached = cache.get(
            req.strategy_id, req.params,
            req.codes, req.start_date, req.end_date,
            req.config or {}
        )
        if cached:
            return {
                "id": f"bt_{uuid.uuid4().hex[:8]}",
                "status": "success",
                "from_cache": True,
                **cached
            }

    # 获取数据
    try:
        ds = get_data_source('tushare')
    except Exception as e:
        raise HTTPException(500, f"Data source init failed: {e}")

    # 执行回测
    engine = BacktestEngine(config)
    all_results = {}
    combined_trades = []
    combined_equity = None

    for code in req.codes:
        try:
            data = ds.get_daily_bars(code, req.start_date, req.end_date, req.adjust)
            if data.empty or len(data) < 30:
                all_results[code] = {"error": "Insufficient data (need >= 30 days)"}
                continue

            result = engine.run(strategy_cls, data, req.params)
            all_results[code] = {
                "metrics": result['metrics'],
                "trades": result['trades'],
                "trade_count": len(result['trades']),
            }
            combined_trades.extend(result['trades'])

            # 合并权益曲线（简单平均）
            if combined_equity is None:
                combined_equity = {e['date']: e['value'] for e in result['equity_curve']}
            else:
                for e in result['equity_curve']:
                    d = e['date']
                    if d in combined_equity:
                        combined_equity[d] = (combined_equity[d] + e['value']) / 2
        except Exception as e:
            all_results[code] = {"error": str(e)}

    # 计算汇总指标
    total_trades = len(combined_trades)
    win_trades = [t for t in combined_trades if t.get('pnl', 0) > 0]
    lose_trades = [t for t in combined_trades if t.get('pnl', 0) <= 0]

    summary = {
        "total_return": round(sum(r.get('metrics', {}).get('total_return', 0) for r in all_results.values() if 'metrics' in r) / max(len([r for r in all_results.values() if 'metrics' in r]), 1), 4),
        "total_trades": total_trades,
        "win_rate": round(len(win_trades) / total_trades, 4) if total_trades > 0 else 0,
        "profit_factor": round(sum(t.get('pnl', 0) for t in win_trades) / abs(sum(t.get('pnl', 0) for t in lose_trades)), 2) if lose_trades and sum(t.get('pnl', 0) for t in lose_trades) != 0 else float('inf'),
        "stocks_tested": len(req.codes),
        "stocks_success": len([r for r in all_results.values() if 'metrics' in r]),
    }

    equity_curve = sorted(
        [{'date': k, 'value': v} for k, v in (combined_equity or {}).items()],
        key=lambda x: x['date']
    )

    response = {
        "id": f"bt_{uuid.uuid4().hex[:8]}",
        "status": "success",
        "from_cache": False,
        "summary": summary,
        "results": all_results,
        "equity_curve": equity_curve,
        "trades": combined_trades[:100],  # 限制返回数量
    }

    # 写入缓存
    if req.use_cache:
        cache.set(
            response, req.strategy_id, req.params,
            req.codes, req.start_date, req.end_date,
            req.config or {}
        )

    # 保存回测记录
    record = {
        "id": response["id"],
        "strategy_id": req.strategy_id,
        "params": req.params,
        "codes": req.codes,
        "start_date": req.start_date,
        "end_date": req.end_date,
        "config": req.config,
        "summary": summary,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _save_backtest_record(record)

    return response


@router.post("/run/frame")
def run_frame_backtest(req: BacktestFrameReq):
    """执行逐帧回测"""
    registry = get_registry()
    strategy_cls = registry.get(req.strategy_id)
    if not strategy_cls:
        raise HTTPException(404, f"Strategy '{req.strategy_id}' not found")

    config = BacktestConfig()
    if req.config:
        for k, v in req.config.items():
            if hasattr(config, k):
                setattr(config, k, v)

    try:
        ds = get_data_source('tushare')
    except Exception as e:
        raise HTTPException(500, f"Data source init failed: {e}")

    data = ds.get_daily_bars(req.code, req.start_date, req.end_date, req.adjust)
    if data.empty or len(data) < 30:
        raise HTTPException(400, "Insufficient data (need >= 30 days)")

    engine = BacktestEngine(config)
    frames = engine.run_frames(strategy_cls, data, req.params)

    return {
        "id": f"btf_{uuid.uuid4().hex[:8]}",
        "code": req.code,
        "frame_count": len(frames),
        "frames": frames,
    }


# ─── 回测记录 ────────────────────────────────────────

@router.get("/records")
def list_records(limit: int = 50):
    """列出回测记录"""
    records_file = '/root/data/FinanceDashboard/data/_backtest_records.json'
    if not os.path.exists(records_file):
        return {"records": [], "count": 0}

    with open(records_file, 'r', encoding='utf-8') as f:
        records = json.load(f)

    # 按时间倒序
    records = sorted(records, key=lambda x: x.get('created_at', ''), reverse=True)
    return {"records": records[:limit], "count": len(records)}


@router.get("/records/{record_id}")
def get_record(record_id: str):
    """获取回测记录详情"""
    records_file = '/root/data/FinanceDashboard/data/_backtest_records.json'
    if not os.path.exists(records_file):
        raise HTTPException(404, "Record not found")

    with open(records_file, 'r', encoding='utf-8') as f:
        records = json.load(f)

    for r in records:
        if r.get('id') == record_id:
            return r

    raise HTTPException(404, "Record not found")


@router.delete("/records/{record_id}")
def delete_record(record_id: str):
    """删除回测记录"""
    records_file = '/root/data/FinanceDashboard/data/_backtest_records.json'
    if not os.path.exists(records_file):
        return {"status": "ok"}

    with open(records_file, 'r', encoding='utf-8') as f:
        records = json.load(f)

    records = [r for r in records if r.get('id') != record_id]

    with open(records_file, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    return {"status": "deleted"}


# ─── 辅助函数 ────────────────────────────────────────

def _save_backtest_record(record: dict):
    """保存回测记录到文件"""
    records_file = '/root/data/FinanceDashboard/data/_backtest_records.json'
    records = []
    if os.path.exists(records_file):
        with open(records_file, 'r', encoding='utf-8') as f:
            records = json.load(f)

    records.append(record)

    # 保留最近 200 条
    records = sorted(records, key=lambda x: x.get('created_at', ''), reverse=True)[:200]

    with open(records_file, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
