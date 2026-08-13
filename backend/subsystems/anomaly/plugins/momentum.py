"""连续动量检测插件

原理：单日异动可能是偶然，连续多日同向运动意味着趋势确立。
"""
from .base import DetectorPlugin, DetectionResult, Signal


class MomentumDetector(DetectorPlugin):
    """连续动量检测"""

    name = "momentum"
    description = "检测连续多日同向运动"

    def detect(self, code, df, today):
        if len(df) < 3:
            return None

        changes = df["pct_chg"].tolist()

        # 从最近一日向前数
        direction = 1 if changes[-1] > 0 else -1
        streak = 1

        for i in range(len(changes) - 2, -1, -1):
            if (changes[i] > 0 and direction > 0) or (changes[i] < 0 and direction < 0):
                streak += 1
            else:
                break

        if streak < 2:
            return None

        # 评分
        if streak >= 4:
            score = 15
        elif streak == 3:
            score = 10
        else:
            score = 5

        direction_str = "涨" if direction > 0 else "跌"

        return DetectionResult(
            plugin_name=self.name,
            score=score,
            signals=[Signal(
                type="momentum",
                value=streak,
                score=score,
                desc=f"连续{streak}日{direction_str}"
            )],
            triggered=True
        )
