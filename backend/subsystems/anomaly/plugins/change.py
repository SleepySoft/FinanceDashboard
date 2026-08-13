"""涨跌幅检测插件

原理：单向大幅运动比双向震荡更有方向性意义。
"""
from .base import DetectorPlugin, DetectionResult, Signal


class ChangeDetector(DetectorPlugin):
    """价格涨跌幅异常检测"""

    name = "change"
    description = "检测当日涨跌幅是否异常"
    default_threshold = 3.0  # 最低涨跌幅度(%)

    def detect(self, code, df, today):
        change_pct = today.get("pct_chg", 0) or 0
        threshold = self._param("threshold", self.default_threshold)

        if abs(change_pct) < threshold:
            return None

        # 分数计算
        score = min(int(abs(change_pct) / threshold * 15), 25)

        return DetectionResult(
            plugin_name=self.name,
            score=score,
            signals=[Signal(
                type="change",
                value=round(change_pct, 2),
                score=score,
                desc=f"{'涨' if change_pct > 0 else '跌'}{abs(change_pct):.1f}%"
            )],
            triggered=True
        )
