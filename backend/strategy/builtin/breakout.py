"""突破策略"""
import pandas as pd
from .base import Strategy


class Breakout(Strategy):
    """突破策略 — 价格突破N日高点买入，跌破N日低点卖出"""

    name = "突破策略"
    description = "突破近期高点买入，跌破近期低点卖出"
    author = "内置"
    version = 1
    tags = ["趋势", "动量"]

    params_def = [
        {
            'name': 'period',
            'type': 'int',
            'default': 20,
            'min': 5,
            'max': 120,
            'step': 1,
            'description': '观察周期（日）'
        },
        {
            'name': 'atr_period',
            'type': 'int',
            'default': 14,
            'min': 5,
            'max': 60,
            'step': 1,
            'description': 'ATR周期（用于止损）'
        }
    ]

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        high = data['high']
        low = data['low']
        close = data['close']

        # 计算N日高低点
        highest = high.rolling(window=self.period).max().shift(1)
        lowest = low.rolling(window=self.period).min().shift(1)

        # ATR
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=self.atr_period).mean()

        # 信号
        signal = pd.Series(0, index=data.index)
        signal[close > highest] = 1
        signal[close < lowest] = -1

        return pd.DataFrame({
            'signal': signal,
            'indicators_highest': highest,
            'indicators_lowest': lowest,
            'indicators_atr': atr,
        })
