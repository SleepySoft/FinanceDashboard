"""策略基类 — 所有策略（内置+自定义）必须继承"""
from abc import ABC, abstractmethod
import pandas as pd
import inspect


class Strategy(ABC):
    """
    策略基类 — 所有策略（内置+自定义）必须继承

    设计要点：
    1. 策略只关心信号生成，不关心回测执行
    2. 参数通过 __init__ 传入，便于参数扫描
    3. 支持逐帧观察 — generate_signals 返回完整信号序列
    """

    # 元数据（必须定义）
    name: str = "unnamed"
    description: str = ""
    author: str = ""
    version: int = 1
    tags: list = []

    # 参数定义（用于前端渲染和验证）
    params_def: list = []

    def __init__(self, **kwargs):
        """参数通过 kwargs 传入"""
        for param in self.params_def:
            name = param['name']
            setattr(self, name, kwargs.get(name, param.get('default')))

    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        核心方法：生成交易信号

        Args:
            data: OHLCV DataFrame
                Index: datetime
                Columns: open, high, low, close, volume

        Returns:
            包含以下列的 DataFrame：
            - signal: 1(买入), -1(卖出), 0(无)
            - indicators_{name}: 指标值（用于逐帧显示）
        """
        pass

    def get_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        可选：单独获取指标值（用于逐帧观察）
        默认调用 generate_signals 并提取指标列
        """
        signals = self.generate_signals(data)
        indicator_cols = [c for c in signals.columns if c.startswith('indicators_')]
        return signals[indicator_cols] if indicator_cols else pd.DataFrame()

    def validate_params(self) -> tuple:
        """参数验证"""
        for param in self.params_def:
            name = param['name']
            value = getattr(self, name, None)
            if param.get('required') and value is None:
                return False, f"参数 {name} 必填"
            if param.get('min') is not None and value < param['min']:
                return False, f"参数 {name} 不能小于 {param['min']}"
            if param.get('max') is not None and value > param['max']:
                return False, f"参数 {name} 不能大于 {param['max']}"
        return True, ""

    def to_dict(self) -> dict:
        """序列化为策略定义"""
        return {
            'id': self.name.lower().replace(' ', '_').replace('-', '_'),
            'name': self.name,
            'description': self.description,
            'author': self.author,
            'version': self.version,
            'tags': self.tags,
            'params': self.params_def,
        }

    def get_source_code(self) -> str:
        """获取策略源码（自定义策略用）"""
        return inspect.getsource(self.__class__)
