"""基于因子的简单条件回测

用户选择因子 + 设置判断条件（阈值），直接生成信号并回测。
无需编写策略代码。
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from dataclasses import dataclass

from backtest.factors import FactorEngine
from backtest.engine import BacktestEngine, BacktestConfig


@dataclass
class Condition:
    """单条判断条件"""
    factor_id: str
    params: dict
    operator: str  # < > <= >= == cross_above cross_below
    value: float

    def to_dict(self):
        return {
            'factor_id': self.factor_id,
            'params': self.params,
            'operator': self.operator,
            'value': self.value,
        }

    @classmethod
    def from_dict(cls, d: dict):
        return cls(
            factor_id=d['factor_id'],
            params=d.get('params', {}),
            operator=d['operator'],
            value=d['value'],
        )


def evaluate_condition(data: pd.DataFrame, condition: Condition) -> pd.Series:
    """
    评估单条条件，返回布尔序列

    Args:
        data: DataFrame 包含因子列 (index=date, columns=因子名)
        condition: 条件定义
    """
    # 构建因子列名
    col_name = _factor_column_name(condition.factor_id, condition.params)
    if col_name not in data.columns:
        raise ValueError(f"Factor column '{col_name}' not found in data. Available: {list(data.columns)}")

    values = data[col_name]
    op = condition.operator
    threshold = condition.value

    if op == '<':
        return values < threshold
    elif op == '<=':
        return values <= threshold
    elif op == '>':
        return values > threshold
    elif op == '>=':
        return values >= threshold
    elif op == '==':
        return values == threshold
    elif op == 'cross_above':
        # 当日值 > threshold 且 前一日 <= threshold
        return (values > threshold) & (values.shift(1) <= threshold)
    elif op == 'cross_below':
        # 当日值 < threshold 且 前一日 >= threshold
        return (values < threshold) & (values.shift(1) >= threshold)
    else:
        raise ValueError(f"Unknown operator: {op}")


def _factor_column_name(factor_id: str, params: dict) -> str:
    """构建因子列名"""
    if params:
        param_str = '_'.join(f"{k}{v}" for k, v in sorted(params.items()))
        return f"{factor_id}_{param_str}"
    return factor_id


def build_signal_from_conditions(
    data: pd.DataFrame,
    buy_conditions: List[Condition],
    sell_conditions: List[Condition],
    logic: str = 'and'  # 'and' = 全部满足, 'or' = 任一满足
) -> pd.Series:
    """
    根据买卖条件构建信号序列

    Args:
        data: 包含因子列的 DataFrame
        buy_conditions: 买入条件列表
        sell_conditions: 卖出条件列表
        logic: 条件组合逻辑

    Returns:
        signal Series: 1=买入, -1=卖出, 0=无
    """
    signal = pd.Series(0, index=data.index)

    # 计算买入信号
    if buy_conditions:
        buy_signals = []
        for cond in buy_conditions:
            buy_signals.append(evaluate_condition(data, cond))

        if logic == 'and':
            buy_mask = pd.concat(buy_signals, axis=1).all(axis=1)
        else:
            buy_mask = pd.concat(buy_signals, axis=1).any(axis=1)
        signal[buy_mask] = 1

    # 计算卖出信号（覆盖买入）
    if sell_conditions:
        sell_signals = []
        for cond in sell_conditions:
            sell_signals.append(evaluate_condition(data, cond))

        if logic == 'and':
            sell_mask = pd.concat(sell_signals, axis=1).all(axis=1)
        else:
            sell_mask = pd.concat(sell_signals, axis=1).any(axis=1)
        signal[sell_mask] = -1

    return signal


class FactorBacktestRunner:
    """因子条件回测执行器"""

    def __init__(self, factor_engine: FactorEngine = None):
        self.factor_engine = factor_engine

    def run(
        self,
        code: str,
        buy_conditions: List[Condition],
        sell_conditions: List[Condition],
        start: str,
        end: str,
        adjust: str = 'qfq',
        config: BacktestConfig = None,
        logic: str = 'and',
    ) -> dict:
        """
        执行因子条件回测

        Returns:
            同 BacktestEngine.run() 格式
        """
        config = config or BacktestConfig()

        # 1. 收集所有需要的因子
        all_factors = []
        for cond in buy_conditions + sell_conditions:
            alias = _factor_column_name(cond.factor_id, cond.params)
            all_factors.append({
                'factor_id': cond.factor_id,
                'params': cond.params,
                'alias': alias,
            })

        # 2. 批量计算因子
        factor_df = self.factor_engine.compute_multi(code, all_factors, start, end, adjust)
        if factor_df.empty:
            return {'error': 'No factor data available'}

        # 3. 生成信号
        signals = build_signal_from_conditions(factor_df, buy_conditions, sell_conditions, logic)

        # 4. 获取价格数据
        price_data = self.factor_engine.data_source.get_daily_bars(code, start, end, adjust)

        # 5. 拼接信号和价格
        price_data['signal'] = signals.reindex(price_data.index, fill_value=0)

        # 6. 回测
        engine = BacktestEngine(config)

        # 用 pandas fallback 方式回测（更灵活，不需要 vectorbt）
        return self._run_with_signals(price_data, config)

    def _run_with_signals(self, data: pd.DataFrame, config: BacktestConfig) -> dict:
        """基于信号序列执行回测（纯 pandas）"""
        cash = config.initial_cash
        position = 0
        avg_cost = 0.0
        equity_curve = []
        trades = []
        max_equity = cash
        max_dd = 0.0

        for date, row in data.iterrows():
            close = row['close']
            signal = row.get('signal', 0)

            if signal == 1 and position <= 0:
                invest = cash * config.size
                qty = int(invest / close)
                cost = qty * close * (1 + config.commission)
                if cash >= cost and qty > 0:
                    position = qty
                    avg_cost = close
                    cash -= cost
                    trades.append({
                        'entry_date': str(date)[:10],
                        'entry_price': round(close, 3),
                        'quantity': qty,
                        'side': 'long',
                    })

            elif signal == -1 and position > 0:
                revenue = position * close * (1 - config.commission)
                pnl = position * (close - avg_cost)
                cash += revenue
                if trades:
                    trades[-1].update({
                        'exit_date': str(date)[:10],
                        'exit_price': round(close, 3),
                        'pnl': round(pnl, 2),
                        'pnl_pct': round((close - avg_cost) / avg_cost * 100, 2) if avg_cost > 0 else 0,
                    })
                position = 0
                avg_cost = 0

            equity = cash + position * close
            max_equity = max(max_equity, equity)
            dd = (equity - max_equity) / max_equity
            max_dd = min(max_dd, dd)

            equity_curve.append({
                'date': str(date)[:10],
                'value': round(equity, 2),
            })

        total_return = (equity_curve[-1]['value'] - config.initial_cash) / config.initial_cash if equity_curve else 0
        completed_trades = [t for t in trades if 'exit_date' in t]
        win_trades = [t for t in completed_trades if t.get('pnl', 0) > 0]
        lose_trades = [t for t in completed_trades if t.get('pnl', 0) <= 0]

        metrics = {
            'total_return': round(total_return, 4),
            'max_drawdown': round(max_dd, 4),
            'win_rate': round(len(win_trades) / len(completed_trades), 4) if completed_trades else 0,
            'profit_factor': round(
                sum(t.get('pnl', 0) for t in win_trades) / abs(sum(t.get('pnl', 0) for t in lose_trades)), 2
            ) if lose_trades and sum(t.get('pnl', 0) for t in lose_trades) != 0 else float('inf'),
            'total_trades': len(completed_trades),
        }

        return {
            'metrics': metrics,
            'trades': completed_trades,
            'equity_curve': equity_curve,
            'signals': {
                'signal': {str(k)[:10]: int(v) for k, v in data['signal'].items()}
            },
        }

    def run_batch(
        self,
        codes: List[str],
        buy_conditions: List[Condition],
        sell_conditions: List[Condition],
        start: str, end: str,
        adjust: str = 'qfq',
        config: BacktestConfig = None,
        logic: str = 'and',
    ) -> Dict[str, dict]:
        """批量回测多只股票"""
        results = {}
        for code in codes:
            try:
                results[code] = self.run(
                    code, buy_conditions, sell_conditions,
                    start, end, adjust, config, logic
                )
            except Exception as e:
                results[code] = {'error': str(e)}
        return results


# ─── 便捷函数 ───────────────────────────────────────

def quick_backtest(
    code: str,
    buy_cond: dict,
    sell_cond: dict,
    start: str,
    end: str,
    data_source=None,
) -> dict:
    """
    快速回测 — 一行代码执行因子条件回测

    Args:
        code: 股票代码
        buy_cond: {"factor_id": "rsi", "params": {"period": 14}, "operator": "<", "value": 30}
        sell_cond: 同上
        start, end: 日期范围
        data_source: 数据源（可选）

    Example:
        result = quick_backtest("000001.SZ",
            {"factor_id": "rsi", "operator": "<", "value": 30},
            {"factor_id": "rsi", "operator": ">", "value": 70},
            "2023-01-01", "2024-12-31")
    """
    from backtest.data_provider import get_data_source

    ds = data_source or get_data_source('tushare')
    factor_engine = FactorEngine(ds)
    runner = FactorBacktestRunner(factor_engine)

    buy = [Condition.from_dict(buy_cond)]
    sell = [Condition.from_dict(sell_cond)]

    return runner.run(code, buy, sell, start, end)
