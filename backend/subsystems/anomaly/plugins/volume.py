"""量比检测插件

原理：价可以骗，量很难骗。
真正的异动通常伴随成交量的显著放大——
意味着大资金真的在进场/离场，不是散户的自嗨。
"""
from .base import DetectorPlugin, DetectionResult, Signal


class VolumeDetector(DetectorPlugin):
    """成交量放大检测"""

    name = "volume"
    description = "检测成交量是否异常放大（量比）"
    default_threshold = 2.0  # 量比倍数

    def detect(self, code, df, today):
        if len(df) < 6:
            return None

        today_vol = df.iloc[-1]["vol"]
        past_5_avg = df.iloc[-6:-1]["vol"].mean()

        if not past_5_avg or past_5_avg <= 0:
            return None

        vol_ratio = today_vol / past_5_avg
        threshold = self._param("threshold", self.default_threshold)

        if vol_ratio < threshold:
            return None

        # 分数计算
        score = min(int(vol_ratio / threshold * 15), 25)

        return DetectionResult(
            plugin_name=self.name,
            score=score,
            signals=[Signal(
                type="volume",
                value=round(vol_ratio, 2),
                score=score,
                desc=f"量比{vol_ratio:.1f}倍"
            )],
            triggered=True
        )
