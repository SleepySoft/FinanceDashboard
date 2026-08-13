"""回测引擎 — 封装 vectorbt，支持向量化回测和逐帧回放"""
import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Type, Dict, Any, Optional


@dataclass
class BacktestConfig:
    initial_cash: float = 100000.0
    commission: float = 0.00025      # 万分之2.5
    slippage: float = 0.001          # 千分之1
    size_type: str = 'percent'       # percent / fixed / shares
    size: float = 0.2                # 每次投入 20%
    freq: str = '1d'                 # 日粒度


class BacktestEngine:
    """
    回测引擎 — 封装 vectorbt，支持向量化回测和逐帧回放

    两种模式：
    1. fast_mode: 向量化快速回测（默认）
    2. frame_mode: 逐帧生成数据（用于前端观察）
    """

    def __init__(self, config: BacktestConfig = None):
        self.config = config or BacktestConfig()

    def run(self, strategy_class: Type, data: pd.DataFrame, params: dict = None) -> dict:
        """
        单次回测 — 向量化模式

        Returns:
            {
                'metrics': PerformanceMetrics dict,
                'trades': list of TradeRecord dicts,
                'equity_curve': list of dicts {date, value},
                'drawdown_curve': list of dicts {date, value},
                'signals': DataFrame serialized as dict,
            }
        """
        try:
            import vectorbt as vbt
        except ImportError:
            # Fallback: pure pandas implementation
            return self._run_pandas(strategy_class, data, params)

        strategy = strategy_class(**(params or {}))
        signals = strategy.generate_signals(data)

        entries = signals['signal'] == 1
        exits = signals['signal'] == -1

        pf = vbt.Portfolio.from_signals(
            close=data['close'],
            entries=entries,
            exits=exits,
            init_cash=self.config.initial_cash,
            fees=self.config.commission,
            slippage=self.config.slippage,
            size=self.config.size,
            size_type=self.config.size_type,
            freq=self.config.freq,
        )

        return {
            'metrics': self._calc_metrics(pf),
            'trades': self._extract_trades(pf),
            'equity_curve': self._extract_equity_curve(pf),
            'drawdown_curve': self._extract_drawdown_curve(pf),
            'signals': self._serialize_signals(signals),
        }

    def _run_pandas(self, strategy_class: Type, data: pd.DataFrame, params: dict = None) -> dict:
        """纯 pandas 回测（vectorbt 不可用时 fallback）"""
        strategy = strategy_class(**(params or {}))
        signals = strategy.generate_signals(data)

        cash = self.config.initial_cash
        position = 0
        avg_cost = 0.0
        equity_curve = []
        trades = []
        max_equity = cash
        max_dd = 0.0

        for date, row in data.iterrows():
            close = row['close']
            signal = signals.loc[date, 'signal']

            if signal == 1 and position <= 0:
                # 买入
                invest = cash * self.config.size
                qty = int(invest / close)
                cost = qty * close * (1 + self.config.commission)
                if cash >= cost and qty > 0:
                    position = qty
                    avg_cost = close
                    cash -= cost
                    trades.append({
                        'entry_date': date.isoformat() if hasattr(date, 'isoformat') else str(date),
                        'entry_price': close,
                        'quantity': qty,
                        'side': 'long',
                    })

            elif signal == -1 and position > 0:
                # 卖出
                revenue = position * close * (1 - self.config.commission)
                entry_price = avg_cost
                pnl = position * (close - entry_price)
                cash += revenue
                if trades:
                    trades[-1].update({
                        'exit_date': date.isoformat() if hasattr(date, 'isoformat') else str(date),
                        'exit_price': close,
                        'pnl': pnl,
                        'pnl_pct': (close - entry_price) / entry_price * 100 if entry_price > 0 else 0,
                    })
                position = 0
                avg_cost = 0

            equity = cash + position * close
            max_equity = max(max_equity, equity)
            dd = (equity - max_equity) / max_equity
            max_dd = min(max_dd, dd)

            equity_curve.append({
                'date': date.isoformat() if hasattr(date, 'isoformat') else str(date),
                'value': round(equity, 2)
            })

        total_return = (equity_curve[-1]['value'] - self.config.initial_cash) / self.config.initial_cash if equity_curve else 0
        win_trades = [t for t in trades if t.get('pnl', 0) > 0]
        lose_trades = [t for t in trades if t.get('pnl', 0) <= 0]

        metrics = {
            'total_return': round(total_return, 4),
            'annualized_return': round(total_return, 4),  # 简化
            'sharpe_ratio': 0.0,  # 简化
            'max_drawdown': round(max_dd, 4),
            'max_drawdown_duration': 0,
            'win_rate': round(len(win_trades) / len(trades), 4) if trades else 0,
            'profit_factor': round(sum(t.get('pnl', 0) for t in win_trades) / abs(sum(t.get('pnl', 0) for t in lose_trades)), 2) if lose_trades and sum(t.get('pnl', 0) for t in lose_trades) != 0 else float('inf'),
            'avg_profit_per_trade': round(sum(t.get('pnl', 0) for t in win_trades) / len(win_trades), 2) if win_trades else 0,
            'total_trades': len(trades),
        }

        return {
            'metrics': metrics,
            'trades': trades,
            'equity_curve': equity_curve,
            'drawdown_curve': [],
            'signals': self._serialize_signals(signals),
        }

    def run_frames(self, strategy_class: Type, data: pd.DataFrame, params: dict = None) -> list:
        """
        逐帧回测 — 生成每一帧的状态数据

        返回 Frame 列表，前端可以逐帧播放
        """
        strategy = strategy_class(**(params or {}))
        signals = strategy.generate_signals(data)

        frames = []
        position = 0
        avg_cost = 0.0
        cash = self.config.initial_cash
        total_trades = 0

        for date, row in data.iterrows():
            signal = int(signals.loc[date, 'signal']) if date in signals.index else 0
            close = row['close']

            orders = []
            trades_today = []

            if signal == 1 and position <= 0:  # 买入
                invest = cash * self.config.size
                qty = int(invest / close)
                cost = qty * close * (1 + self.config.commission)
                if cash >= cost and qty > 0:
                    orders.append({
                        'type': 'buy', 'price': round(close, 3),
                        'quantity': qty, 'status': 'filled'
                    })
                    avg_cost = close
                    position = qty
                    cash -= cost
                    total_trades += 1
                    trades_today.append({
                        'entry_date': str(date)[:10],
                        'entry_price': round(close, 3),
                        'quantity': qty, 'side': 'long'
                    })

            elif signal == -1 and position > 0:  # 卖出
                revenue = position * close * (1 - self.config.commission)
                pnl = position * (close - avg_cost)
                orders.append({
                    'type': 'sell', 'price': round(close, 3),
                    'quantity': position, 'status': 'filled'
                })
                cash += revenue
                total_trades += 1
                trades_today.append({
                    'exit_date': str(date)[:10],
                    'exit_price': round(close, 3),
                    'quantity': position,
                    'pnl': round(pnl, 2),
                    'side': 'long'
                })
                position = 0
                avg_cost = 0

            equity = cash + position * close

            # 提取指标
            indicators = {}
            if date in signals.index:
                for k, v in signals.loc[date].items():
                    if k.startswith('indicators_'):
                        indicators[k.replace('indicators_', '')] = round(float(v), 4) if pd.notna(v) else None

            frames.append({
                'date': str(date)[:10],
                'bar': {
                    'open': round(row.get('open', close), 3),
                    'high': round(row.get('high', close), 3),
                    'low': round(row.get('low', close), 3),
                    'close': round(close, 3),
                    'volume': int(row.get('volume', 0))
                },
                'indicators': indicators,
                'signal': signal,
                'position': {
                    'quantity': position,
                    'avg_cost': round(avg_cost, 3),
                    'unrealized_pnl': round(position * (close - avg_cost), 2) if position > 0 else 0
                },
                'portfolio': {
                    'cash': round(cash, 2),
                    'equity': round(equity, 2),
                    'total_value': round(equity, 2)
                },
                'orders': orders,
                'trades': trades_today
            })

        return frames

    def _calc_metrics(self, pf) -> dict:
        """计算绩效指标（vectorbt 版本）"""
        try:
            return {
                'total_return': float(pf.total_return()),
                'annualized_return': float(pf.annualized_return()),
                'sharpe_ratio': float(pf.sharpe_ratio()),
                'max_drawdown': float(pf.max_drawdown()),
                'max_drawdown_duration': int(pf.max_drawdown_duration()),
                'win_rate': float(pf.trades.win_rate()),
                'profit_factor': float(pf.trades.profit_factor()),
                'avg_profit_per_trade': float(pf.trades.returns.mean()),
                'total_trades': int(pf.trades.count()),
            }
        except Exception:
            # Fallback
            return {
                'total_return': 0.0,
                'annualized_return': 0.0,
                'sharpe_ratio': 0.0,
                'max_drawdown': 0.0,
                'max_drawdown_duration': 0,
                'win_rate': 0.0,
                'profit_factor': 0.0,
                'avg_profit_per_trade': 0.0,
                'total_trades': 0,
            }

    def _extract_trades(self, pf) -> list:
        """提取交易记录"""
        try:
            records = pf.trades.records_readable
            trades = []
            for _, row in records.iterrows():
                trades.append({
                    'entry_date': str(row.get('Entry Index', ''))[:10],
                    'exit_date': str(row.get('Exit Index', ''))[:10],
                    'entry_price': float(row.get('Avg Entry Price', 0)),
                    'exit_price': float(row.get('Avg Exit Price', 0)),
                    'quantity': int(row.get('Size', 0)),
                    'pnl': float(row.get('PnL', 0)),
                    'pnl_pct': float(row.get('Return', 0)) * 100,
                    'side': 'long',
                })
            return trades
        except Exception:
            return []

    def _extract_equity_curve(self, pf) -> list:
        """提取权益曲线"""
        try:
            values = pf.value()
            return [
                {'date': str(idx)[:10], 'value': float(v)}
                for idx, v in values.items()
            ]
        except Exception:
            return []

    def _extract_drawdown_curve(self, pf) -> list:
        """提取回撤曲线"""
        try:
            dd = pf.drawdown()
            return [
                {'date': str(idx)[:10], 'value': float(v)}
                for idx, v in dd.items()
            ]
        except Exception:
            return []

    def _serialize_signals(self, signals: pd.DataFrame) -> dict:
        """将信号 DataFrame 序列化为可 JSON 的格式"""
        result = {}
        for col in signals.columns:
            result[col] = {
                str(idx)[:10]: (float(v) if pd.notna(v) else None)
                for idx, v in signals[col].items()
            }
        return result
