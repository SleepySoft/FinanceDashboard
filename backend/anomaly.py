"""
Anomaly Detection Module for FinanceDashboard
===============================================

原理：异动不是"波动"，而是"异常行为"。

普通人的视角：今天涨了5%，算异动。
我们的视角：涨5%是结果，要看它为什么涨——
是放量突破？是板块共振？还是孤立事件？

核心思想：多条件交叉验证，降低噪音，提高信噪比。

信号分级：
- weak（微弱）：单一条件触发，可能只是噪声
- notable（显著）：2-3个条件同时满足，值得观察
- strong（强烈）：多条件共振，或板块级别异动，高概率有叙事驱动

数据源：Tushare Pro（日线数据 + 板块数据）
"""

import os
import json
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass, field, asdict

import pandas as pd
import tushare as ts

# ─── Configuration ───────────────────────────────────
# Tushare token from environment (never hardcode)
TUSHARE_TOKEN = os.environ.get("TUSHARE_TOKEN", "")

# 数据目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(os.path.dirname(BASE_DIR), "data")
ANOMALY_FILE = os.path.join(REPORTS_DIR, "_anomalies.json")
DASHBOARD_FILE = os.path.join(REPORTS_DIR, "_dashboard.json")

# 尝试从.env文件加载（如果环境变量未设置）
if not TUSHARE_TOKEN:
    env_path = os.path.join(BASE_DIR, ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("TUSHARE_TOKEN="):
                    TUSHARE_TOKEN = line[len("TUSHARE_TOKEN="):].strip()
                    break

# ─── Thresholds ──────────────────────────────────────
# 这些阈值决定了"什么算异动"。调松了噪音多，调严了错过信号。
# 当前设定偏向"宁缺毋滥"。

# 个股阈值
MIN_AMPLITUDE_PCT = 5.0          # 最低振幅（%），低于此忽略
MIN_VOLUME_RATIO = 2.0           # 成交量至少是5日均量的几倍
MIN_CHANGE_PCT = 3.0             # 涨跌幅度至少多少
BREAKOUT_LOOKBACK = 20           # 突破检测向前看多少交易日

# 评分阈值（总分100）
SCORE_NOTABLE = 60               # >=60 算显著异动
SCORE_STRONG = 80                # >=80 算强烈异动

# 板块阈值
MIN_SECTOR_STOCKS = 3            # 板块内至少几只个股异动才算板块异动
MIN_SECTOR_RATIO = 0.30          # 或板块内多少比例的股票大幅波动


# ─── Data Classes ────────────────────────────────────

@dataclass
class StockAnomaly:
    """单只个股的异动记录"""
    code: str
    name: str
    date: str                       # YYYY-MM-DD
    score: int                      # 0-100
    level: str                      # weak / notable / strong
    
    # 原始数据
    close: float
    change_pct: float
    amplitude: float
    volume: float
    vol_ratio: float                # 量比（当日/5日均量）
    
    # 信号详情
    signals: List[Dict] = field(default_factory=list)
    
    # 突破信息
    breakout_type: str = ""         # "high" / "low" / "none"
    breakout_level: float = 0.0     # 突破的价格水平
    
    # 关联信息
    sector: str = ""
    sector_anomaly: bool = False    # 是否伴随板块异动
    
    created_at: str = ""


@dataclass
class SectorAnomaly:
    """板块级别的异动记录"""
    sector: str
    date: str
    score: int
    level: str
    
    # 统计数据
    stock_count: int                # 板块内股票总数
    anomaly_count: int              # 异动个股数
    anomaly_ratio: float            # 异动占比
    avg_change_pct: float           # 板块平均涨跌幅
    avg_volume_ratio: float         # 板块平均量比
    
    # 领涨/领跌
    top_gainer: Optional[Dict] = None
    top_loser: Optional[Dict] = None
    
    signals: List[Dict] = field(default_factory=list)
    created_at: str = ""


# ─── Tushare Client ──────────────────────────────────

class TushareClient:
    """Tushare数据客户端，带缓存和限流"""
    
    def __init__(self):
        self._pro = None
        self._cache = {}          # {key: (timestamp, data)}
        self._cache_ttl = 300     # 缓存5分钟
        self._last_call = 0
        self._min_interval = 0.15  # 最小调用间隔150ms（约4次/秒，Tushare限制500次/分钟）
    
    @property
    def pro(self):
        """延迟初始化，避免导入时触发"""
        if self._pro is None:
            if not TUSHARE_TOKEN:
                raise RuntimeError(
                    "TUSHARE_TOKEN environment variable not set. "
                    "Get one at https://tushare.pro/register"
                )
            ts.set_token(TUSHARE_TOKEN)
            self._pro = ts.pro_api()
        return self._pro
    
    def _throttle(self):
        """限流：避免触发Tushare频率限制"""
        now = time.time()
        elapsed = now - self._last_call
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_call = time.time()
    
    def _cached_call(self, key: str, fetch_fn):
        """带缓存的数据获取"""
        now = time.time()
        if key in self._cache:
            ts_cached, data = self._cache[key]
            if now - ts_cached < self._cache_ttl:
                return data
        self._throttle()
        data = fetch_fn()
        self._cache[key] = (now, data)
        return data
    
    # ─── Public APIs ─────────────────────────────────
    
    def get_daily(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取个股日线数据"""
        key = f"daily_{ts_code}_{start_date}_{end_date}"
        
        def fetch():
            df = self.pro.daily(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date
            )
            return df
        
        return self._cached_call(key, fetch)
    
    def get_daily_batch(self, ts_codes: List[str], start_date: str, end_date: str) -> pd.DataFrame:
        """
        批量获取多只股票日线数据。
        
        Tushare支持ts_code传入逗号分隔的多只股票，
        这样30只股票只需要1次API调用，而不是30次。
        """
        if not ts_codes:
            return pd.DataFrame()
        codes_str = ",".join(ts_codes)
        key = f"daily_batch_{codes_str}_{start_date}_{end_date}"
        
        def fetch():
            df = self.pro.daily(
                ts_code=codes_str,
                start_date=start_date,
                end_date=end_date
            )
            return df
        
        return self._cached_call(key, fetch)
    
    def get_stock_basic(self) -> pd.DataFrame:
        """获取股票基础信息（含行业分类）"""
        key = "stock_basic"
        
        def fetch():
            df = self.pro.stock_basic(
                exchange="",
                list_status="L",
                fields="ts_code,name,industry,market"
            )
            return df
        
        return self._cached_call(key, fetch)
    
    def get_daily_basic(self, trade_date: str) -> pd.DataFrame:
        """获取某交易日的全市场每日指标（用于批量扫描）"""
        key = f"daily_basic_{trade_date}"
        
        def fetch():
            df = self.pro.daily_basic(trade_date=trade_date)
            return df
        
        return self._cached_call(key, fetch)
    
    def get_daily_all(self, trade_date: str) -> pd.DataFrame:
        """获取某交易日的全市场日线数据"""
        key = f"daily_all_{trade_date}"
        
        def fetch():
            df = self.pro.daily(trade_date=trade_date)
            return df
        
        return self._cached_call(key, fetch)
    
    def get_ths_daily(self, trade_date: str) -> pd.DataFrame:
        """获取同花顺行业指数日线（用于板块监控）"""
        key = f"ths_daily_{trade_date}"
        
        def fetch():
            df = self.pro.ths_daily(trade_date=trade_date)
            return df
        
        return self._cached_call(key, fetch)
    
    def get_ths_member(self, ts_code: str) -> pd.DataFrame:
        """获取同花顺行业成分股"""
        key = f"ths_member_{ts_code}"
        
        def fetch():
            df = self.pro.ths_member(ts_code=ts_code)
            return df
        
        return self._cached_call(key, fetch)
    
    def get_trade_cal(self, start_date: str, end_date: str) -> pd.DataFrame:
        """获取交易日历"""
        key = f"trade_cal_{start_date}_{end_date}"
        
        def fetch():
            df = self.pro.trade_cal(
                exchange="SSE",
                start_date=start_date,
                end_date=end_date
            )
            return df
        
        return self._cached_call(key, fetch)


# ─── Anomaly Detector ────────────────────────────────

class AnomalyDetector:
    """
    异动检测器
    
    核心逻辑：
    1. 获取最近N个交易日数据
    2. 计算多个维度的"异常度"
    3. 加权求和得到总分
    4. 根据分数分级（weak / notable / strong）
    
    为什么这样设计：
    - 单一指标容易被操控（如对倒放量但价格不动）
    - 多指标交叉验证大幅提高信噪比
    - 评分制而非二元判断，方便后续筛选
    """
    
    def __init__(self):
        self.client = TushareClient()
    
    # ─── Individual Stock Detection ──────────────────
    
    def detect_stock(
        self,
        ts_code: str,
        trade_date: Optional[str] = None,
        lookback: int = 30,
        df: Optional[pd.DataFrame] = None
    ) -> Optional[StockAnomaly]:
        """
        检测单只个股在指定交易日是否有异动。
        
        Args:
            ts_code: Tushare格式代码，如 "000636.SZ"
            trade_date: 检测日期（YYYYMMDD），None则取最近交易日
            lookback: 向前看多少个交易日（用于计算均线、历史高低点）
            df: 可选，传入已获取的历史数据，避免重复API调用
        
        Returns:
            StockAnomaly if anomaly detected, else None
        """
        # 确定检测日期
        if trade_date is None:
            trade_date = self._latest_trade_date()
        trade_date = trade_date.replace("-", "")
        
        if df is None:
            # 计算查询区间（需要足够多的历史数据）
            end_dt = datetime.strptime(trade_date, "%Y%m%d")
            start_dt = end_dt - timedelta(days=lookback * 2)  # 留足余量过滤非交易日
            start_date = start_dt.strftime("%Y%m%d")
            
            # 获取日线数据
            df = self.client.get_daily(ts_code, start_date, trade_date)
            if df is None or len(df) < 10:
                return None  # 数据不足，跳过
        else:
            # 筛选指定股票的数据
            df = df[df["ts_code"] == ts_code].copy()
            if len(df) < 10:
                return None
        
        df = df.sort_values("trade_date").reset_index(drop=True)
        
        # 提取当日数据
        today = df[df["trade_date"] == trade_date]
        if today.empty:
            return None  # 指定日期无数据（可能是非交易日）
        
        today = today.iloc[0]
        
        # 计算指标
        signals = []
        score = 0
        
        # === 信号1：振幅 ===
        # 原理：振幅反映当日多空博弈激烈程度。
        # 大振幅通常意味着重要信息释放或资金激烈换手。
        amplitude = self._calc_amplitude(today)
        if amplitude >= MIN_AMPLITUDE_PCT:
            amp_score = min(int(amplitude / MIN_AMPLITUDE_PCT * 20), 30)
            score += amp_score
            signals.append({
                "type": "amplitude",
                "value": round(amplitude, 2),
                "score": amp_score,
                "desc": f"振幅{amplitude:.1f}%"
            })
        
        # === 信号2：涨跌幅 ===
        # 原理：单向大幅运动比双向震荡更有方向性意义。
        change_pct = today.get("pct_chg", 0)
        if abs(change_pct) >= MIN_CHANGE_PCT:
            chg_score = min(int(abs(change_pct) / MIN_CHANGE_PCT * 15), 25)
            score += chg_score
            signals.append({
                "type": "change",
                "value": round(change_pct, 2),
                "score": chg_score,
                "desc": f"{'涨' if change_pct > 0 else '跌'}{abs(change_pct):.1f}%"
            })
        
        # === 信号3：成交量放大 ===
        # 原理：价可以骗，量很难骗。
        # 真正的异动通常伴随成交量的显著放大——
        # 意味着大资金真的在进场/离场，不是散户的自嗨。
        vol_ratio = self._calc_volume_ratio(df)
        if vol_ratio >= MIN_VOLUME_RATIO:
            vol_score = min(int(vol_ratio / MIN_VOLUME_RATIO * 15), 25)
            score += vol_score
            signals.append({
                "type": "volume",
                "value": round(vol_ratio, 2),
                "score": vol_score,
                "desc": f"量比{vol_ratio:.1f}倍"
            })
        
        # === 信号4：突破/跌破 ===
        # 原理：价格突破关键位置（如前20日高点）通常意味着趋势转折或加速。
        # 这是技术分析中最经典的信号之一。
        breakout_type, breakout_level, breakout_score = self._detect_breakout(df)
        if breakout_score > 0:
            score += breakout_score
            signals.append({
                "type": "breakout",
                "value": round(breakout_level, 2),
                "score": breakout_score,
                "desc": f"突破{breakout_type} {breakout_level:.2f}"
            })
        
        # === 信号5：连续动量 ===
        # 原理：单日异动可能是偶然，连续多日同向运动意味着趋势确立。
        momentum_score = self._detect_momentum(df)
        if momentum_score > 0:
            score += momentum_score
            signals.append({
                "type": "momentum",
                "value": momentum_score,
                "score": momentum_score,
                "desc": "连续动量"
            })
        
        # 如果没有信号，直接返回
        if not signals or score < SCORE_NOTABLE:
            return None
        
        # 确定级别
        level = "weak" if score < SCORE_NOTABLE else ("strong" if score >= SCORE_STRONG else "notable")
        
        # 获取股票名称
        name = self._get_stock_name(ts_code)
        
        return StockAnomaly(
            code=ts_code,
            name=name,
            date=trade_date[:4] + "-" + trade_date[4:6] + "-" + trade_date[6:],
            score=score,
            level=level,
            close=today.get("close", 0),
            change_pct=change_pct,
            amplitude=amplitude,
            volume=today.get("vol", 0),
            vol_ratio=vol_ratio,
            signals=signals,
            breakout_type=breakout_type,
            breakout_level=breakout_level,
            created_at=datetime.now(timezone.utc).isoformat()
        )
    
    def scan_market(
        self,
        trade_date: Optional[str] = None,
        min_score: int = SCORE_NOTABLE,
        sample_size: Optional[int] = None,
        codes: Optional[List[str]] = None
    ) -> Tuple[List[StockAnomaly], List[SectorAnomaly]]:
        """
        扫描异动。
        
        原理：
        1. 获取当日数据
        2. 对每只股票计算异动评分
        3. 聚合到板块级别
        
        Args:
            trade_date: 扫描日期
            min_score: 最低分数阈值（过滤噪音）
            sample_size: 限制扫描数量（测试用）
            codes: 指定扫描的股票列表，None则扫描全市场
        
        Returns:
            (stock_anomalies, sector_anomalies)
        """
        if trade_date is None:
            trade_date = self._latest_trade_date()
        trade_date_str = trade_date.replace("-", "")
        
        # 获取全市场日线
        df_all = self.client.get_daily_all(trade_date_str)
        if df_all is None or df_all.empty:
            return [], []
        
        # 获取全市场每日指标（含量比）
        df_basic = self.client.get_daily_basic(trade_date_str)
        
        # 合并数据
        if df_basic is not None and not df_basic.empty:
            df_all = df_all.merge(
                df_basic[["ts_code", "volume_ratio"]],
                on="ts_code",
                how="left"
            )
        
        # 获取股票基础信息（行业分类）
        df_basic_info = self.client.get_stock_basic()
        name_map = dict(zip(df_basic_info["ts_code"], df_basic_info["name"])) if df_basic_info is not None else {}
        sector_map = dict(zip(df_basic_info["ts_code"], df_basic_info["industry"])) if df_basic_info is not None else {}
        
        stock_anomalies = []
        sector_data: Dict[str, List[Dict]] = {}  # sector -> list of stock data
        
        # 确定扫描范围
        if codes:
            # 只扫描指定列表
            scan_codes = [c for c in codes if c in df_all["ts_code"].values]
        else:
            # 全市场扫描
            scan_codes = df_all["ts_code"].tolist()
            if sample_size:
                scan_codes = scan_codes[:sample_size]
        
        # 批量获取历史数据（仅指定codes模式）
        # Tushare支持一次传入多只股票，这样30只只需要1次调用
        hist_df = None
        if codes and len(scan_codes) > 0:
            end_dt = datetime.strptime(trade_date_str, "%Y%m%d")
            start_dt = end_dt - timedelta(days=60 * 2)  # 留足余量
            start_date = start_dt.strftime("%Y%m%d")
            hist_df = self.client.get_daily_batch(scan_codes, start_date, trade_date_str)
        
        for ts_code in scan_codes:
            row = df_all[df_all["ts_code"] == ts_code]
            if row.empty:
                continue
            
            row = row.iloc[0]
            
            # 快速过滤：先排除明显不可能异动的
            amplitude = self._calc_amplitude_from_row(row)
            change_pct = row.get("pct_chg", 0) or 0
            
            if abs(change_pct) < 2 and amplitude < 4:
                continue  # 快速跳过，节省API调用
            
            # 需要历史数据做深度检测
            # 如果有批量获取的数据，直接传入避免重复调用
            anomaly = self.detect_stock(ts_code, trade_date, df=hist_df)
            
            if anomaly and anomaly.score >= min_score:
                # 补充名称和行业
                anomaly.name = name_map.get(ts_code, anomaly.name)
                anomaly.sector = sector_map.get(ts_code, "")
                stock_anomalies.append(anomaly)
                
                # 收集板块数据
                sector = anomaly.sector or "其他"
                if sector not in sector_data:
                    sector_data[sector] = []
                sector_data[sector].append({
                    "code": ts_code,
                    "name": anomaly.name,
                    "change_pct": anomaly.change_pct,
                    "score": anomaly.score,
                    "vol_ratio": anomaly.vol_ratio
                })
        
        # 检测板块异动
        sector_anomalies = self._detect_sectors(sector_data, trade_date)
        
        # 标记个股是否伴随板块异动
        for sa in stock_anomalies:
            for sec_a in sector_anomalies:
                if sa.sector == sec_a.sector and sec_a.level in ("notable", "strong"):
                    sa.sector_anomaly = True
                    break
        
        # 按分数排序
        stock_anomalies.sort(key=lambda x: x.score, reverse=True)
        sector_anomalies.sort(key=lambda x: x.score, reverse=True)
        
        return stock_anomalies, sector_anomalies
    
    # ─── Sector Detection ────────────────────────────
    
    def _detect_sectors(
        self,
        sector_data: Dict[str, List[Dict]],
        trade_date: str
    ) -> List[SectorAnomaly]:
        """
        检测板块级别异动。
        
        原理：
        板块异动 > 个股异动。
        如果同一板块内多只个股同时异动，
        说明这不是个股行为，而是行业/主题级别的资金流动。
        这种信号的可信度和持续性远高于孤立个股。
        """
        sector_anomalies = []
        
        for sector, stocks in sector_data.items():
            if len(stocks) < 2:
                continue  # 板块内异动股太少，可能是巧合
            
            score = 0
            signals = []
            
            # 统计指标
            stock_count = len(stocks)
            avg_change = sum(s["change_pct"] for s in stocks) / stock_count
            avg_vol = sum(s.get("vol_ratio", 1) for s in stocks) / stock_count
            
            # 信号1：板块内异动股数量
            # 原理：越多股票同时异动，越不可能是偶然
            if stock_count >= MIN_SECTOR_STOCKS:
                count_score = min(stock_count * 10, 30)
                score += count_score
                signals.append({
                    "type": "count",
                    "value": stock_count,
                    "score": count_score,
                    "desc": f"{stock_count}只个股异动"
                })
            
            # 信号2：板块内异动股占比
            # 需要知道板块总股票数，这里用估计值
            # 实际应用中可以从数据库/缓存获取
            
            # 信号3：板块平均涨跌幅
            if abs(avg_change) >= 3:
                chg_score = min(int(abs(avg_change) / 3 * 15), 25)
                score += chg_score
                signals.append({
                    "type": "avg_change",
                    "value": round(avg_change, 2),
                    "score": chg_score,
                    "desc": f"板块平均{'涨' if avg_change > 0 else '跌'}{abs(avg_change):.1f}%"
                })
            
            # 信号4：板块平均量比
            if avg_vol >= 1.5:
                vol_score = min(int(avg_vol / 1.5 * 10), 20)
                score += vol_score
                signals.append({
                    "type": "avg_volume",
                    "value": round(avg_vol, 2),
                    "score": vol_score,
                    "desc": f"板块平均量比{avg_vol:.1f}"
                })
            
            # 信号5：方向一致性
            # 原理：如果板块内异动股全部同向（全涨或全跌），
            # 说明资金有明确的行业偏好/厌恶
            up_count = sum(1 for s in stocks if s["change_pct"] > 0)
            down_count = stock_count - up_count
            consistency = max(up_count, down_count) / stock_count
            
            if consistency >= 0.8:
                cons_score = 15
                score += cons_score
                direction = "涨" if up_count > down_count else "跌"
                signals.append({
                    "type": "consistency",
                    "value": round(consistency, 2),
                    "score": cons_score,
                    "desc": f"方向一致：{up_count}涨{down_count}跌"
                })
            
            if score >= SCORE_NOTABLE:
                level = "strong" if score >= SCORE_STRONG else "notable"
                
                # 找领涨/领跌
                sorted_stocks = sorted(stocks, key=lambda x: x["change_pct"], reverse=True)
                top_gainer = sorted_stocks[0] if sorted_stocks and sorted_stocks[0]["change_pct"] > 0 else None
                top_loser = sorted_stocks[-1] if sorted_stocks and sorted_stocks[-1]["change_pct"] < 0 else None
                
                sector_anomalies.append(SectorAnomaly(
                    sector=sector,
                    date=trade_date,
                    score=score,
                    level=level,
                    stock_count=stock_count,
                    anomaly_count=stock_count,
                    anomaly_ratio=0.0,  # 需要板块总股票数才能计算
                    avg_change_pct=avg_change,
                    avg_volume_ratio=avg_vol,
                    top_gainer=top_gainer,
                    top_loser=top_loser,
                    signals=signals,
                    created_at=datetime.now(timezone.utc).isoformat()
                ))
        
        return sector_anomalies
    
    # ─── Helper Methods ──────────────────────────────
    
    def _latest_trade_date(self) -> str:
        """获取最近一个交易日"""
        today = datetime.now().strftime("%Y%m%d")
        df = self.client.get_trade_cal(today, today)
        if df is not None and not df.empty:
            # 找最近的交易日
            trade_dates = df[df["is_open"] == 1]["cal_date"].tolist()
            if trade_dates:
                return max(trade_dates)
        # Fallback：如果今天已经收盘，返回今天；否则返回昨天
        now = datetime.now()
        if now.hour >= 15:
            return now.strftime("%Y%m%d")
        else:
            return (now - timedelta(days=1)).strftime("%Y%m%d")
    
    def _calc_amplitude(self, row) -> float:
        """计算振幅（%）"""
        high = row.get("high", 0)
        low = row.get("low", 0)
        pre_close = row.get("pre_close", 0)
        if pre_close and pre_close > 0:
            return (high - low) / pre_close * 100
        return 0
    
    def _calc_amplitude_from_row(self, row) -> float:
        """从DataFrame row计算振幅"""
        return self._calc_amplitude(row)
    
    def _calc_volume_ratio(self, df: pd.DataFrame) -> float:
        """
        计算量比（当日成交量 / 近5日平均成交量）
        
        原理：量比是判断资金活跃度的核心指标。
        量比>2 意味着当日成交量是平时的两倍以上，
        通常伴随着重要信息的释放或大资金的介入。
        """
        if len(df) < 6:
            return 1.0
        
        today_vol = df.iloc[-1]["vol"]
        past_5_avg = df.iloc[-6:-1]["vol"].mean()
        
        if past_5_avg and past_5_avg > 0:
            return today_vol / past_5_avg
        return 1.0
    
    def _detect_breakout(self, df: pd.DataFrame) -> Tuple[str, float, int]:
        """
        检测是否突破近期高低点。
        
        原理：
        - 突破前N日高点：意味着买方力量突破了近期阻力位，
          通常会吸引更多跟风盘，形成正向反馈。
        - 跌破前N日低点：意味着卖方力量击溃了近期支撑位，
          可能触发连锁止损。
        
        Returns: (type, level, score)
            type: "high" | "low" | "none"
        """
        if len(df) < BREAKOUT_LOOKBACK + 1:
            return "none", 0, 0
        
        today = df.iloc[-1]
        history = df.iloc[-(BREAKOUT_LOOKBACK + 1):-1]
        
        high_20 = history["high"].max()
        low_20 = history["low"].min()
        
        close = today["close"]
        
        # 突破前20日高点
        if close > high_20:
            # 计算突破幅度
            breakout_pct = (close - high_20) / high_20 * 100
            score = min(int(breakout_pct * 5) + 10, 25)
            return "high", high_20, score
        
        # 跌破前20日低点
        if close < low_20:
            breakout_pct = (low_20 - close) / low_20 * 100
            score = min(int(breakout_pct * 5) + 10, 25)
            return "low", low_20, score
        
        return "none", 0, 0
    
    def _detect_momentum(self, df: pd.DataFrame) -> int:
        """
        检测连续动量。
        
        原理：
        连续N个交易日同向运动（连涨/连跌），
        意味着趋势正在自我强化。
        这种动量通常不会突然停止，而是会持续一段时间。
        
        评分：
        - 连续2日：+5
        - 连续3日：+10
        - 连续4日及以上：+15
        """
        if len(df) < 3:
            return 0
        
        changes = df["pct_chg"].tolist()
        
        # 从最近一日向前数
        direction = 1 if changes[-1] > 0 else -1
        streak = 1
        
        for i in range(len(changes) - 2, -1, -1):
            if (changes[i] > 0 and direction > 0) or (changes[i] < 0 and direction < 0):
                streak += 1
            else:
                break
        
        if streak >= 4:
            return 15
        elif streak == 3:
            return 10
        elif streak == 2:
            return 5
        return 0
    
    def _get_stock_name(self, ts_code: str) -> str:
        """从缓存或API获取股票名称"""
        df = self.client.get_stock_basic()
        if df is not None:
            row = df[df["ts_code"] == ts_code]
            if not row.empty:
                return row.iloc[0]["name"]
        return ts_code


# ─── Persistence ─────────────────────────────────────

def load_anomalies() -> Dict:
    """加载已保存的异动记录"""
    if os.path.exists(ANOMALY_FILE):
        try:
            with open(ANOMALY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {"daily": {}, "weekly": {}, "last_scan": None}


def save_anomalies(data: Dict):
    """保存异动记录"""
    os.makedirs(os.path.dirname(ANOMALY_FILE), exist_ok=True)
    with open(ANOMALY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def add_daily_anomalies(
    date: str,
    stocks: List[StockAnomaly],
    sectors: List[SectorAnomaly]
):
    """添加某日的异动记录"""
    data = load_anomalies()
    
    data["daily"][date] = {
        "stocks": [asdict(s) for s in stocks],
        "sectors": [asdict(s) for s in sectors],
        "stock_count": len(stocks),
        "sector_count": len(sectors),
        "scanned_at": datetime.now(timezone.utc).isoformat()
    }
    
    save_anomalies(data)


def get_daily_anomalies(date: str) -> Dict:
    """获取某日的异动记录"""
    data = load_anomalies()
    return data["daily"].get(date, {"stocks": [], "sectors": []})


def get_all_dates() -> List[str]:
    """获取所有有记录的日期，从新到旧排序"""
    data = load_anomalies()
    dates = list(data["daily"].keys())
    return sorted(dates, reverse=True)


# ─── Weekly Aggregation ──────────────────────────────

def aggregate_weekly(date_str: str) -> Dict:
    """
    汇总某周（以date_str所在周为单位）的异动统计。
    
    返回：
    {
        "week_start": "YYYY-MM-DD",
        "week_end": "YYYY-MM-DD",
        "total_stock_anomalies": int,
        "total_sector_anomalies": int,
        "top_sectors": [...],
        "top_stocks": [...],
        "daily_breakdown": {...}
    }
    """
    date = datetime.strptime(date_str, "%Y-%m-%d")
    # 找到本周周一
    week_start = date - timedelta(days=date.weekday())
    week_end = week_start + timedelta(days=6)
    
    week_start_str = week_start.strftime("%Y-%m-%d")
    week_end_str = week_end.strftime("%Y-%m-%d")
    
    data = load_anomalies()
    
    total_stocks = 0
    total_sectors = 0
    sector_counter = {}
    stock_counter = {}
    daily_breakdown = {}
    
    for d, record in data["daily"].items():
        d_dt = datetime.strptime(d, "%Y-%m-%d")
        if week_start <= d_dt <= week_end:
            stocks = record.get("stocks", [])
            sectors = record.get("sectors", [])
            
            total_stocks += len(stocks)
            total_sectors += len(sectors)
            
            for s in stocks:
                key = s["code"]
                stock_counter[key] = stock_counter.get(key, 0) + 1
            
            for s in sectors:
                key = s["sector"]
                sector_counter[key] = sector_counter.get(key, 0) + 1
            
            daily_breakdown[d] = {
                "stock_count": len(stocks),
                "sector_count": len(sectors)
            }
    
    top_sectors = sorted(
        [{"sector": k, "count": v} for k, v in sector_counter.items()],
        key=lambda x: x["count"],
        reverse=True
    )[:10]
    
    top_stocks = sorted(
        [{"code": k, "count": v} for k, v in stock_counter.items()],
        key=lambda x: x["count"],
        reverse=True
    )[:10]
    
    return {
        "week_start": week_start_str,
        "week_end": week_end_str,
        "total_stock_anomalies": total_stocks,
        "total_sector_anomalies": total_sectors,
        "top_sectors": top_sectors,
        "top_stocks": top_stocks,
        "daily_breakdown": daily_breakdown
    }


# ─── Main Entry Point ────────────────────────────────

def run_daily_scan(trade_date: Optional[str] = None, sample_size: Optional[int] = None, codes: Optional[List[str]] = None) -> Dict:
    """
    执行每日异动扫描。
    
    这是主入口函数，建议通过cron在每日收盘后（15:30后）调用。
    
    Args:
        trade_date: 扫描日期（YYYY-MM-DD），None则自动判断
        sample_size: 限制扫描数量（测试用）
        codes: 指定扫描的股票代码列表，None则扫描全市场
    
    Returns:
        扫描结果摘要
    """
    detector = AnomalyDetector()
    
    if trade_date is None:
        trade_date = detector._latest_trade_date()
        trade_date = trade_date[:4] + "-" + trade_date[4:6] + "-" + trade_date[6:]
    
    # 先尝试获取当日全市场数据，确认数据是否可用
    trade_date_str = trade_date.replace("-", "")
    df_test = detector.client.get_daily_all(trade_date_str)
    
    # 如果指定日期没有数据，回退到最近有数据的交易日
    if df_test is None or df_test.empty:
        print(f"[AnomalyScan] No data for {trade_date}, falling back to latest available...")
        # 尝试前5个交易日
        for i in range(1, 6):
            fallback = (datetime.strptime(trade_date, "%Y-%m-%d") - timedelta(days=i)).strftime("%Y%m%d")
            df_test = detector.client.get_daily_all(fallback)
            if df_test is not None and not df_test.empty:
                trade_date = fallback[:4] + "-" + fallback[4:6] + "-" + fallback[6:]
                print(f"[AnomalyScan] Using fallback date: {trade_date}")
                break
    
    scope = f"{len(codes)} tracked stocks" if codes else "full market"
    print(f"[AnomalyScan] Starting scan for {trade_date} ({scope})...")
    
    stocks, sectors = detector.scan_market(trade_date, sample_size=sample_size, codes=codes)
    
    # 保存结果
    add_daily_anomalies(trade_date, stocks, sectors)
    
    # 生成本周汇总
    weekly = aggregate_weekly(trade_date)
    
    # 保存周汇总
    data = load_anomalies()
    week_key = weekly["week_start"]
    data["weekly"][week_key] = weekly
    save_anomalies(data)
    
    result = {
        "date": trade_date,
        "stocks_found": len(stocks),
        "sectors_found": len(sectors),
        "strong_signals": len([s for s in stocks if s.level == "strong"]),
        "notable_signals": len([s for s in stocks if s.level == "notable"]),
        "weekly_summary": {
            "week": f"{weekly['week_start']} ~ {weekly['week_end']}",
            "total_this_week": weekly["total_stock_anomalies"],
            "top_sectors": [s["sector"] for s in weekly["top_sectors"][:5]]
        }
    }
    
    print(f"[AnomalyScan] Done. Found {len(stocks)} stock anomalies, {len(sectors)} sector anomalies.")
    
    return result


# ─── CLI ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    
    # 简单CLI支持
    if len(sys.argv) > 1 and sys.argv[1] == "scan":
        date = sys.argv[2] if len(sys.argv) > 2 else None
        sample = int(sys.argv[3]) if len(sys.argv) > 3 else None
        result = run_daily_scan(date, sample_size=sample)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("Usage: python anomaly.py scan [YYYY-MM-DD] [sample_size]")
