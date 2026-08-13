"""板块异动检测插件

原理：板块异动 > 个股异动。
如果同一板块内多只个股同时异动，说明这不是个股行为，
而是行业/主题级别的资金流动。
"""
from .base import SectorDetectorPlugin, DetectionResult, Signal


class SectorMomentumDetector(SectorDetectorPlugin):
    """板块共振检测"""

    name = "sector_momentum"
    description = "检测板块内多股同时异动"
    default_min_stocks = 3
    default_min_sector_ratio = 0.30
    default_score_notable = 60
    default_score_strong = 80

    def detect_sector(self, sector, stocks, trade_date):
        if len(stocks) < 2:
            return None

        min_stocks = self._param("min_stocks", self.default_min_stocks)
        score_notable = self._param("score_notable", self.default_score_notable)
        score_strong = self._param("score_strong", self.default_score_strong)

        score = 0
        signals = []
        stock_count = len(stocks)
        avg_change = sum(s["change_pct"] for s in stocks) / stock_count
        avg_vol = sum(s.get("vol_ratio", 1) for s in stocks) / stock_count

        # 信号1：板块内异动股数量
        if stock_count >= min_stocks:
            count_score = min(stock_count * 10, 30)
            score += count_score
            signals.append(Signal(
                type="count",
                value=stock_count,
                score=count_score,
                desc=f"{stock_count}只个股异动"
            ))

        # 信号2：板块平均涨跌幅
        if abs(avg_change) >= 3:
            chg_score = min(int(abs(avg_change) / 3 * 15), 25)
            score += chg_score
            signals.append(Signal(
                type="avg_change",
                value=round(avg_change, 2),
                score=chg_score,
                desc=f"板块平均{'涨' if avg_change > 0 else '跌'}{abs(avg_change):.1f}%"
            ))

        # 信号3：板块平均量比
        if avg_vol >= 1.5:
            vol_score = min(int(avg_vol / 1.5 * 10), 20)
            score += vol_score
            signals.append(Signal(
                type="avg_volume",
                value=round(avg_vol, 2),
                score=vol_score,
                desc=f"板块平均量比{avg_vol:.1f}"
            ))

        # 信号4：方向一致性
        up_count = sum(1 for s in stocks if s["change_pct"] > 0)
        down_count = stock_count - up_count
        consistency = max(up_count, down_count) / stock_count

        if consistency >= 0.8:
            cons_score = 15
            score += cons_score
            direction = "涨" if up_count > down_count else "跌"
            signals.append(Signal(
                type="consistency",
                value=round(consistency, 2),
                score=cons_score,
                desc=f"方向一致：{up_count}涨{down_count}跌"
            ))

        if score < score_notable:
            return None

        level = "strong" if score >= score_strong else "notable"

        return DetectionResult(
            plugin_name=self.name,
            score=score,
            signals=signals,
            metadata={
                "level": level,
                "stock_count": stock_count,
                "avg_change_pct": round(avg_change, 2),
                "avg_volume_ratio": round(avg_vol, 2),
                "top_gainer": max(stocks, key=lambda x: x["change_pct"]) if stocks else None,
                "top_loser": min(stocks, key=lambda x: x["change_pct"]) if stocks else None,
            },
            triggered=True
        )
