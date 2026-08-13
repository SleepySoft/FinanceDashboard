"""MACD 趋势策略"""
import pandas as pd
from .base import Strategy


class MACDTrend(Strategy):
    """MACD 趋势跟踪策略 — DIF上穿DEA买入，下穿卖出"""

    name = "MACD趋势"
    description = "MACD金叉买入，死叉卖出"
    author = "内置"
    version = 1
    tags = ["趋势", "动量"]

    params_def = [
        {
            'name': 'fast',
            'type': 'int',
            'default': 12,
            'min': 2,
            'max': 60,
            'step': 1,
            'description': '快线周期'
        },
        {
            'name': 'slow',
            'type': 'int',
            'default': 26,
            'min': 5,
            'max': 120,
            'step': 1,
            'description': '慢线周期'
        },
        {
            'name': 'signal',
            'type': 'int',
            'default': 9,
            'min': 2,
            'max': 60,
            'step': 1,
            'description': '信号线周期'
        }
    ]

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        close = data['close']

        ema_fast = close.ewm(span=self.fast, adjust=False).mean()
        ema_slow = close.ewm(span=self.slow, adjust=False).mean()
        dif = ema_fast - ema_slow
        dea = dif.ewm(span=self.signal, adjust=False).mean()
        macd = 2 * (dif - dea)

        # 信号: DIF上穿DEA(1), 下穿(-1)
        signal = pd.Series(0, index=data.index)
        signal[(dif > dea) & (dif.shift(1) <= dea.shift(1))] = 1
        signal[(dif < dea) & (dif.shift(1) >= dea.shift(1))] = -1

        return pd.DataFrame({
            'signal': signal,
            'indicators_dif': dif,
            'indicators_dea': dea,
            'indicators_macd': macd,
        })
