"""振幅检测插件

原理：振幅反映当日多空博弈激烈程度。
大振幅通常意味着重要信息释放或资金激烈换手。
"""
from .base import DetectorPlugin, DetectionResult, Signal


class AmplitudeDetector(DetectorPlugin):
    """振幅异常检测"""

    name = "amplitude"
    description = "检测当日振幅是否异常放大"
    default_threshold = 5.0  # 最低振幅(%)

    def detect(self, code, df, today):
        high = today.get("high", 0)
        low = today.get("low", 0)
        pre_close = today.get("pre_close", 0)

        if not pre_close or pre_close <= 0:
            return None

        amplitude = (high - low) / pre_close * 100
        threshold = self._param("threshold", self.default_threshold)

        if amplitude < threshold:
            return None

        # 分数计算：振幅越大分越高，封顶30
        score = min(int(amplitude / threshold * 20), 30)

        return DetectionResult(
            plugin_name=self.name,
            score=score,
            signals=[Signal(
                type="amplitude",
                value=round(amplitude, 2),
                score=score,
                desc=f"振幅{amplitude:.1f}%"
            )],
            triggered=True
        )
