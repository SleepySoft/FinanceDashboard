"""数据源抽象基类 — 支持 Tushare 和用户自定义库"""
from abc import ABC, abstractmethod
import pandas as pd
import os


class DataSource(ABC):
    """数据源抽象基类 — 支持 Tushare 和用户自定义库"""

    @abstractmethod
    def get_daily_bars(
        self,
        code: str,
        start: str,
        end: str,
        adjust: str = 'qfq',
    ) -> pd.DataFrame:
        """
        返回 OHLCV DataFrame，index 为日期
        必须处理复权
        """
        pass

    @abstractmethod
    def get_all_codes(self) -> list:
        """获取所有可交易股票代码列表"""
        pass

    @abstractmethod
    def get_name(self, code: str) -> str:
        """获取股票名称"""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """数据源名称"""
        pass


class TushareDataSource(DataSource):
    """Tushare 数据源实现"""

    name = "tushare"

    def __init__(self, token: str = None):
        import tushare as ts
        self.token = token or os.environ.get('TUSHARE_TOKEN')
        if not self.token:
            raise ValueError("Tushare token required. Set TUSHARE_TOKEN env or pass token.")
        ts.set_token(self.token)
        self.pro = ts.pro_api()
        self._stock_basic = None

    def get_daily_bars(self, code, start, end, adjust='qfq'):
        # Tushare 代码格式: 000001.SZ
        ts_code = code.upper().strip()
        adj_map = {'qfq': 'qfq', 'hfq': 'hfq', 'none': None}
        adj = adj_map.get(adjust)

        df = self.pro.pro_bar(
            ts_code=ts_code,
            start_date=start.replace('-', ''),
            end_date=end.replace('-', ''),
            adj=adj,
            freq='D'
        )
        return self._normalize(df)

    def _normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        """标准化 DataFrame 格式"""
        if df is None or df.empty:
            return pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume'])

        df = df.copy()
        df['trade_date'] = pd.to_datetime(df['trade_date'])
        df = df.sort_values('trade_date')
        df = df.set_index('trade_date')

        # 统一列名
        col_map = {}
        for c in df.columns:
            lc = c.lower()
            if lc in ['open', 'high', 'low', 'close', 'volume', 'amount']:
                col_map[c] = lc
        df = df.rename(columns=col_map)

        # 确保必要列存在
        for col in ['open', 'high', 'low', 'close', 'volume']:
            if col not in df.columns:
                df[col] = 0.0

        return df[['open', 'high', 'low', 'close', 'volume']]

    def get_all_codes(self) -> list:
        if self._stock_basic is None:
            self._stock_basic = self.pro.stock_basic(exchange='', list_status='L')
        return self._stock_basic['ts_code'].tolist()

    def get_name(self, code: str) -> str:
        if self._stock_basic is None:
            self._stock_basic = self.pro.stock_basic(exchange='', list_status='L')
        row = self._stock_basic[self._stock_basic['ts_code'] == code.upper()]
        if not row.empty:
            return row.iloc[0]['name']
        return code


class CachedDataSource(DataSource):
    """带本地缓存的数据源包装器"""

    def __init__(self, source: DataSource, cache_dir: str):
        self.source = source
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    @property
    def name(self) -> str:
        return f"cached_{self.source.name}"

    def _cache_key(self, code: str, start: str, end: str, adjust: str) -> str:
        import hashlib
        key = f"{code}_{start}_{end}_{adjust}"
        return hashlib.md5(key.encode()).hexdigest() + ".parquet"

    def get_daily_bars(self, code, start, end, adjust='qfq'):
        cache_file = os.path.join(self.cache_dir, self._cache_key(code, start, end, adjust))

        if os.path.exists(cache_file):
            try:
                df = pd.read_parquet(cache_file)
                # 检查日期范围是否满足
                if not df.empty:
                    df_start = df.index.min().strftime('%Y-%m-%d')
                    df_end = df.index.max().strftime('%Y-%m-%d')
                    if df_start <= start and df_end >= end:
                        mask = (df.index >= start) & (df.index <= end)
                        return df.loc[mask]
            except Exception:
                pass  # 缓存损坏，重新获取

        df = self.source.get_daily_bars(code, start, end, adjust)
        if not df.empty:
            try:
                df.to_parquet(cache_file)
            except Exception:
                pass
        return df

    def get_all_codes(self) -> list:
        return self.source.get_all_codes()

    def get_name(self, code: str) -> str:
        return self.source.get_name(code)


def get_data_source(source_type: str = 'tushare', **kwargs) -> DataSource:
    """工厂函数：获取数据源实例"""
    if source_type == 'tushare':
        ds = TushareDataSource(**kwargs)
    else:
        raise ValueError(f"Unknown data source: {source_type}")

    # 自动包装缓存
    cache_dir = kwargs.get('cache_dir', '/root/data/FinanceDashboard/data/backtest/bars_cache')
    return CachedDataSource(ds, cache_dir)
