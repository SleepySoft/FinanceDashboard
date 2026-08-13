"""异动检测插件包

所有检测算法以插件形式存在，可插拔、可组合。
"""
from .base import DetectorPlugin, SectorDetectorPlugin, DetectionResult, Signal
from .amplitude import AmplitudeDetector
from .change import ChangeDetector
from .volume import VolumeDetector
from .breakout import BreakoutDetector
from .momentum import MomentumDetector
from .sector import SectorMomentumDetector

# 默认插件列表
DEFAULT_STOCK_PLUGINS = [
    AmplitudeDetector,
    ChangeDetector,
    VolumeDetector,
    BreakoutDetector,
    MomentumDetector,
]

DEFAULT_SECTOR_PLUGINS = [
    SectorMomentumDetector,
]

__all__ = [
    "DetectorPlugin",
    "SectorDetectorPlugin",
    "DetectionResult",
    "Signal",
    "AmplitudeDetector",
    "ChangeDetector",
    "VolumeDetector",
    "BreakoutDetector",
    "MomentumDetector",
    "SectorMomentumDetector",
    "DEFAULT_STOCK_PLUGINS",
    "DEFAULT_SECTOR_PLUGINS",
]
