# 回测系统选型与架构建议

> 目标：Playground（快速验证）+ 算法库（可维护复用）
> 数据：Tushare（先用），后续可扩展

---

## 一、选型建议

### 不推荐

| 框架 | 原因 |
|------|------|
| **backtrader** | 维护停滞（最后更新 2021），Python 3.10+ 兼容性差，设计老派，扩展痛苦 |
| **vn.py** | 太重，偏实盘交易，回测只是附带功能 |
| **Quantaxis** | 项目已死，文档缺失 |
| **Zipline** | Quantopian 倒闭后维护乏力，安装复杂 |

### 推荐方案：vectorbt + 自定义封装

```
核心引擎：vectorbt（向量化回测，速度快，NumPy/Pandas 原生）
策略框架：自定义（简单、可控、可扩展）
数据层：Tushare + 本地缓存
Playground：Jupyter Notebook / Web 界面
```

**为什么选 vectorbt？**
- 向量化计算，回测速度比事件驱动快 100x+
- 支持多策略并行回测、参数扫描
- 与 Pandas/NumPy 无缝集成
- 活跃维护，文档完善
- 支持投资组合级别分析

---

## 二、架构设计

```
FinanceDashboard/
├── backend/
│   ├── main.py
│   ├── auth.py
│   └── backtest/                 # 新增回测核心模块
│       ├── __init__.py
│       ├── engine.py             # 回测引擎（封装 vectorbt）
│       ├── data_provider.py      # 数据获取（Tushare + 缓存）
│       ├── strategy_base.py      # 策略基类接口
│       └── metrics.py            # 绩效指标计算
│
├── strategies/                   # 用户策略库（Git 跟踪）
│   ├── __init__.py
│   ├── base.py                   # 策略基类定义
│   ├── moving_average.py         # 均线策略示例
│   ├── rsi_reversal.py           # RSI 反转策略示例
│   └── breakout.py               # 突破策略示例
│
├── playground/                   # Playground 环境
│   ├── notebooks/                # Jupyter 笔记本
│   └── scripts/                  # 快速测试脚本
│
├── data/backtest/                # 回测数据缓存
│   ├── bars/                     # K线数据（按股票分目录）
│   └── results/                  # 回测结果存储
│
└── frontend/src/views/           # 前端新增页面
    └── Backtest.vue              # 回测 Playground 界面
```

---

## 三、核心组件设计

### 1. 策略基类（strategies/base.py）

策略只关心信号生成，不关心回测执行：

```python
from abc import ABC, abstractmethod
import pandas as pd

class Strategy(ABC):
    """策略基类 - 只定义接口，不依赖回测引擎"""
    
    name: str = "unnamed"
    params: dict = {}  # 策略参数定义
    
    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        输入: OHLCV DataFrame (index=datetime)
        输出: 带信号列的 DataFrame
            - signal: 1(买入), -1(卖出), 0(持仓)
            - 可选: size, stop_loss, take_profit
        """
        pass
    
    def on_data_update(self, data: pd.DataFrame):
        """数据更新回调（用于实时监控）"""
        pass
```

### 2. 回测引擎（backend/backtest/engine.py）

```python
import vectorbt as vbt
from typing import Type, List, Dict
import pandas as pd

class BacktestEngine:
    """
    回测引擎 - 封装 vectorbt，统一接口
    """
    def __init__(self, initial_cash: float = 100000.0):
        self.initial_cash = initial_cash
        self.results = {}
    
    def run_single(
        self,
        strategy_class: Type,
        data: pd.DataFrame,
        params: dict = None,
        commission: float = 0.00025,  # 万分之2.5
        slippage: float = 0.001,       # 千分之1滑点
    ) -> dict:
        """
        单策略回测
        
        Returns:
            {
                'pf': Portfolio object,
                'metrics': {sharpe, max_drawdown, total_return, ...},
                'trades': DataFrame,
                'equity_curve': Series
            }
        """
        # 生成信号
        strategy = strategy_class(**(params or {}))
        signals = strategy.generate_signals(data)
        
        # vectorbt 回测
        pf = vbt.Portfolio.from_signals(
            close=data['close'],
            entries=signals['signal'] == 1,
            exits=signals['signal'] == -1,
            init_cash=self.initial_cash,
            fees=commission,
            slippage=slippage,
            freq='1d',
        )
        
        return {
            'pf': pf,
            'metrics': self._calc_metrics(pf),
            'trades': pf.trades.records_readable,
            'equity_curve': pf.value(),
        }
    
    def run_param_scan(
        self,
        strategy_class: Type,
        data: pd.DataFrame,
        param_grid: Dict[str, List],
    ) -> pd.DataFrame:
        """
        参数扫描 - 找最优参数组合
        
        param_grid = {'fast_ma': [5, 10, 20], 'slow_ma': [30, 60]}
        """
        results = []
        # 使用 itertools.product 遍历参数组合
        # 对每个组合运行回测，记录指标
        return pd.DataFrame(results)
```

### 3. 数据层（backend/backtest/data_provider.py）

```python
import tushare as ts
import pandas as pd
from datetime import datetime, timedelta
import os

class DataProvider:
    """
    数据提供者 - Tushare + 本地缓存
    """
    def __init__(self, token: str = None):
        self.token = token or os.environ.get('TUSHARE_TOKEN')
        ts.set_token(self.token)
        self.pro = ts.pro_api()
        self.cache_dir = '/root/data/FinanceDashboard/data/backtest/bars'
        os.makedirs(self.cache_dir, exist_ok=True)
    
    def get_daily_bars(
        self,
        code: str,
        start: str,
        end: str,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        获取日线数据，优先本地缓存
        """
        cache_file = f"{self.cache_dir}/{code.replace('.', '_')}.csv"
        
        if use_cache and os.path.exists(cache_file):
            df = pd.read_csv(cache_file, index_col='trade_date', parse_dates=True)
            # 检查数据范围是否覆盖请求区间
            if df.index.min() <= pd.Timestamp(start) and df.index.max() >= pd.Timestamp(end):
                return df.loc[start:end]
        
        # 从 Tushare 获取
        df = self.pro.daily(ts_code=code, start_date=start, end_date=end)
        df['trade_date'] = pd.to_datetime(df['trade_date'])
        df.set_index('trade_date', inplace=True)
        df.sort_index(inplace=True)
        
        # 合并到缓存
        if use_cache:
            if os.path.exists(cache_file):
                old_df = pd.read_csv(cache_file, index_col='trade_date', parse_dates=True)
                df = pd.concat([old_df, df]).drop_duplicates().sort_index()
            df.to_csv(cache_file)
        
        return df
```

### 4. Playground 接口（backend/main.py 新增路由）

```python
from backtest.engine import BacktestEngine
from backtest.data_provider import DataProvider
from strategies import load_strategy  # 动态加载策略

@app.post("/api/backtest/run")
async def run_backtest(req: BacktestRequest):
    """
    执行回测
    
    Request:
        code: "000001.SZ"
        strategy: "moving_average"
        params: {"fast": 5, "slow": 20}
        start: "2024-01-01"
        end: "2024-12-31"
        initial_cash: 100000
    """
    # 获取数据
    data = data_provider.get_daily_bars(req.code, req.start, req.end)
    
    # 加载策略
    strategy_class = load_strategy(req.strategy)
    
    # 执行回测
    engine = BacktestEngine(initial_cash=req.initial_cash)
    result = engine.run_single(strategy_class, data, req.params)
    
    return {
        'metrics': result['metrics'],
        'trades_count': len(result['trades']),
        'equity_curve': result['equity_curve'].to_list(),
        'chart_data': {...}  # 给前端画图用
    }

@app.get("/api/backtest/strategies")
async def list_strategies():
    """列出所有可用策略"""
    return [
        {'id': 'moving_average', 'name': '均线交叉', 'params': [...]},
        {'id': 'rsi_reversal', 'name': 'RSI 反转', 'params': [...]},
    ]
```

---

## 四、使用流程

### Playground 快速验证（Jupyter）

```python
# playground/quick_test.ipynb
from backtest.engine import BacktestEngine
from backtest.data_provider import DataProvider
from strategies.moving_average import MovingAverageCross

# 1. 获取数据
dp = DataProvider()
data = dp.get_daily_bars('000001.SZ', '2023-01-01', '2024-12-31')

# 2. 定义策略
strategy = MovingAverageCross(fast=10, slow=30)

# 3. 回测
engine = BacktestEngine(initial_cash=100000)
result = engine.run_single(strategy, data)

# 4. 查看结果
print(result['metrics'])
result['pf'].plot().show()
```

### Web 界面操作

1. 选择股票代码
2. 选择策略（下拉菜单）
3. 调整参数（滑块/输入框）
4. 点击「回测」
5. 查看：收益曲线、回撤图、交易记录、绩效指标

---

## 五、策略库管理

### 目录结构

```
strategies/
├── __init__.py          # 自动发现所有策略
├── base.py              # 基类
├── utils/               # 策略工具函数
│   ├── indicators.py    # 自定义指标
│   └── filters.py       # 过滤条件
├── trend_following/     # 趋势跟踪策略
│   ├── ma_cross.py
│   └── macd_trend.py
├── mean_reversion/      # 均值回归策略
│   ├── rsi_reversal.py
│   └── bollinger.py
└── breakout/            # 突破策略
    └── volume_breakout.py
```

### 策略注册机制

```python
# strategies/__init__.py
import importlib
import os
from pathlib import Path

def load_strategy(name: str):
    """动态加载策略类"""
    # 遍历所有子目录找对应策略
    for root, dirs, files in os.walk(Path(__file__).parent):
        for file in files:
            if file.endswith('.py') and not file.startswith('_'):
                module_path = os.path.join(root, file)
                # 动态导入...
```

---

## 六、实施建议

### Phase 1：MVP（1-2 天）
- [ ] 安装 vectorbt：`pip install vectorbt`
- [ ] 创建 `strategies/base.py` 基类
- [ ] 实现 1 个示例策略（均线交叉）
- [ ] 创建 `backtest/engine.py` 核心引擎
- [ ] 写 1 个 Jupyter Notebook 验证流程

### Phase 2：Playground 界面（2-3 天）
- [ ] 后端 API：`/api/backtest/run`, `/api/backtest/strategies`
- [ ] 前端页面：策略选择、参数调整、结果展示
- [ ] 图表：收益曲线、回撤、交易标记

### Phase 3：策略库（持续）
- [ ] 迁移现有分析逻辑为策略
- [ ] 添加参数扫描功能
- [ ] 支持多因子组合
- [ ] 实盘信号对接（后续）

---

## 七、依赖安装

```bash
cd /root/data/FinanceDashboard/backend
source venv/bin/activate

# 核心回测库
pip install vectorbt

# 图表（Jupyter 用）
pip install plotly

# 可选：性能优化
pip install numba
```

---

## 八、与现有系统整合

| 现有功能 | 回测系统复用 |
|---------|-------------|
| Tushare Token | 直接复用 |
| 股票列表/元数据 | 复用 `data/{code}/meta.json` |
| 用户认证 | 复用 `auth.py` |
| 前端框架 | 复用 Vue3 组件 |
| 数据目录 | 共用 `data/` 结构 |

---

总结：**不要自己写回测引擎，用 vectorbt 做核心计算，自己只写策略接口和 Playground 封装。** 这样最快，也最不容易出 bug。

要我直接开始写代码吗？ 🔥
