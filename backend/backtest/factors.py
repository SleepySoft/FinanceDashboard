"""因子计算与缓存系统

预计算常见技术指标因子，支持缓存复用。
用户可通过选择因子 + 设置阈值条件直接回测，无需编写策略代码。
"""
import pandas as pd
import numpy as np
import os
import hashlib
from typing import Dict, List, Optional
from dataclasses import dataclass

from backtest.data_provider import DataSource


@dataclass
class FactorDef:
    """因子定义"""
    id: str
    name: str
    category: str  # momentum / trend / volatility / volume / composite
    params: List[dict]  # 因子参数定义
    description: str = ""


# ─── 预定义因子列表 ─────────────────────────────────

BUILTIN_FACTORS: List[FactorDef] = [
    FactorDef("rsi", "RSI", "momentum",
              [{"name": "period", "type": "int", "default": 14, "min": 2, "max": 100}],
              "相对强弱指数"),
    FactorDef("macd_dif", "MACD-DIF", "trend",
              [{"name": "fast", "type": "int", "default": 12},
               {"name": "slow", "type": "int", "default": 26}],
              "MACD快线"),
    FactorDef("macd_dea", "MACD-DEA", "trend",
              [{"name": "fast", "type": "int", "default": 12},
               {"name": "slow", "type": "int", "default": 26},
               {"name": "signal", "type": "int", "default": 9}],
              "MACD信号线"),
    FactorDef("ma", "移动平均线", "trend",
              [{"name": "period", "type": "int", "default": 20, "min": 2, "max": 250}],
              "简单移动平均"),
    FactorDef("ema", "指数移动平均", "trend",
              [{"name": "period", "type": "int", "default": 20, "min": 2, "max": 250}],
              "指数移动平均"),
    FactorDef("boll_upper", "布林上轨", "volatility",
              [{"name": "period", "type": "int", "default": 20},
               {"name": "std", "type": "int", "default": 2}],
              "布林带上轨"),
    FactorDef("boll_lower", "布林下轨", "volatility",
              [{"name": "period", "type": "int", "default": 20},
               {"name": "std", "type": "int", "default": 2}],
              "布林带下轨"),
    FactorDef("atr", "ATR", "volatility",
              [{"name": "period", "type": "int", "default": 14}],
              "平均真实波幅"),
    FactorDef("roc", "ROC", "momentum",
              [{"name": "period", "type": "int", "default": 12}],
              "变动率"),
    FactorDef("cci", "CCI", "momentum",
              [{"name": "period", "type": "int", "default": 14}],
              "顺势指标"),
    FactorDef("volume_ma", "成交量MA", "volume",
              [{"name": "period", "type": "int", "default": 20}],
              "成交量移动平均"),
    FactorDef("obv", "OBV", "volume", [], "能量潮"),
    FactorDef("price_to_ma", "价格/均线", "trend",
              [{"name": "period", "type": "int", "default": 20}],
              "收盘价与均线比值"),
]


# ─── 因子计算函数 ──────────────────────────────────

def calc_rsi(data: pd.DataFrame, period: int = 14) -> pd.Series:
    close = data['close']
    delta = close.diff()
    gain = delta.where(delta > 0, 0)
    loss = (-delta).where(delta < 0, 0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calc_macd(data: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    close = data['close']
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal, adjust=False).mean()
    macd = 2 * (dif - dea)
    return pd.DataFrame({'dif': dif, 'dea': dea, 'macd': macd})


def calc_ma(data: pd.DataFrame, period: int = 20) -> pd.Series:
    return data['close'].rolling(window=period).mean()


def calc_ema(data: pd.DataFrame, period: int = 20) -> pd.Series:
    return data['close'].ewm(span=period, adjust=False).mean()


def calc_boll(data: pd.DataFrame, period: int = 20, std: int = 2) -> pd.DataFrame:
    close = data['close']
    ma = close.rolling(window=period).mean()
    sigma = close.rolling(window=period).std()
    return pd.DataFrame({
        'upper': ma + std * sigma,
        'lower': ma - std * sigma,
        'mid': ma,
    })


def calc_atr(data: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = data['high'], data['low'], data['close']
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()


def calc_roc(data: pd.DataFrame, period: int = 12) -> pd.Series:
    return (data['close'] - data['close'].shift(period)) / data['close'].shift(period) * 100


def calc_cci(data: pd.DataFrame, period: int = 14) -> pd.Series:
    tp = (data['high'] + data['low'] + data['close']) / 3
    ma_tp = tp.rolling(window=period).mean()
    md = tp.rolling(window=period).apply(lambda x: np.mean(np.abs(x - np.mean(x))), raw=False)
    return (tp - ma_tp) / (0.015 * md)


def calc_volume_ma(data: pd.DataFrame, period: int = 20) -> pd.Series:
    return data['volume'].rolling(window=period).mean()


def calc_obv(data: pd.DataFrame) -> pd.Series:
    close = data['close']
    volume = data['volume']
    obv = pd.Series(0, index=data.index)
    obv.iloc[0] = volume.iloc[0]
    for i in range(1, len(data)):
        if close.iloc[i] > close.iloc[i - 1]:
            obv.iloc[i] = obv.iloc[i - 1] + volume.iloc[i]
        elif close.iloc[i] < close.iloc[i - 1]:
            obv.iloc[i] = obv.iloc[i - 1] - volume.iloc[i]
        else:
            obv.iloc[i] = obv.iloc[i - 1]
    return obv


def calc_price_to_ma(data: pd.DataFrame, period: int = 20) -> pd.Series:
    return data['close'] / calc_ma(data, period)


# 因子计算路由表
FACTOR_CALCULATORS = {
    'rsi': lambda d, p: calc_rsi(d, **p),
    'macd_dif': lambda d, p: calc_macd(d, **{k: v for k, v in p.items() if k in ['fast', 'slow']})['dif'],
    'macd_dea': lambda d, p: calc_macd(d, **{k: v for k, v in p.items() if k in ['fast', 'slow', 'signal']})['dea'],
    'ma': calc_ma,
    'ema': calc_ema,
    'boll_upper': lambda d, p: calc_boll(d, **p)['upper'],
    'boll_lower': lambda d, p: calc_boll(d, **p)['lower'],
    'atr': calc_atr,
    'roc': calc_roc,
    'cci': calc_cci,
    'volume_ma': calc_volume_ma,
    'obv': calc_obv,
    'price_to_ma': calc_price_to_ma,
}


class FactorCache:
    """因子计算缓存 — 按 (code, factor_id, params, date_range) 缓存"""

    def __init__(self, cache_dir: str = None):
        self.cache_dir = cache_dir or '/root/data/FinanceDashboard/data/backtest/factor_cache'
        os.makedirs(self.cache_dir, exist_ok=True)

    def _cache_key(self, code: str, factor_id: str, params: dict,
                   start: str, end: str, adjust: str) -> str:
        """生成缓存键"""
        param_str = '_'.join(f"{k}={v}" for k, v in sorted(params.items()))
        key = f"{code}_{factor_id}_{param_str}_{start}_{end}_{adjust}"
        return hashlib.md5(key.encode()).hexdigest()

    def get(self, code: str, factor_id: str, params: dict,
            start: str, end: str, adjust: str) -> Optional[pd.Series]:
        """从缓存读取因子"""
        key = self._cache_key(code, factor_id, params, start, end, adjust)
        cache_file = os.path.join(self.cache_dir, f"{key}.parquet")

        if os.path.exists(cache_file):
            try:
                df = pd.read_parquet(cache_file)
                # 过滤日期范围
                mask = (df.index >= start) & (df.index <= end)
                return df.loc[mask, 'value']
            except Exception:
                pass
        return None

    def set(self, series: pd.Series, code: str, factor_id: str, params: dict,
            start: str, end: str, adjust: str):
        """保存因子到缓存（扩展范围以支持复用）"""
        key = self._cache_key(code, factor_id, params, start, end, adjust)
        cache_file = os.path.join(self.cache_dir, f"{key}.parquet")

        df = pd.DataFrame({'value': series})
        try:
            df.to_parquet(cache_file)
        except Exception:
            pass


class FactorEngine:
    """因子引擎 — 计算、缓存、管理因子"""

    def __init__(self, data_source: DataSource = None, cache: FactorCache = None):
        self.data_source = data_source
        self.cache = cache or FactorCache()

    def list_factors(self) -> List[dict]:
        """列出所有可用因子"""
        return [{
            'id': f.id,
            'name': f.name,
            'category': f.category,
            'params': f.params,
            'description': f.description,
        } for f in BUILTIN_FACTORS]

    def compute(self, code: str, factor_id: str, params: dict = None,
                start: str = None, end: str = None, adjust: str = 'qfq',
                use_cache: bool = True) -> pd.Series:
        """
        计算单个因子

        Args:
            code: 股票代码
            factor_id: 因子ID
            params: 因子参数
            start, end: 日期范围
            adjust: 复权方式
            use_cache: 是否使用缓存

        Returns:
            因子值序列 (index=date)
        """
        params = params or {}

        # 检查缓存
        if use_cache:
            cached = self.cache.get(code, factor_id, params, start, end, adjust)
            if cached is not None:
                return cached

        # 获取数据（扩展范围以支持均线等需要历史数据的计算）
        # 最大回溯 250 天
        from datetime import datetime, timedelta
        ext_start = (datetime.strptime(start, '%Y-%m-%d') - timedelta(days=300)).strftime('%Y-%m-%d')
        data = self.data_source.get_daily_bars(code, ext_start, end, adjust)

        if data.empty:
            return pd.Series(dtype=float)

        # 计算因子
        calc_fn = FACTOR_CALCULATORS.get(factor_id)
        if calc_fn is None:
            raise ValueError(f"Unknown factor: {factor_id}")

        result = calc_fn(data, params)

        # 缓存完整序列
        if use_cache:
            self.cache.set(result, code, factor_id, params, start, end, adjust)

        # 返回请求范围内的数据
        mask = (result.index >= start) & (result.index <= end)
        return result.loc[mask]

    def compute_multi(self, code: str, factors: List[dict],
                      start: str, end: str, adjust: str = 'qfq') -> pd.DataFrame:
        """
        批量计算多个因子

        Args:
            factors: [{"factor_id": str, "params": dict, "alias": str}, ...]
        Returns:
            DataFrame, columns = aliases or factor_ids
        """
        data = self.data_source.get_daily_bars(code, start, end, adjust)
        if data.empty:
            return pd.DataFrame()

        results = {}
        for f in factors:
            fid = f['factor_id']
            params = f.get('params', {})
            alias = f.get('alias', fid)
            try:
                series = self.compute(code, fid, params, start, end, adjust)
                results[alias] = series
            except Exception as e:
                print(f"Factor compute failed {fid}: {e}")
                results[alias] = pd.Series(np.nan, index=data.index)

        df = pd.DataFrame(results)
        df.index = pd.to_datetime(df.index)
        return df

    def compute_for_universe(self, codes: List[str], factor_id: str, params: dict = None,
                             start: str = None, end: str = None,
                             adjust: str = 'qfq') -> Dict[str, pd.Series]:
        """为股票池计算单个因子"""
        return {
            code: self.compute(code, factor_id, params, start, end, adjust)
            for code in codes
        }
