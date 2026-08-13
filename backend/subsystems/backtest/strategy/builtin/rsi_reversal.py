"""RSI 反转策略"""
import pandas as pd
from .base import Strategy


class RSIReversal(Strategy):
    """RSI 超卖反弹策略 — RSI低于阈值买入，高于阈值卖出"""

    name = "RSI反转"
    description = "RSI超卖时买入，超买时卖出"
    author = "内置"
    version = 1
    tags = ["反转", "震荡"]

    params_def = [
        {
            'name': 'period',
            'type': 'int',
            'default': 14,
            'min': 2,
            'max': 100,
            'step': 1,
            'description': 'RSI周期'
        },
        {
            'name': 'oversold',
            'type': 'int',
            'default': 30,
            'min': 5,
            'max': 50,
            'step': 1,
            'description': '超卖阈值'
        },
        {
            'name': 'overbought',
            'type': 'int',
            'default': 70,
            'min': 50,
            'max': 95,
            'step': 1,
            'description': '超买阈值'
        }
    ]

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        close = data['close']
        delta = close.diff()
        gain = delta.where(delta > 0, 0)
        loss = (-delta).where(delta < 0, 0)

        avg_gain = gain.rolling(window=self.period).mean()
        avg_loss = loss.rolling(window=self.period).mean()

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        # 信号: 超卖反弹(1), 超买回落(-1)
        signal = pd.Series(0, index=data.index)
        signal[rsi < self.oversold] = 1
        signal[rsi > self.overbought] = -1

        return pd.DataFrame({
            'signal': signal,
            'indicators_rsi': rsi,
        })
