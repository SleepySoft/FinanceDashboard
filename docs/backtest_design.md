# FinanceDashboard 回测系统设计文档

> 版本：v1.0
> 日期：2026-08-12
> 状态：设计阶段

---

## 一、设计目标

### 核心诉求
1. **策略库管理** — 网页上维护策略，为每个策略写笔记
2. **灵活回测** — 支持指定股票/全量，指定时间范围，缓存结果
3. **标准+自定义** — 算法有标准模板，也可自定义代码
4. **逐帧观察** — 后端支持逐帧回测数据，前端已有组件
5. **复权稳定** — 正确处理各种复权场景
6. **数据源可插拔** — 当前 Tushare，未来切换到用户自己的库
7. **可扩展** — 当前日粒度，未来可能支持分钟

### 设计原则
- **渐进式实现** — MVP 先跑通，逐步增强
- **向后兼容** — 数据结构设计预留扩展空间
- **简单优先** — 策略编写维护简单，不引入复杂 DSL
- **可观测** — 回测过程可逐帧观察，方便调试

---

## 二、架构设计

### 2.1 模块划分

```
FinanceDashboard/
├── backend/
│   ├── main.py                    # 现有主入口
│   ├── auth.py                    # 现有认证
│   ├── backtest/
│   │   ├── __init__.py
│   │   ├── engine.py              # 回测引擎核心（封装 vectorbt）
│   │   ├── data_provider.py       # 数据提供者（抽象层）
│   │   ├── data_source_tushare.py # Tushare 实现
│   │   ├── data_source_custom.py  # 用户自定义数据源（预留）
│   │   ├── frame_replayer.py      # 逐帧回放器
│   │   ├── metrics.py             # 绩效指标
│   │   └── cache.py               # 回测结果缓存
│   └── strategy/
│       ├── __init__.py
│       ├── registry.py            # 策略注册/发现
│       ├── models.py              # 策略数据模型
│       ├── builtin/               # 内置标准策略
│       │   ├── __init__.py
│       │   ├── ma_cross.py        # 均线交叉
│       │   ├── rsi_reversal.py    # RSI 反转
│       │   ├── macd_trend.py      # MACD 趋势
│       │   └── breakout.py        # 突破策略
│       └── custom/                # 用户自定义策略（Git 跟踪）
│           ├── __init__.py
│           └── .gitkeep
│
├── data/
│   ├── backtest/                  # 回测相关数据
│   │   ├── cache/                 # 回测结果缓存
│   │   │   └── {hash}.json        # 按参数哈希缓存
│   │   ├── frames/                # 逐帧数据（临时/按需）
│   │   └── bars_cache/            # K线数据本地缓存
│   └── _strategies.json           # 策略库元数据
│
└── frontend/src/views/
    ├── Backtest.vue               # 回测主页面
    ├── StrategyLibrary.vue        # 策略库管理
    └── StrategyEditor.vue         # 策略编辑器
```

### 2.2 数据模型

#### 策略（Strategy）

```typescript
interface Strategy {
  id: string;              // 唯一标识 (uuid)
  name: string;            // 显示名称
  description: string;     // 描述
  notes: string;           // 用户笔记（Markdown）
  type: 'builtin' | 'custom';  // 内置或自定义
  source: string;          // 策略代码（Python）
  params: StrategyParam[]; // 参数定义
  tags: string[];          // 标签
  created_at: string;
  updated_at: string;
  author: string;
  version: number;         // 版本号
  is_active: boolean;
}

interface StrategyParam {
  name: string;            // 参数名
  type: 'int' | 'float' | 'string' | 'bool' | 'select';
  default: any;            // 默认值
  min?: number;            // 范围（数值型）
  max?: number;
  step?: number;
  options?: string[];      // 选项（select 型）
  description: string;     // 参数说明
}
```

#### 回测记录（BacktestRecord）

```typescript
interface BacktestRecord {
  id: string;              // 唯一标识
  strategy_id: string;     // 策略 ID
  strategy_version: number;
  params: Record<string, any>;  // 实际使用的参数值
  
  // 回测范围
  scope: {
    mode: 'single' | 'batch';   // 单股/批量
    codes: string[];             // 股票列表
    start_date: string;
    end_date: string;
  };
  
  // 配置
  config: {
    initial_cash: number;
    commission: number;     // 佣金率
    slippage: number;       // 滑点
    adjust: 'qfq' | 'hfq' | 'none';  // 复权方式
  };
  
  // 结果
  result: {
    status: 'success' | 'error' | 'running';
    metrics: PerformanceMetrics;
    trades: TradeRecord[];
    equity_curve: number[];  // 每日权益
    drawdown_curve: number[];
    error_message?: string;
  };
  
  // 缓存控制
  cache_key: string;       // 参数哈希，用于缓存匹配
  created_at: string;
  ran_by: string;          // 执行者
}

interface PerformanceMetrics {
  total_return: number;        // 总收益率
  annualized_return: number;   // 年化收益率
  sharpe_ratio: number;        // 夏普比率
  max_drawdown: number;        // 最大回撤
  max_drawdown_duration: number;
  win_rate: number;            // 胜率
  profit_factor: number;       // 盈亏比
  avg_profit_per_trade: number;
  avg_loss_per_trade: number;
  total_trades: number;
  
  // 扩展字段（预留）
  calmar_ratio?: number;
  sortino_ratio?: number;
  omega_ratio?: number;
}

interface TradeRecord {
  entry_date: string;
  exit_date: string;
  entry_price: number;
  exit_price: number;
  quantity: number;
  pnl: number;
  pnl_pct: number;
  side: 'long' | 'short';
}
```

#### 逐帧数据（Frame）

```typescript
interface Frame {
  date: string;            // 日期
  bar: {
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
  };
  indicators: Record<string, number>;  // 指标值
  signal: 0 | 1 | -1;      // 信号
  position: {
    quantity: number;
    avg_cost: number;
    unrealized_pnl: number;
  };
  portfolio: {
    cash: number;
    equity: number;
    total_value: number;
  };
  orders: OrderRecord[];   // 当日订单
  trades: TradeRecord[];   // 当日成交
}

interface OrderRecord {
  type: 'buy' | 'sell';
  price: number;
  quantity: number;
  status: 'filled' | 'partial' | 'cancelled';
}
```

### 2.3 数据源抽象层

```python
# backend/backtest/data_provider.py
from abc import ABC, abstractmethod
import pandas as pd

class DataSource(ABC):
    """数据源抽象基类 — 支持 Tushare 和用户自定义库"""
    
    @abstractmethod
    def get_daily_bars(
        self,
        code: str,
        start: str,
        end: str,
        adjust: str = 'qfq',    # qfq=前复权, hfq=后复权, none=不复权
    ) -> pd.DataFrame:
        """
        返回 OHLCV DataFrame，index 为日期
        必须处理复权
        """
        pass
    
    @abstractmethod
    def get_all_codes(self) -> list[str]:
        """获取所有可交易股票代码列表"""
        pass
    
    @abstractmethod
    def get_name(self, code: str) -> str:
        """获取股票名称"""
        pass

# 实现 1：Tushare
class TushareDataSource(DataSource):
    def __init__(self, token: str):
        import tushare as ts
        ts.set_token(token)
        self.pro = ts.pro_api()
    
    def get_daily_bars(self, code, start, end, adjust='qfq'):
        # Tushare 复权接口
        df = self.pro.pro_bar(
            ts_code=code,
            start_date=start,
            end_date=end,
            adj=adjust,
            freq='D'
        )
        return self._normalize(df)

# 实现 2：用户自定义（预留）
class CustomDataSource(DataSource):
    def __init__(self, connection_string: str):
        # 用户自己的数据库连接
        pass
```

---

## 三、策略系统

### 3.1 策略基类

```python
# backend/strategy/builtin/base.py
from abc import ABC, abstractmethod
import pandas as pd
from typing import Dict, Any, Optional

class Strategy(ABC):
    """
    策略基类 — 所有策略（内置+自定义）必须继承
    
    设计要点：
    1. 策略只关心信号生成，不关心回测执行
    2. 参数通过 __init__ 传入，便于参数扫描
    3. 支持逐帧观察 — generate_signals 返回完整信号序列
    """
    
    # 元数据（必须定义）
    name: str = "unnamed"
    description: str = ""
    author: str = ""
    version: int = 1
    tags: list[str] = []
    
    # 参数定义（用于前端渲染和验证）
    params_def: list[dict] = []
    
    def __init__(self, **kwargs):
        """参数通过 kwargs 传入"""
        for param in self.params_def:
            name = param['name']
            setattr(self, name, kwargs.get(name, param.get('default')))
    
    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        核心方法：生成交易信号
        
        Args:
            data: OHLCV DataFrame
                Index: datetime
                Columns: open, high, low, close, volume
        
        Returns:
            包含以下列的 DataFrame：
            - signal: 1(买入), -1(卖出), 0(无)
            - indicators_{name}: 指标值（用于逐帧显示）
        """
        pass
    
    def get_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        可选：单独获取指标值（用于逐帧观察）
        默认调用 generate_signals 并提取指标列
        """
        signals = self.generate_signals(data)
        indicator_cols = [c for c in signals.columns if c.startswith('indicators_')]
        return signals[indicator_cols] if indicator_cols else pd.DataFrame()
    
    def validate_params(self) -> tuple[bool, str]:
        """参数验证"""
        for param in self.params_def:
            name = param['name']
            value = getattr(self, name, None)
            if param.get('required') and value is None:
                return False, f"参数 {name} 必填"
            if param.get('min') is not None and value < param['min']:
                return False, f"参数 {name} 不能小于 {param['min']}"
            if param.get('max') is not None and value > param['max']:
                return False, f"参数 {name} 不能大于 {param['max']}"
        return True, ""
    
    def to_dict(self) -> dict:
        """序列化为策略定义"""
        return {
            'id': self.name.lower().replace(' ', '_'),
            'name': self.name,
            'description': self.description,
            'author': self.author,
            'version': self.version,
            'tags': self.tags,
            'params': self.params_def,
            'source': self.get_source_code(),
        }
    
    def get_source_code(self) -> str:
        """获取策略源码（自定义策略用）"""
        import inspect
        return inspect.getsource(self.__class__)
```

### 3.2 策略示例：均线交叉

```python
# backend/strategy/builtin/ma_cross.py
import pandas as pd
import vectorbt as vbt
from .base import Strategy

class MovingAverageCross(Strategy):
    """双均线交叉策略"""
    
    name = "均线交叉"
    description = "快线突破慢线买入，跌破卖出"
    tags = ["趋势", "经典"]
    
    params_def = [
        {
            'name': 'fast',
            'type': 'int',
            'default': 10,
            'min': 2,
            'max': 60,
            'step': 1,
            'description': '快线周期'
        },
        {
            'name': 'slow',
            'type': 'int',
            'default': 30,
            'min': 5,
            'max': 250,
            'step': 1,
            'description': '慢线周期'
        }
    ]
    
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        close = data['close']
        
        # 计算均线
        fast_ma = vbt.MA.run(close, window=self.fast).ma
        slow_ma = vbt.MA.run(close, window=self.slow).ma
        
        # 信号
        entries = fast_ma > slow_ma
        exits = fast_ma < slow_ma
        
        return pd.DataFrame({
            'signal': entries.astype(int) - exits.astype(int),
            'indicators_fast_ma': fast_ma,
            'indicators_slow_ma': slow_ma,
        })
```

### 3.3 自定义策略加载

```python
# backend/strategy/registry.py
import os
import sys
import importlib
import inspect
from pathlib import Path

class StrategyRegistry:
    """策略注册表 — 管理内置策略和自定义策略"""
    
    def __init__(self, custom_dir: str = None):
        self.strategies: dict[str, type] = {}
        self.custom_dir = custom_dir or '/root/data/FinanceDashboard/strategy/custom'
        self._load_builtin()
        self._load_custom()
    
    def _load_builtin(self):
        """加载内置策略"""
        from .builtin import ma_cross, rsi_reversal, macd_trend, breakout
        
        modules = [ma_cross, rsi_reversal, macd_trend, breakout]
        for module in modules:
            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and 
                    hasattr(obj, 'name') and 
                    obj.__name__ != 'Strategy'):
                    self.strategies[obj.name] = obj
    
    def _load_custom(self):
        """从文件加载自定义策略"""
        os.makedirs(self.custom_dir, exist_ok=True)
        
        for file in Path(self.custom_dir).glob('*.py'):
            if file.name.startswith('_'):
                continue
            
            # 动态导入
            spec = importlib.util.spec_from_file_location(
                file.stem, str(file)
            )
            module = importlib.util.module_from_spec(spec)
            sys.modules[file.stem] = module
            spec.loader.exec_module(module)
            
            # 提取策略类
            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and 
                    hasattr(obj, 'name') and
                    hasattr(obj, 'generate_signals')):
                    self.strategies[obj.name] = obj
    
    def get(self, name: str) -> type:
        return self.strategies.get(name)
    
    def list_all(self) -> list[dict]:
        return [cls().to_dict() for cls in self.strategies.values()]
    
    def save_custom(self, name: str, source: str) -> bool:
        """保存自定义策略到文件"""
        file_path = Path(self.custom_dir) / f"{name}.py"
        with open(file_path, 'w') as f:
            f.write(source)
        
        # 重新加载
        self._load_custom()
        return True
```

---

## 四、回测引擎

### 4.1 引擎设计

```python
# backend/backtest/engine.py
import vectorbt as vbt
import pandas as pd
from typing import Type, Dict, Any, Optional, Callable
from dataclasses import dataclass

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
    
    # ─── 快速回测（向量化） ───
    
    def run(
        self,
        strategy_class: Type,
        data: pd.DataFrame,
        params: dict = None,
    ) -> dict:
        """
        单次回测
        
        Returns:
            {
                'portfolio': vbt.Portfolio,
                'metrics': PerformanceMetrics,
                'trades': pd.DataFrame,
                'equity_curve': pd.Series,
                'drawdown_curve': pd.Series,
                'signals': pd.DataFrame,
            }
        """
        strategy = strategy_class(**(params or {}))
        signals = strategy.generate_signals(data)
        
        pf = vbt.Portfolio.from_signals(
            close=data['close'],
            entries=signals['signal'] == 1,
            exits=signals['signal'] == -1,
            init_cash=self.config.initial_cash,
            fees=self.config.commission,
            slippage=self.config.slippage,
            size=self.config.size,
            size_type=self.config.size_type,
            freq=self.config.freq,
        )
        
        return {
            'portfolio': pf,
            'metrics': self._calc_metrics(pf),
            'trades': pf.trades.records_readable,
            'equity_curve': pf.value(),
            'drawdown_curve': pf.drawdown(),
            'signals': signals,
        }
    
    # ─── 逐帧回放（用于前端观察） ───
    
    def run_frames(
        self,
        strategy_class: Type,
        data: pd.DataFrame,
        params: dict = None,
    ) -> list[dict]:
        """
        逐帧回测 — 生成每一帧的状态数据
        
        返回 Frame 列表，前端可以逐帧播放
        
        注意：这比向量化慢，但提供了完整的中间状态
        """
        strategy = strategy_class(**(params or {}))
        signals = strategy.generate_signals(data)
        
        frames = []
        position = 0
        avg_cost = 0.0
        cash = self.config.initial_cash
        
        for date, row in data.iterrows():
            signal = signals.loc[date, 'signal']
            close = row['close']
            
            # 模拟交易
            orders = []
            trades_today = []
            
            if signal == 1 and position <= 0:  # 买入
                size = cash * self.config.size / close
                cost = size * close * (1 + self.config.commission)
                if cash >= cost:
                    orders.append({
                        'type': 'buy', 'price': close, 
                        'quantity': size, 'status': 'filled'
                    })
                    avg_cost = close
                    position = size
                    cash -= cost
                    trades_today.append({
                        'entry_date': date, 'entry_price': close,
                        'quantity': size, 'side': 'long'
                    })
            
            elif signal == -1 and position > 0:  # 卖出
                revenue = position * close * (1 - self.config.commission)
                pnl = position * (close - avg_cost)
                orders.append({
                    'type': 'sell', 'price': close,
                    'quantity': position, 'status': 'filled'
                })
                cash += revenue
                position = 0
                trades_today.append({
                    'exit_date': date, 'exit_price': close,
                    'quantity': position, 'pnl': pnl, 'side': 'long'
                })
            
            # 计算市值
            equity = cash + position * close
            
            # 提取指标
            indicators = {
                k.replace('indicators_', ''): v
                for k, v in signals.loc[date].items()
                if k.startswith('indicators_')
            }
            
            frames.append({
                'date': date.isoformat(),
                'bar': {
                    'open': row['open'], 'high': row['high'],
                    'low': row['low'], 'close': close,
                    'volume': row['volume']
                },
                'indicators': indicators,
                'signal': int(signal),
                'position': {
                    'quantity': position,
                    'avg_cost': avg_cost,
                    'unrealized_pnl': position * (close - avg_cost) if position > 0 else 0
                },
                'portfolio': {
                    'cash': cash,
                    'equity': equity,
                    'total_value': equity
                },
                'orders': orders,
                'trades': trades_today
            })
        
        return frames
    
    def _calc_metrics(self, pf: vbt.Portfolio) -> dict:
        """计算绩效指标"""
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
```

### 4.2 缓存系统

```python
# backend/backtest/cache.py
import hashlib
import json
import os
from datetime import datetime

class BacktestCache:
    """
    回测结果缓存 — 基于参数哈希
    
    缓存键生成：
    - 策略 ID + 版本
    - 参数值
    - 股票代码 + 时间范围
    - 回测配置（手续费、滑点等）
    """
    
    def __init__(self, cache_dir: str = None):
        self.cache_dir = cache_dir or '/root/data/FinanceDashboard/data/backtest/cache'
        os.makedirs(self.cache_dir, exist_ok=True)
    
    def _make_key(self, strategy_id: str, params: dict, 
                  codes: list, start: str, end: str,
                  config: dict) -> str:
        """生成缓存键"""
        key_data = {
            'strategy': strategy_id,
            'params': params,
            'codes': sorted(codes),
            'start': start,
            'end': end,
            'config': config
        }
        json_str = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()[:16]
    
    def get(self, strategy_id: str, params: dict,
            codes: list, start: str, end: str,
            config: dict) -> dict:
        """获取缓存结果"""
        key = self._make_key(strategy_id, params, codes, start, end, config)
        cache_file = os.path.join(self.cache_dir, f"{key}.json")
        
        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                return json.load(f)
        return None
    
    def set(self, result: dict, strategy_id: str, params: dict,
            codes: list, start: str, end: str,
            config: dict):
        """保存缓存"""
        key = self._make_key(strategy_id, params, codes, start, end, config)
        cache_file = os.path.join(self.cache_dir, f"{key}.json")
        
        with open(cache_file, 'w') as f:
            json.dump({
                'key': key,
                'created_at': datetime.now().isoformat(),
                'result': result
            }, f, ensure_ascii=False, indent=2)
    
    def clear(self):
        """清除所有缓存"""
        for f in os.listdir(self.cache_dir):
            os.remove(os.path.join(self.cache_dir, f))
```

---

## 五、API 设计

### 5.1 策略管理

```
GET    /api/backtest/strategies           # 列出所有策略
POST   /api/backtest/strategies           # 创建自定义策略
GET    /api/backtest/strategies/{id}      # 获取策略详情
PUT    /api/backtest/strategies/{id}      # 更新策略（自定义）
DELETE /api/backtest/strategies/{id}      # 删除策略（自定义）
GET    /api/backtest/strategies/{id}/source  # 获取策略源码
```

### 5.2 回测执行

```
POST   /api/backtest/run                  # 执行回测
POST   /api/backtest/run/frame            # 执行逐帧回测
GET    /api/backtest/run/{id}/status      # 查询回测状态（异步）
```

### 5.3 回测记录

```
GET    /api/backtest/records              # 列出回测记录（支持过滤）
GET    /api/backtest/records/{id}         # 获取回测详情
DELETE /api/backtest/records/{id}         # 删除记录
```

### 5.4 示例请求/响应

**创建策略：**
```http
POST /api/backtest/strategies
Content-Type: application/json

{
  "name": "我的策略",
  "description": "基于RSI的反转策略",
  "notes": "## 思路\n在RSI超卖时买入...",
  "source": "from strategy.builtin.base import Strategy\n...",
  "params": [
    {"name": "rsi_period", "type": "int", "default": 14, "min": 2, "max": 100}
  ],
  "tags": ["反转", "RSI"]
}
```

**执行回测：**
```http
POST /api/backtest/run
Content-Type: application/json

{
  "strategy_id": "ma_cross",
  "params": {"fast": 10, "slow": 30},
  "codes": ["000001.SZ", "000002.SZ"],
  "start_date": "2023-01-01",
  "end_date": "2024-12-31",
  "config": {
    "initial_cash": 100000,
    "commission": 0.00025,
    "slippage": 0.001,
    "adjust": "qfq"
  },
  "use_cache": true
}

# 响应
{
  "id": "bt_xxx",
  "status": "success",
  "metrics": {
    "total_return": 0.35,
    "sharpe_ratio": 1.2,
    "max_drawdown": -0.15
  },
  "trades_count": 42,
  "equity_curve": [100000, 100100, 99800, ...],
  "cache_key": "a1b2c3d4"
}
```

**逐帧回测：**
```http
POST /api/backtest/run/frame
Content-Type: application/json

{
  "strategy_id": "ma_cross",
  "params": {"fast": 10, "slow": 30},
  "code": "000001.SZ",
  "start_date": "2024-01-01",
  "end_date": "2024-03-01"
}

# 响应 — 返回每一帧的详细数据
{
  "frames": [
    {
      "date": "2024-01-02",
      "bar": {"open": 10.5, "high": 10.8, "low": 10.4, "close": 10.6, "volume": 100000},
      "indicators": {"fast_ma": 10.55, "slow_ma": 10.50},
      "signal": 1,
      "position": {"quantity": 1000, "avg_cost": 10.6, "unrealized_pnl": 0},
      "portfolio": {"cash": 89360, "equity": 99960, "total_value": 99960},
      "orders": [{"type": "buy", "price": 10.6, "quantity": 1000, "status": "filled"}],
      "trades": []
    },
    ...
  ]
}
```

---

## 六、前端设计

### 6.1 页面规划

| 页面 | 功能 |
|------|------|
| **StrategyLibrary.vue** | 策略列表、创建/编辑/删除策略、写笔记 |
| **Backtest.vue** | 选择策略 → 设置参数 → 选择股票 → 执行回测 → 查看结果 |
| **BacktestResult.vue** | 回测结果详情：收益曲线、回撤、交易记录、指标卡片 |
| **FramePlayer.vue** | 逐帧播放器（用户说已有组件，只需对接数据） |

### 6.2 StrategyLibrary 界面

```
┌─────────────────────────────────────────────┐
│  策略库                              [+ 新建] │
├─────────────────────────────────────────────┤
│  [全部] [趋势] [反转] [突破] [我的]          │
│                                             │
│  ┌──────────────┐  ┌──────────────┐        │
│  │ 📈 均线交叉   │  │ 📉 RSI反转   │        │
│  │ 趋势 · 内置   │  │ 反转 · 内置   │        │
│  │              │  │              │        │
│  │ 快:10 慢:30  │  │ 周期:14      │        │
│  │ [回测] [编辑] │  │ [回测] [编辑] │        │
│  └──────────────┘  └──────────────┘        │
│                                             │
│  ┌──────────────┐                          │
│  │ 📝 我的策略A  │                          │
│  │ 自定义       │                          │
│  │ [回测] [编辑] [删除]                     │
│  └──────────────┘                          │
└─────────────────────────────────────────────┘
```

### 6.3 Backtest 界面

```
┌─────────────────────────────────────────────┐
│  回测 Playground                             │
├─────────────────────────────────────────────┤
│  1. 选择策略                                 │
│     [均线交叉 ▼]                             │
│                                             │
│  2. 参数设置                                 │
│     快线: [10    ]  慢线: [30    ]          │
│                                             │
│  3. 回测范围                                 │
│     股票: [000001.SZ        ] [+ 添加]      │
│     时间: [2023-01-01] ~ [2024-12-31]       │
│     复权: [前复权 ▼]                        │
│                                             │
│  4. 资金设置                                 │
│     初始资金: [100000]  佣金: [0.025%]      │
│                                             │
│     [开始回测]                               │
│     [⚡ 使用缓存] [☐ 逐帧模式]              │
└─────────────────────────────────────────────┘
```

---

## 七、复权处理

### 7.1 复权方式

| 方式 | 适用场景 | 数据特点 |
|------|---------|---------|
| **前复权 (qfq)** | 回测（默认） | 最新价格真实，历史价格被调整 |
| **后复权 (hfq)** | 长期趋势分析 | 历史价格真实，最新价格被调整 |
| **不复权** | 查看原始 K 线 | 有跳空缺口 |

### 7.2 实现策略

```python
# 数据层统一处理复权
class DataProvider:
    def get_daily_bars(self, code, start, end, adjust='qfq'):
        """
        根据复权方式获取数据
        
        Tushare 的复权接口：
        - pro_bar(adj='qfq')  前复权
        - pro_bar(adj='hfq')  后复权
        - pro_bar(adj=None)   不复权
        """
        df = self.pro.pro_bar(
            ts_code=code,
            start_date=start,
            end_date=end,
            adj=adjust,
            freq='D'
        )
        return self._normalize(df)
```

### 7.3 注意事项

1. **回测必须用前复权** — 保证最新价格真实，避免"未来数据"
2. **复权因子变化** — 每次分红送转后需要重新下载历史数据
3. **缓存失效** — 复权因子更新时，缓存的历史数据需要刷新

---

## 八、数据源切换计划

### 8.1 抽象层

```python
# backend/backtest/data_source.py
from abc import ABC, abstractmethod

class DataSource(ABC):
    """数据源抽象基类"""
    
    @abstractmethod
    def get_daily_bars(self, code: str, start: str, end: str, adjust: str = 'qfq') -> pd.DataFrame:
        pass
    
    @abstractmethod
    def get_all_codes(self) -> list[str]:
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass
```

### 8.2 当前实现：Tushare

```python
class TushareDataSource(DataSource):
    name = "tushare"
    
    def __init__(self, token: str = None):
        import tushare as ts
        self.token = token or os.environ.get('TUSHARE_TOKEN')
        ts.set_token(self.token)
        self.pro = ts.pro_api()
```

### 8.3 未来实现：用户自定义库

```python
class CustomDataSource(DataSource):
    """用户自定义数据源 — 通过配置文件或环境变量注入"""
    
    name = "custom"
    
    def __init__(self, config: dict):
        """
        config = {
            'type': 'postgresql' | 'mysql' | 'clickhouse' | 'api',
            'connection': {...},
            'table_mapping': {...}
        }
        """
        self.config = config
        self.conn = self._connect()
    
    def get_daily_bars(self, code, start, end, adjust='qfq'):
        # 从用户数据库查询
        query = f"""
            SELECT date, open, high, low, close, volume
            FROM daily_bars
            WHERE code = '{code}' 
            AND date BETWEEN '{start}' AND '{end}'
            ORDER BY date
        """
        return pd.read_sql(query, self.conn)
```

### 8.4 配置切换

```python
# backend/config.py
BACKTEST_DATA_SOURCE = os.environ.get('BACKTEST_DATA_SOURCE', 'tushare')

def get_data_source():
    if BACKTEST_DATA_SOURCE == 'tushare':
        return TushareDataSource()
    elif BACKTEST_DATA_SOURCE == 'custom':
        config = load_custom_config()
        return CustomDataSource(config)
    else:
        raise ValueError(f"Unknown data source: {BACKTEST_DATA_SOURCE}")
```

---

## 九、分钟级扩展（预留）

### 9.1 频率抽象

```python
class BacktestConfig:
    freq: str = '1d'   # '1d', '1h', '30m', '15m', '5m', '1m'
```

### 9.2 数据接口预留

```python
class DataSource(ABC):
    @abstractmethod
    def get_bars(
        self, 
        code: str, 
        start: str, 
        end: str,
        freq: str = '1d',    # 新增频率参数
        adjust: str = 'qfq'
    ) -> pd.DataFrame:
        pass
```

### 9.3 当前限制

- Phase 1 只实现日级回测
- 数据结构和 API 预留 `freq` 参数
- vectorbt 本身支持任意频率

---

## 十、实施计划

### Phase 1：核心骨架（2-3 天）

**目标**：能跑通一个回测，有基本界面

- [ ] 安装 vectorbt：`pip install vectorbt`
- [ ] 创建目录结构：`backtest/`, `strategy/`, `data/backtest/`
- [ ] 实现 `DataSource` 抽象层 + `TushareDataSource`
- [ ] 实现 `Strategy` 基类 + `MovingAverageCross` 示例策略
- [ ] 实现 `BacktestEngine.run()`（向量化回测）
- [ ] 实现 `BacktestCache` 缓存系统
- [ ] 后端 API：`/api/backtest/strategies`, `/api/backtest/run`
- [ ] 前端：策略列表页 + 回测表单页 + 结果展示页

### Phase 2：策略库管理（2-3 天）

- [ ] 策略 CRUD API（创建自定义策略）
- [ ] 策略源码编辑器（前端 Monaco/CodeMirror）
- [ ] 策略笔记/文档（Markdown 渲染）
- [ ] 策略标签系统
- [ ] 策略注册表自动发现

### Phase 3：逐帧观察（2-3 天）

- [ ] 实现 `BacktestEngine.run_frames()`（逐帧模式）
- [ ] 后端 API：`/api/backtest/run/frame`
- [ ] 前端对接用户已有组件
- [ ] 帧数据预加载/流式传输优化

### Phase 4：全量回测与优化（2-3 天）

- [ ] 批量回测（多股票并行）
- [ ] 参数扫描（网格搜索）
- [ ] 回测记录管理（列表/筛选/删除）
- [ ] 性能优化：大数据量分页/流式

### Phase 5：完善与切换数据源（后续）

- [ ] 复权处理完善
- [ ] 用户自定义数据源接入
- [ ] 分钟级回测（按需）
- [ ] 更多内置策略

---

## 十一、风险与应对

| 风险 | 影响 | 应对 |
|------|------|------|
| vectorbt 学习曲线 | 开发时间增加 | 先用简单策略跑通，逐步深入 |
| 大数据量性能 | 前端卡顿/后端内存不足 | 分页加载、流式传输、服务端聚合 |
| 自定义策略安全 | 用户代码可能有害 | 沙箱执行、限制导入、超时控制 |
| 复权数据一致性 | 回测结果不准确 | 复权因子版本管理、缓存失效策略 |
| Tushare 频率限制 | 全量回测被限流 | 本地缓存、增量更新、限流处理 |

---

## 十二、文件清单

### 新增文件

```
backend/backtest/
├── __init__.py
├── engine.py              # 回测引擎
├── data_provider.py       # 数据源抽象
├── data_source_tushare.py # Tushare 实现
├── frame_replayer.py      # 逐帧回放
├── metrics.py             # 绩效指标
└── cache.py               # 缓存系统

backend/strategy/
├── __init__.py
├── registry.py            # 策略注册
├── models.py              # 数据模型
└── builtin/
    ├── __init__.py
    ├── base.py            # 策略基类
    ├── ma_cross.py        # 均线策略
    ├── rsi_reversal.py    # RSI策略
    ├── macd_trend.py      # MACD策略
    └── breakout.py        # 突破策略

data/backtest/
├── cache/                 # 回测缓存
├── frames/                # 逐帧数据
└── bars_cache/            # K线缓存

frontend/src/views/
├── StrategyLibrary.vue    # 策略库
├── Backtest.vue           # 回测页面
└── BacktestResult.vue     # 结果展示
```

---

## 十三、总结

本设计遵循以下原则：

1. **渐进实现** — Phase 1 先跑通 MVP，后续逐步增强
2. **向量化优先** — 用 vectorbt 做计算，自己写封装
3. **数据源抽象** — 预留切换接口，当前 Tushare，未来无缝切换
4. **策略即代码** — 策略是 Python 类，不是 DSL，灵活且可扩展
5. **逐帧可观测** — 双模式回测：快速向量化 + 逐帧观察
6. **缓存加速** — 相同参数直接读缓存，避免重复计算

---

> **下一步**：确认设计无误后，开始 Phase 1 实施。
