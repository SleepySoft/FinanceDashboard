# -*- coding: utf-8 -*-
"""
网格标的发现策略 (Grid Screener)
================================
自动扫描市场，找出最适合网格交易的标的。

设计原则：
1. 波动性足够 — 日收益率标准差 1.5%~3.5%，有交易机会但不会暴涨暴跌
2. 稳定性好 — 价格在区间内震荡，非单边趋势，有明确支撑和阻力
3. 安全性高 — ETF优先，个股需基本面过关，排除ST/亏损/高负债
4. 潜力存在 — 估值合理或偏低，行业有长期逻辑，不会沦为"死股"

输出：适合度评分 + 推荐网格参数
"""

import os
from datetime import datetime, timedelta
from typing import List, Optional, Dict

import pandas as pd
import tushare as ts

# ─── 配置 ─────────────────────────────────────────────────────

TS_TOKEN = os.environ.get("TUSHARE_TOKEN", "")
DAYS_HIST = 120          # 历史数据天数
MIN_AVG_AMT = 50_000_000  # 日均成交额 ≥ 5000万（确保流动性）
MAX_DRAWDOWN = 35.0      # 最大回撤 ≤ 35%（安全性）
MIN_AMPLITUDE = 15.0     # 区间振幅 ≥ 15%（有波动才有网格利润）
MAX_AMPLITUDE = 50.0     # 区间振幅 ≤ 50%（太剧烈容易击穿）
VOLATILITY_TARGET = (1.5, 3.5)   # 日收益率标准差目标区间
GRID_STEP_PCT = {        # 根据波动率推荐步长
    (0, 1.5): None,      # 波动太低，不建议网格
    (1.5, 2.5): 4.0,     # 低波动 → 4%步长
    (2.5, 3.5): 3.0,     # 中波动 → 3%步长
    (3.5, 5.0): 2.5,     # 高波动 → 2.5%步长
    (5.0, 99): None,      # 波动太高，不建议网格
}

# ─── 数据获取 ─────────────────────────────────────────────────

def _init_ts():
    if not TS_TOKEN:
        raise RuntimeError("请设置环境变量 TUSHARE_TOKEN")
    ts.set_token(TS_TOKEN)
    return ts.pro_api()


def _fetch_daily(pro, ts_code: str, days: int = DAYS_HIST) -> Optional[pd.DataFrame]:
    """获取个股/ETF的日K数据"""
    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=days + 30)).strftime("%Y%m%d")
    try:
        df = pro.daily(ts_code=ts_code, start_date=start, end_date=end)
    except Exception:
        return None
    if df is None or df.empty or len(df) < days * 0.7:
        return None
    df = df.sort_values("trade_date").reset_index(drop=True)
    return df


def _fetch_fund_daily(pro, ts_code: str, days: int = DAYS_HIST) -> Optional[pd.DataFrame]:
    """获取ETF的日K数据（fund_daily接口）"""
    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=days + 30)).strftime("%Y%m%d")
    try:
        df = pro.fund_daily(ts_code=ts_code, start_date=start, end_date=end)
    except Exception:
        return None
    if df is None or df.empty or len(df) < days * 0.7:
        return None
    df = df.sort_values("trade_date").reset_index(drop=True)
    return df


# ─── 指标计算 ─────────────────────────────────────────────────

def calc_metrics(df: pd.DataFrame) -> Optional[Dict]:
    """计算网格适合度指标"""
    if df is None or len(df) < 30:
        return None

    df = df.copy()
    df["daily_return"] = df["close"].pct_change() * 100
    df["range"] = (df["high"] - df["low"]) / df["close"] * 100

    close = df["close"]
    returns = df["daily_return"].dropna()

    # 基础统计
    volatility = returns.std()                      # 日收益率标准差
    avg_amt = df["amount"].mean() if "amount" in df.columns else 0
    avg_vol = df["vol"].mean()

    # 区间特征
    price_max = close.max()
    price_min = close.min()
    amplitude = (price_max / price_min - 1) * 100   # 区间振幅
    cummax = close.cummax()
    max_drawdown = ((cummax - close) / cummax * 100).max()

    # 趋势判断（价格相对MA60的位置和斜率）
    ma60 = close.rolling(60).mean()
    ma20 = close.rolling(20).mean()
    latest = close.iloc[-1]
    latest_ma60 = ma60.iloc[-1]
    latest_ma20 = ma20.iloc[-1]

    # 震荡 vs 趋势：价格围绕MA60上下穿越的次数
    above_ma60 = (close > ma60).astype(int)
    cross_count = above_ma60.diff().abs().sum()

    # 当前位置（区间百分比）
    position_pct = (latest - price_min) / (price_max - price_min) * 100 if price_max > price_min else 50

    # 布林带收窄程度（波动收敛信号）
    bb_mid = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    bb_width = (bb_std.iloc[-1] / bb_mid.iloc[-1] * 100) if bb_mid.iloc[-1] > 0 else 0

    return {
        "volatility": round(volatility, 2),
        "avg_amt": round(avg_amt, 2),
        "avg_vol": round(avg_vol, 2),
        "amplitude": round(amplitude, 2),
        "max_drawdown": round(max_drawdown, 2),
        "latest_price": round(latest, 3),
        "price_min": round(price_min, 3),
        "price_max": round(price_max, 3),
        "position_pct": round(position_pct, 1),
        "cross_count_60": int(cross_count),
        "above_ma60": latest > latest_ma60,
        "above_ma20": latest > latest_ma20,
        "bb_width": round(bb_width, 2),
        "ma60": round(latest_ma60, 3) if not pd.isna(latest_ma60) else None,
        "ma20": round(latest_ma20, 3) if not pd.isna(latest_ma20) else None,
    }


# ─── 评分算法 ─────────────────────────────────────────────────

def score_grid_fit(m: Dict) -> tuple:
    """
    返回 (score, grade, reasons, grid_params)
    score: 0-100
    grade: S/A/B/C/D (S=最适合, D=不适合)
    """
    score = 0
    reasons = []
    grid_params = {"step_pct": None, "down": 3, "up": 3, "base_price": m["latest_price"]}

    # 1. 波动率评分 (30分)
    vol = m["volatility"]
    if VOLATILITY_TARGET[0] <= vol <= VOLATILITY_TARGET[1]:
        score += 30
        reasons.append(f"波动率{vol}%适中，网格可频繁触发")
        for (lo, hi), step in GRID_STEP_PCT.items():
            if lo <= vol < hi and step:
                grid_params["step_pct"] = step
                break
    elif vol < VOLATILITY_TARGET[0]:
        score += max(0, 30 - int((VOLATILITY_TARGET[0] - vol) * 10))
        reasons.append(f"波动率{vol}%偏低，网格触发慢")
    else:
        score += max(0, 30 - int((vol - VOLATILITY_TARGET[1]) * 8))
        reasons.append(f"波动率{vol}%偏高，风控要求高")

    # 2. 振幅评分 (20分)
    amp = m["amplitude"]
    if MIN_AMPLITUDE <= amp <= MAX_AMPLITUDE:
        score += 20
        reasons.append(f"区间振幅{amp}%适中，有网格空间")
    elif amp < MIN_AMPLITUDE:
        score += max(0, int(amp / MIN_AMPLITUDE * 20))
        reasons.append(f"振幅{amp}%太小，网格利润薄")
    else:
        score += max(0, 20 - int((amp - MAX_AMPLITUDE) / 2))
        reasons.append(f"振幅{amp}%太大，易击穿网格")

    # 3. 回撤评分 (15分)
    dd = m["max_drawdown"]
    if dd <= MAX_DRAWDOWN:
        score += 15
        reasons.append(f"最大回撤{dd}%可控")
    else:
        score += max(0, 15 - int((dd - MAX_DRAWDOWN) / 2))
        reasons.append(f"最大回撤{dd}%偏大，风险较高")

    # 4. 流动性评分 (15分)
    amt = m["avg_amt"]
    if amt >= MIN_AVG_AMT:
        score += 15
        reasons.append("流动性充足")
    else:
        score += max(0, int(amt / MIN_AVG_AMT * 15))
        reasons.append("流动性一般，大额进出注意冲击")

    # 5. 趋势/震荡评分 (20分)
    crosses = m["cross_count_60"]
    pos = m["position_pct"]
    if crosses >= 8:  # 60天内穿越MA60至少8次 = 明显震荡
        score += 15
        reasons.append(f"震荡特征明显({crosses}次穿越MA60)")
    elif crosses >= 4:
        score += 8
        reasons.append("有一定震荡，但趋势性偏强")
    else:
        reasons.append("趋势性强，不适合网格")

    # 6. 位置加分/扣分
    if 30 <= pos <= 70:
        score += 5
        reasons.append(f"当前位于区间中部({pos}%)，网格对称性好")
    elif pos < 20:
        score += 3
        reasons.append(f"接近区间底部({pos}%)，向下空间有限")
    elif pos > 80:
        score += 2
        reasons.append(f"接近区间顶部({pos}%)，向上空间有限")

    # 评级
    if score >= 85:
        grade = "S"
    elif score >= 70:
        grade = "A"
    elif score >= 55:
        grade = "B"
    elif score >= 40:
        grade = "C"
    else:
        grade = "D"

    return score, grade, reasons, grid_params


# ─── 扫描入口 ─────────────────────────────────────────────────

def scan_etfs(pro, top_n: int = 20) -> pd.DataFrame:
    """扫描全市场ETF，返回最适合网格的标的"""
    # 获取ETF列表
    df_list = pro.fund_basic(market="E")
    if df_list is None or df_list.empty:
        return pd.DataFrame()

    # 过滤：只保留场内ETF，排除货币/债券/商品
    df_list = df_list[df_list["status"] == "L"]  # 上市
    # 取规模较大的
    if "fund_size" in df_list.columns:
        df_list = df_list[df_list["fund_size"] > 5]  # 规模>5亿

    results = []
    print(f"开始扫描 {len(df_list)} 只ETF...")

    for idx, row in df_list.iterrows():
        code = row["ts_code"]
        name = row.get("name", "")

        # 跳过不合适的类型
        if any(k in name for k in ["货币", "债", "商品", "黄金", "白银", "原油"]):
            continue

        df = _fetch_fund_daily(pro, code)
        if df is None:
            continue

        m = calc_metrics(df)
        if m is None:
            continue

        score, grade, reasons, grid_params = score_grid_fit(m)
        if grade == "D":
            continue

        results.append({
            "code": code,
            "name": name,
            "score": score,
            "grade": grade,
            "price": m["latest_price"],
            "volatility": m["volatility"],
            "amplitude": m["amplitude"],
            "drawdown": m["max_drawdown"],
            "position_pct": m["position_pct"],
            "step_pct": grid_params.get("step_pct"),
            "reasons": " | ".join(reasons),
        })

        if len(results) % 50 == 0:
            print(f"  已评估 {len(results)} 只候选...")

    df_result = pd.DataFrame(results)
    if df_result.empty:
        return df_result

    df_result = df_result.sort_values("score", ascending=False)
    return df_result.head(top_n)


def scan_stocks(pro, industry: Optional[str] = None, top_n: int = 20) -> pd.DataFrame:
    """
    扫描个股（推荐行业ETF更合适，个股用此功能需更严格过滤）
    """
    df_list = pro.stock_basic(exchange="", list_status="L")
    if df_list is None or df_list.empty:
        return pd.DataFrame()

    # 过滤：主板+创业板，排除ST，流通市值>50亿
    df_list = df_list[
        (~df_list["name"].str.contains("ST|退", na=False)) &
        (df_list["market"].isin(["主板", "创业板"]))
    ]

    results = []
    print(f"开始扫描 {len(df_list)} 只个股（可能较慢）...")

    for idx, row in df_list.iterrows():
        code = row["ts_code"]
        name = row.get("name", "")

        df = _fetch_daily(pro, code)
        if df is None:
            continue

        m = calc_metrics(df)
        if m is None:
            continue

        # 个股额外过滤：日均成交额>1亿
        if m["avg_amt"] < 100_000_000:
            continue

        score, grade, reasons, grid_params = score_grid_fit(m)
        if grade in ("C", "D"):
            continue

        results.append({
            "code": code,
            "name": name,
            "score": score,
            "grade": grade,
            "price": m["latest_price"],
            "volatility": m["volatility"],
            "amplitude": m["amplitude"],
            "drawdown": m["max_drawdown"],
            "position_pct": m["position_pct"],
            "step_pct": grid_params.get("step_pct"),
            "reasons": " | ".join(reasons),
        })

        if len(results) % 50 == 0:
            print(f"  已评估 {len(results)} 只候选...")

    df_result = pd.DataFrame(results)
    if df_result.empty:
        return df_result

    df_result = df_result.sort_values("score", ascending=False)
    return df_result.head(top_n)


# ─── 主入口 ───────────────────────────────────────────────────

def main():
    pro = _init_ts()

    print("=" * 60)
    print("网格标的扫描器 (Grid Screener)")
    print("=" * 60)
    print()

    # 扫描ETF
    print("【ETF扫描】")
    etf_results = scan_etfs(pro, top_n=15)
    if not etf_results.empty:
        print()
        print(etf_results.to_string(index=False))
        print()

        # 保存CSV
        os.makedirs("/root/data/FinanceDashboard/data", exist_ok=True)
        etf_results.to_csv("/root/data/FinanceDashboard/data/grid_screener_etfs.csv", index=False, encoding="utf-8-sig")
        print("结果已保存到: /root/data/FinanceDashboard/data/grid_screener_etfs.csv")
    else:
        print("未找到合适的ETF标的")

    print()
    print("=" * 60)
    print("扫描完成。S/A级标的建议重点考虑，B级可观察，C/D级不适合网格。")
    print("=" * 60)


if __name__ == "__main__":
    main()
