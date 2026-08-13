"""回测结果缓存 — 基于参数哈希"""
import hashlib
import json
import os
from datetime import datetime


class BacktestCache:
    """
    回测结果缓存 — 基于参数哈希

    缓存键生成：
    - 策略 ID + 版本
    - 参数值
    - 股票代码 + 时间范围
    - 回测配置（手续费、滑点等）
    """

    def __init__(self, cache_dir: str = None):
        self.cache_dir = cache_dir or '/root/data/FinanceDashboard/data/backtest/cache'
        os.makedirs(self.cache_dir, exist_ok=True)

    def _make_key(self, strategy_id: str, params: dict,
                  codes: list, start: str, end: str,
                  config: dict) -> str:
        """生成缓存键"""
        key_data = {
            'strategy': strategy_id,
            'params': params,
            'codes': sorted(codes),
            'start': start,
            'end': end,
            'config': config
        }
        json_str = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()[:16]

    def get(self, strategy_id: str, params: dict,
            codes: list, start: str, end: str,
            config: dict) -> dict:
        """获取缓存结果"""
        key = self._make_key(strategy_id, params, codes, start, end, config)
        cache_file = os.path.join(self.cache_dir, f"{key}.json")

        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cached = json.load(f)
                # 检查缓存是否过期（7天）
                created = datetime.fromisoformat(cached.get('created_at', '2000-01-01'))
                if (datetime.now() - created).days < 7:
                    return cached.get('result')
            except Exception:
                pass
        return None

    def set(self, result: dict, strategy_id: str, params: dict,
            codes: list, start: str, end: str,
            config: dict):
        """保存缓存"""
        key = self._make_key(strategy_id, params, codes, start, end, config)
        cache_file = os.path.join(self.cache_dir, f"{key}.json")

        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump({
                'key': key,
                'created_at': datetime.now().isoformat(),
                'result': result
            }, f, ensure_ascii=False, indent=2)

    def clear(self):
        """清除所有缓存"""
        for f in os.listdir(self.cache_dir):
            if f.endswith('.json'):
                os.remove(os.path.join(self.cache_dir, f))
