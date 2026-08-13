"""均线交叉策略"""
import pandas as pd
from .base import Strategy


class MovingAverageCross(Strategy):
    """双均线交叉策略 — 快线突破慢线买入，跌破卖出"""

    name = "均线交叉"
    description = "快线突破慢线买入，跌破卖出"
    author = "内置"
    version = 1
    tags = ["趋势", "经典"]

    params_def = [
        {
            'name': 'fast',
            'type': 'int',
            'default': 10,
            'min': 2,
            'max': 60,
            'step': 1,
            'description': '快线周期'
        },
        {
            'name': 'slow',
            'type': 'int',
            'default': 30,
            'min': 5,
            'max': 250,
            'step': 1,
            'description': '慢线周期'
        }
    ]

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        close = data['close']

        # 计算均线
        fast_ma = close.rolling(window=self.fast).mean()
        slow_ma = close.rolling(window=self.slow).mean()

        # 信号: 金叉买入(1), 死叉卖出(-1), 其他(0)
        entries = fast_ma > slow_ma
        exits = fast_ma < slow_ma

        signal = pd.Series(0, index=data.index)
        signal[entries] = 1
        signal[exits] = -1

        return pd.DataFrame({
            'signal': signal,
            'indicators_fast_ma': fast_ma,
            'indicators_slow_ma': slow_ma,
        })
