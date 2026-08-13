"""异动检测插件基类

设计目标：
- 每个检测算法独立为一个插件
- 插件可任意组合、插拔
- 支持同时运行多个插件，结果聚合
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Optional
import pandas as pd


@dataclass
class Signal:
    """单个信号"""
    type: str           # 信号类型标识
    value: float        # 信号数值
    score: int          # 该信号贡献的分数
    desc: str           # 人类可读描述


@dataclass
class DetectionResult:
    """插件检测结果"""
    plugin_name: str
    score: int                      # 该插件贡献的总分
    signals: List[Signal] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)  # 额外数据（如突破类型/价位）
    triggered: bool = False         # 是否触发（即使分数低也可以记录）


class DetectorPlugin(ABC):
    """
    个股异动检测插件基类

    每个子类实现一种检测算法，如振幅检测、量比检测、突破检测等。
    Orchestrator 会调用所有已注册插件，聚合它们的 DetectionResult。
    """

    name: str = ""
    description: str = ""
    version: str = "1.0"

    # 默认阈值（子类可覆盖，也可通过 config 动态调整）
    default_threshold: float = 0.0
    default_score_weight: float = 1.0

    def __init__(self, config: Dict = None):
        """
        Args:
            config: 插件配置，可覆盖默认阈值等参数
        """
        self.config = config or {}

    @abstractmethod
    def detect(self, code: str, df: pd.DataFrame, today: pd.Series) -> Optional[DetectionResult]:
        """
        执行检测

        Args:
            code: 股票代码
            df: 历史数据 DataFrame（含多日均线等预处理数据）
            today: 当日数据 Series

        Returns:
            DetectionResult or None（未触发）
        """
        pass

    def _param(self, key: str, default=None):
        """读取配置参数，优先使用传入的 config，否则用默认值"""
        return self.config.get(key, getattr(self, f"default_{key}", default))


class SectorDetectorPlugin(ABC):
    """
    板块级检测插件基类

    与 DetectorPlugin 不同，SectorDetectorPlugin 接收的是一个板块内
    所有个股的数据，输出板块级别的异动判断。
    """

    name: str = ""
    description: str = ""

    def __init__(self, config: Dict = None):
        self.config = config or {}

    @abstractmethod
    def detect_sector(self, sector: str, stocks: List[Dict], trade_date: str) -> Optional[DetectionResult]:
        """
        检测单个板块

        Args:
            sector: 板块名称
            stocks: 板块内个股列表 [{code, name, change_pct, score, vol_ratio}, ...]
            trade_date: 交易日期

        Returns:
            DetectionResult or None
        """
        pass
