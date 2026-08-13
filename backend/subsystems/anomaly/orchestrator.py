"""异动检测编排器

协调多个检测插件运行，聚合结果。
可同时运行多个插件，结果合并输出。
"""
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
import pandas as pd

from .plugins.base import DetectorPlugin, SectorDetectorPlugin, DetectionResult
from .registry import PluginRegistry
from .core import (
    StockAnomaly, SectorAnomaly,
    TushareClient,
    MIN_AMPLITUDE_PCT, MIN_CHANGE_PCT,
    SCORE_NOTABLE, SCORE_STRONG,
)


@dataclass
class OrchestratorResult:
    """编排器输出"""
    stock_anomalies: List[StockAnomaly] = field(default_factory=list)
    sector_anomalies: List[SectorAnomaly] = field(default_factory=list)
    plugin_results: Dict[str, List[DetectionResult]] = field(default_factory=dict)
    # plugin_results 记录每个插件对每只个股的输出，方便调试和分析


class AnomalyOrchestrator:
    """
    异动检测编排器

    管理多个检测插件，支持：
    - 同时运行多个个股检测插件
    - 同时运行多个板块检测插件
    - 插件结果聚合、去重、评分

    用法：
        registry = PluginRegistry()
        registry.register_defaults()

        orch = AnomalyOrchestrator(registry=registry)
        result = orch.scan(date="2024-01-15", codes=["000001.SZ"])
    """

    def __init__(self, registry: PluginRegistry = None, client: TushareClient = None):
        self.registry = registry or PluginRegistry()
        if not self.registry.stock_plugins:
            self.registry.register_defaults()
        self.client = client or TushareClient()

    def detect_stock(
        self,
        code: str,
        df: pd.DataFrame,
        trade_date: str,
        name_map: Dict = None,
        sector_map: Dict = None
    ) -> Optional[StockAnomaly]:
        """
        对单只股票运行所有已注册的个股检测插件

        Returns:
            StockAnomaly or None
        """
        df = df.sort_values("trade_date").reset_index(drop=True)

        today_rows = df[df["trade_date"] == trade_date.replace("-", "")]
        if today_rows.empty:
            return None
        today = today_rows.iloc[0]

        # 运行所有插件
        total_score = 0
        all_signals = []
        breakout_type = ""
        breakout_level = 0.0

        for plugin in self.registry.stock_plugins:
            try:
                result = plugin.detect(code, df, today)
                if result and result.triggered:
                    total_score += result.score
                    all_signals.extend([
                        {"type": s.type, "value": s.value, "score": s.score, "desc": s.desc}
                        for s in result.signals
                    ])
                    # 收集突破信息
                    if result.metadata.get("breakout_type"):
                        breakout_type = result.metadata["breakout_type"]
                        breakout_level = result.metadata.get("breakout_level", 0)
            except Exception as e:
                # 单个插件失败不影响整体
                print(f"[Orchestrator] Plugin {plugin.name} failed for {code}: {e}")
                continue

        if not all_signals or total_score < SCORE_NOTABLE:
            return None

        level = "weak" if total_score < SCORE_NOTABLE else ("strong" if total_score >= SCORE_STRONG else "notable")

        name = (name_map or {}).get(code, code)
        sector = (sector_map or {}).get(code, "")

        return StockAnomaly(
            code=code,
            name=name,
            date=f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:]}",
            score=total_score,
            level=level,
            close=today.get("close", 0),
            change_pct=today.get("pct_chg", 0),
            amplitude=(today.get("high", 0) - today.get("low", 0)) / today.get("pre_close", 1) * 100 if today.get("pre_close") else 0,
            volume=today.get("vol", 0),
            vol_ratio=1.0,  # 会在后续从 daily_basic 补充
            signals=all_signals,
            breakout_type=breakout_type,
            breakout_level=round(breakout_level, 2) if breakout_level else 0,
            sector=sector,
            sector_anomaly=False,
        )

    def detect_sectors(
        self,
        sector_data: Dict[str, List[Dict]],
        trade_date: str
    ) -> List[SectorAnomaly]:
        """
        检测板块异动
        """
        sector_anomalies = []

        for sector, stocks in sector_data.items():
            if len(stocks) < 2:
                continue

            for plugin in self.registry.sector_plugins:
                try:
                    result = plugin.detect_sector(sector, stocks, trade_date)
                    if result and result.triggered:
                        meta = result.metadata
                        sector_anomalies.append(SectorAnomaly(
                            sector=sector,
                            date=trade_date,
                            score=result.score,
                            level=meta.get("level", "notable"),
                            stock_count=meta.get("stock_count", len(stocks)),
                            anomaly_count=meta.get("stock_count", len(stocks)),
                            anomaly_ratio=0.0,
                            avg_change_pct=meta.get("avg_change_pct", 0),
                            avg_volume_ratio=meta.get("avg_volume_ratio", 0),
                            top_gainer=meta.get("top_gainer"),
                            top_loser=meta.get("top_loser"),
                            signals=[{"type": s.type, "value": s.value, "score": s.score, "desc": s.desc}
                                     for s in result.signals],
                        ))
                except Exception as e:
                    print(f"[Orchestrator] Sector plugin {plugin.name} failed for {sector}: {e}")
                    continue

        sector_anomalies.sort(key=lambda x: x.score, reverse=True)
        return sector_anomalies

    def scan(
        self,
        trade_date: Optional[str] = None,
        codes: Optional[List[str]] = None,
        min_score: int = SCORE_NOTABLE,
        sample_size: Optional[int] = None,
    ) -> OrchestratorResult:
        """
        全市场扫描

        Args:
            trade_date: YYYY-MM-DD 或 YYYYMMDD
            codes: 限定扫描列表
            min_score: 最低分数
            sample_size: 测试用，限制扫描数量

        Returns:
            OrchestratorResult
        """
        if trade_date is None:
            trade_date = self._latest_trade_date()
        trade_date_str = trade_date.replace("-", "")

        # 获取全市场日线
        df_all = self.client.get_daily_all(trade_date_str)
        if df_all is None or df_all.empty:
            return OrchestratorResult()

        # 基础信息映射
        df_basic = self.client.get_stock_basic()
        name_map = dict(zip(df_basic["ts_code"], df_basic["name"])) if df_basic is not None else {}
        sector_map = dict(zip(df_basic["ts_code"], df_basic["industry"])) if df_basic is not None else {}

        # 确定扫描范围
        if codes:
            scan_codes = [c for c in codes if c in df_all["ts_code"].values]
        else:
            scan_codes = df_all["ts_code"].tolist()
            if sample_size:
                scan_codes = scan_codes[:sample_size]

        # 快速过滤
        deep_check_codes = []
        for ts_code in scan_codes:
            row = df_all[df_all["ts_code"] == ts_code]
            if row.empty:
                continue
            row = row.iloc[0]
            amplitude = (row.get("high", 0) - row.get("low", 0)) / row.get("pre_close", 1) * 100 if row.get("pre_close") else 0
            change_pct = row.get("pct_chg", 0) or 0
            if abs(change_pct) >= 1.5 or amplitude >= 3:
                deep_check_codes.append(ts_code)

        # 批量获取历史数据
        hist_df_map = {}
        if deep_check_codes:
            from datetime import datetime, timedelta
            end_dt = datetime.strptime(trade_date_str, "%Y%m%d")
            start_dt = end_dt - timedelta(days=120)
            start_date = start_dt.strftime("%Y%m%d")

            batch_size = 500
            for i in range(0, len(deep_check_codes), batch_size):
                batch = deep_check_codes[i:i + batch_size]
                batch_df = self.client.get_daily_batch(batch, start_date, trade_date_str)
                if batch_df is not None and not batch_df.empty:
                    for code in batch:
                        code_df = batch_df[batch_df["ts_code"] == code]
                        if len(code_df) >= 10:
                            hist_df_map[code] = code_df

        # 深度检测
        stock_anomalies = []
        sector_data: Dict[str, List[Dict]] = {}

        for ts_code in deep_check_codes:
            hist_df = hist_df_map.get(ts_code)
            if hist_df is None:
                continue

            anomaly = self.detect_stock(ts_code, hist_df, trade_date_str, name_map, sector_map)
            if anomaly and anomaly.score >= min_score:
                stock_anomalies.append(anomaly)

                sector = anomaly.sector or "其他"
                if sector not in sector_data:
                    sector_data[sector] = []
                sector_data[sector].append({
                    "code": ts_code,
                    "name": anomaly.name,
                    "change_pct": anomaly.change_pct,
                    "score": anomaly.score,
                    "vol_ratio": anomaly.vol_ratio,
                })

        # 板块检测
        sector_anomalies = self.detect_sectors(sector_data, trade_date_str)

        # 标记个股是否伴随板块异动
        for sa in stock_anomalies:
            for sec_a in sector_anomalies:
                if sa.sector == sec_a.sector and sec_a.level in ("notable", "strong"):
                    sa.sector_anomaly = True
                    break

        stock_anomalies.sort(key=lambda x: x.score, reverse=True)

        return OrchestratorResult(
            stock_anomalies=stock_anomalies,
            sector_anomalies=sector_anomalies,
        )

    def _latest_trade_date(self) -> str:
        """获取最近一个交易日"""
        from datetime import datetime, timedelta
        today = datetime.now().strftime("%Y%m%d")
        df = self.client.get_trade_cal(today, today)
        if df is not None and not df.empty:
            trade_dates = df[df["is_open"] == 1]["cal_date"].tolist()
            if trade_dates:
                return max(trade_dates)
        now = datetime.now()
        if now.hour >= 15:
            return now.strftime("%Y%m%d")
        return (now - timedelta(days=1)).strftime("%Y%m%d")
