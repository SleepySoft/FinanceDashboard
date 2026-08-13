"""策略注册表 — 管理内置策略和自定义策略"""
import os
import sys
import importlib.util
import inspect
from pathlib import Path


class StrategyRegistry:
    """策略注册表 — 管理内置策略和自定义策略"""

    def __init__(self, custom_dir: str = None):
        self.strategies = {}  # {strategy_id: StrategyClass}
        self.custom_dir = custom_dir or '/root/data/FinanceDashboard/backend/strategy/custom'
        self._load_builtin()
        self._load_custom()

    def _load_builtin(self):
        """加载内置策略"""
        from strategy.builtin import ma_cross, rsi_reversal, macd_trend, breakout

        modules = [ma_cross, rsi_reversal, macd_trend, breakout]
        for module in modules:
            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and
                    hasattr(obj, 'name') and
                    hasattr(obj, 'generate_signals') and
                    obj.__name__ != 'Strategy'):
                    sid = obj.name.lower().replace(' ', '_').replace('-', '_')
                    self.strategies[sid] = obj

    def _load_custom(self):
        """从文件加载自定义策略"""
        os.makedirs(self.custom_dir, exist_ok=True)

        for file in Path(self.custom_dir).glob('*.py'):
            if file.name.startswith('_'):
                continue

            try:
                spec = importlib.util.spec_from_file_location(
                    f"custom_{file.stem}", str(file)
                )
                module = importlib.util.module_from_spec(spec)
                sys.modules[spec.name] = module
                spec.loader.exec_module(module)

                for name, obj in inspect.getmembers(module):
                    if (inspect.isclass(obj) and
                        hasattr(obj, 'name') and
                        hasattr(obj, 'generate_signals') and
                        obj.__name__ != 'Strategy'):
                        sid = obj.name.lower().replace(' ', '_').replace('-', '_')
                        self.strategies[sid] = obj
            except Exception as e:
                print(f"Failed to load custom strategy {file}: {e}")

    def get(self, strategy_id: str):
        """获取策略类"""
        return self.strategies.get(strategy_id)

    def list_all(self) -> list:
        """列出所有策略的元数据"""
        result = []
        for sid, cls in self.strategies.items():
            try:
                instance = cls()
                d = instance.to_dict()
                d['id'] = sid
                d['type'] = 'builtin' if self._is_builtin(sid) else 'custom'
                result.append(d)
            except Exception as e:
                print(f"Failed to describe strategy {sid}: {e}")
        return result

    def _is_builtin(self, sid: str) -> bool:
        """判断是否为内置策略"""
        from strategy.builtin import ma_cross, rsi_reversal, macd_trend, breakout
        builtin_modules = [ma_cross, rsi_reversal, macd_trend, breakout]
        for module in builtin_modules:
            for name, obj in inspect.getmembers(module):
                if inspect.isclass(obj) and hasattr(obj, 'name'):
                    bid = obj.name.lower().replace(' ', '_').replace('-', '_')
                    if bid == sid:
                        return True
        return False

    def save_custom(self, strategy_id: str, source: str) -> bool:
        """保存自定义策略到文件"""
        file_path = Path(self.custom_dir) / f"{strategy_id}.py"
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(source)
        self._load_custom()
        return True

    def delete_custom(self, strategy_id: str) -> bool:
        """删除自定义策略"""
        file_path = Path(self.custom_dir) / f"{strategy_id}.py"
        if file_path.exists():
            file_path.unlink()
            if strategy_id in self.strategies:
                del self.strategies[strategy_id]
            return True
        return False


# 全局注册表实例
_registry = None

def get_registry() -> StrategyRegistry:
    global _registry
    if _registry is None:
        _registry = StrategyRegistry()
    return _registry
