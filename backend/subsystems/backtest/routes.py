"""回测系统 API 路由"""
from fastapi import APIRouter, HTTPException
from typing import Optional
import json
import os
import uuid
import pandas as pd
from datetime import datetime, timezone

from .strategy.models import CreateStrategyReq, BacktestRunReq, BacktestFrameReq
from .strategy.registry import get_registry
from .backtest.engine import BacktestEngine, BacktestConfig
from .backtest.data_provider import get_data_source
from .backtest.cache import BacktestCache
from .backtest.factors import FactorEngine, BUILTIN_FACTORS
from .backtest.factor_backtest import FactorBacktestRunner, Condition

router = APIRouter(prefix="/api/backtest", tags=["backtest"])

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
STRATEGIES_FILE = os.path.join(DATA_DIR, "_strategies.json")
RECORDS_FILE = os.path.join(DATA_DIR, "_backtest_records.json")


def _safe_json_load(path: str, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, type(default)):
            raise TypeError(f"expected {type(default).__name__}")
        return data
    except Exception as exc:
        print(f"[data-guard] 读取 {path} 失败: {type(exc).__name__}: {exc}")
        return default


def _atomic_json_dump(path: str, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

# 全局实例
cache = BacktestCache()

# ─── 因子系统 ──────────────────────────────────────

@router.get("/factors")
def list_factors():
    """列出所有可用因子"""
    return {
        "factors": [{
            'id': f.id,
            'name': f.name,
            'category': f.category,
            'params': f.params,
            'description': f.description,
        } for f in BUILTIN_FACTORS]
    }


@router.post("/factors/compute")
def compute_factor(req: dict):
    """计算单个因子"""
    code = req.get('code', '').upper().strip()
    factor_id = req.get('factor_id', '')
    params = req.get('params', {})
    start = req.get('start_date', '2023-01-01')
    end = req.get('end_date', '2024-12-31')
    adjust = req.get('adjust', 'qfq')

    if not code or not factor_id:
        raise HTTPException(400, "code and factor_id required")

    try:
        ds = get_data_source('tushare')
        engine = FactorEngine(ds)
        series = engine.compute(code, factor_id, params, start, end, adjust)

        return {
            "code": code,
            "factor_id": factor_id,
            "values": [
                {"date": str(idx)[:10], "value": round(float(v), 4) if pd.notna(v) else None}
                for idx, v in series.items()
            ]
        }
    except Exception as e:
        raise HTTPException(500, f"Factor compute failed: {e}")


@router.post("/factor-run")
def run_factor_backtest(req: dict):
    """
    基于因子条件的简单回测

    Request:
    {
        "codes": ["000001.SZ"],
        "buy_conditions": [{"factor_id": "rsi", "params": {"period": 14}, "operator": "<", "value": 30}],
        "sell_conditions": [{"factor_id": "rsi", "params": {"period": 14}, "operator": ">", "value": 70}],
        "start_date": "2023-01-01",
        "end_date": "2024-12-31",
        "adjust": "qfq",
        "logic": "and",
        "config": {"initial_cash": 100000, "commission": 0.00025, "size": 0.2}
    }
    """
    codes = req.get('codes', [])
    buy_conds_raw = req.get('buy_conditions', [])
    sell_conds_raw = req.get('sell_conditions', [])
    start = req.get('start_date', '2023-01-01')
    end = req.get('end_date', '2024-12-31')
    adjust = req.get('adjust', 'qfq')
    logic = req.get('logic', 'and')
    config_raw = req.get('config', {})

    if not codes:
        raise HTTPException(400, "codes required")
    if not buy_conds_raw and not sell_conds_raw:
        raise HTTPException(400, "At least one buy or sell condition required")

    # 构建 Condition 对象
    buy_conditions = [Condition.from_dict(c) for c in buy_conds_raw]
    sell_conditions = [Condition.from_dict(c) for c in sell_conds_raw]

    config = BacktestConfig()
    for k, v in config_raw.items():
        if hasattr(config, k):
            setattr(config, k, v)

    try:
        ds = get_data_source('tushare')
        factor_engine = FactorEngine(ds)
        runner = FactorBacktestRunner(factor_engine)

        all_results = {}
        combined_trades = []
        combined_equity = None

        for code in codes:
            result = runner.run(
                code, buy_conditions, sell_conditions,
                start, end, adjust, config, logic
            )
            if 'error' in result:
                all_results[code] = result
                continue

            all_results[code] = {
                'metrics': result['metrics'],
                'trades': result['trades'],
                'trade_count': len(result['trades']),
            }
            combined_trades.extend(result['trades'])

            if combined_equity is None:
                combined_equity = {e['date']: e['value'] for e in result['equity_curve']}
            else:
                for e in result['equity_curve']:
                    d = e['date']
                    if d in combined_equity:
                        combined_equity[d] = (combined_equity[d] + e['value']) / 2

        total_trades = len(completed_trades := [t for t in combined_trades if 'exit_date' in t])
        win_trades = [t for t in completed_trades if t.get('pnl', 0) > 0]
        lose_trades = [t for t in completed_trades if t.get('pnl', 0) <= 0]

        summary = {
            'total_return': round(sum(r['metrics']['total_return'] for r in all_results.values() if 'metrics' in r) / max(len([r for r in all_results.values() if 'metrics' in r]), 1), 4),
            'total_trades': total_trades,
            'win_rate': round(len(win_trades) / total_trades, 4) if total_trades > 0 else 0,
            'profit_factor': round(sum(t.get('pnl', 0) for t in win_trades) / abs(sum(t.get('pnl', 0) for t in lose_trades)), 2) if lose_trades and sum(t.get('pnl', 0) for t in lose_trades) != 0 else float('inf'),
            'stocks_tested': len(codes),
        }

        equity_curve = sorted(
            [{'date': k, 'value': v} for k, v in (combined_equity or {}).items()],
            key=lambda x: x['date']
        )

        return {
            'id': f"fb_{uuid.uuid4().hex[:8]}",
            'status': 'success',
            'summary': summary,
            'results': all_results,
            'equity_curve': equity_curve,
            'trades': completed_trades[:100],
        }

    except Exception as e:
        raise HTTPException(500, f"Factor backtest failed: {e}")


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
    strategies = _safe_json_load(STRATEGIES_FILE, {})

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

    _atomic_json_dump(STRATEGIES_FILE, strategies)

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
    strategies = _safe_json_load(STRATEGIES_FILE, {})
    metadata = strategies.get(strategy_id)
    if isinstance(metadata, dict):
        info['notes'] = metadata.get('notes', '')

    return info


@router.put("/strategies/{strategy_id}")
def update_strategy(strategy_id: str, req: CreateStrategyReq):
    """更新自定义策略"""
    registry = get_registry()
    if registry._is_builtin(strategy_id):
        raise HTTPException(403, "Cannot modify built-in strategy")

    registry.save_custom(strategy_id, req.source)

    strategies = _safe_json_load(STRATEGIES_FILE, {})

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

    _atomic_json_dump(STRATEGIES_FILE, strategies)

    return {"id": strategy_id, "status": "updated"}


@router.delete("/strategies/{strategy_id}")
def delete_strategy(strategy_id: str):
    """删除自定义策略"""
    registry = get_registry()
    if registry._is_builtin(strategy_id):
        raise HTTPException(403, "Cannot delete built-in strategy")

    registry.delete_custom(strategy_id)

    if os.path.exists(STRATEGIES_FILE):
        strategies = _safe_json_load(STRATEGIES_FILE, {})
        strategies.pop(strategy_id, None)
        _atomic_json_dump(STRATEGIES_FILE, strategies)

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
    records = [record for record in _safe_json_load(RECORDS_FILE, []) if isinstance(record, dict)]

    # 按时间倒序
    records = sorted(records, key=lambda x: x.get('created_at', ''), reverse=True)
    return {"records": records[:limit], "count": len(records)}


@router.get("/records/{record_id}")
def get_record(record_id: str):
    """获取回测记录详情"""
    records = [record for record in _safe_json_load(RECORDS_FILE, []) if isinstance(record, dict)]

    for r in records:
        if r.get('id') == record_id:
            return r

    raise HTTPException(404, "Record not found")


@router.delete("/records/{record_id}")
def delete_record(record_id: str):
    """删除回测记录"""
    if not os.path.exists(RECORDS_FILE):
        return {"status": "ok"}

    records = [record for record in _safe_json_load(RECORDS_FILE, []) if isinstance(record, dict)]

    records = [r for r in records if r.get('id') != record_id]

    _atomic_json_dump(RECORDS_FILE, records)

    return {"status": "deleted"}


# ─── 辅助函数 ────────────────────────────────────────

def _save_backtest_record(record: dict):
    """保存回测记录到文件"""
    records = [item for item in _safe_json_load(RECORDS_FILE, []) if isinstance(item, dict)]

    records.append(record)

    # 保留最近 200 条
    records = sorted(records, key=lambda x: x.get('created_at', ''), reverse=True)[:200]

    _atomic_json_dump(RECORDS_FILE, records)
