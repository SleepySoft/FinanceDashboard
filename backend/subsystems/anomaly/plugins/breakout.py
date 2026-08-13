"""突破检测插件

原理：价格突破关键位置（如前20日高点）通常意味着趋势转折或加速。
这是技术分析中最经典的信号之一。
"""
from .base import DetectorPlugin, DetectionResult, Signal


class BreakoutDetector(DetectorPlugin):
    """突破/跌破检测"""

    name = "breakout"
    description = "检测是否突破近期高低点"
    default_lookback = 20  # 向前看多少个交易日

    def detect(self, code, df, today):
        lookback = self._param("lookback", self.default_lookback)

        if len(df) < lookback + 1:
            return None

        history = df.iloc[-(lookback + 1):-1]
        high_n = history["high"].max()
        low_n = history["low"].min()
        close = today["close"]

        # 突破前N日高点
        if close > high_n:
            breakout_pct = (close - high_n) / high_n * 100
            score = min(int(breakout_pct * 5) + 10, 25)
            return DetectionResult(
                plugin_name=self.name,
                score=score,
                signals=[Signal(
                    type="breakout",
                    value=round(high_n, 2),
                    score=score,
                    desc=f"突破前{lookback}日高点 {high_n:.2f}"
                )],
                metadata={"breakout_type": "high", "breakout_level": round(high_n, 2)},
                triggered=True
            )

        # 跌破前N日低点
        if close < low_n:
            breakout_pct = (low_n - close) / low_n * 100
            score = min(int(breakout_pct * 5) + 10, 25)
            return DetectionResult(
                plugin_name=self.name,
                score=score,
                signals=[Signal(
                    type="breakout",
                    value=round(low_n, 2),
                    score=score,
                    desc=f"跌破前{lookback}日低点 {low_n:.2f}"
                )],
                metadata={"breakout_type": "low", "breakout_level": round(low_n, 2)},
                triggered=True
            )

        return None
