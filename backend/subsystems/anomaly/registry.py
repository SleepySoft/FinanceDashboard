"""插件注册表

管理所有已注册的检测插件，支持动态增删。
"""
from typing import List, Type, Dict, Optional

from .plugins.base import DetectorPlugin, SectorDetectorPlugin


class PluginRegistry:
    """
    插件注册表

    用法：
        registry = PluginRegistry()
        registry.register(AmplitudeDetector, {"threshold": 4.0})
        registry.register(VolumeDetector)

        # 运行检测
        for plugin in registry.stock_plugins:
            result = plugin.detect(code, df, today)
            ...
    """

    def __init__(self):
        self._stock_plugins: List[DetectorPlugin] = []
        self._sector_plugins: List[SectorDetectorPlugin] = []
        self._plugin_info: List[Dict] = []  # 元数据记录

    # ─── 注册 ──────────────────────────────────────────

    def register(self, plugin_cls: Type, config: Dict = None, name: str = None):
        """
        注册一个插件

        Args:
            plugin_cls: 插件类（继承 DetectorPlugin 或 SectorDetectorPlugin）
            config: 插件配置
            name: 可选自定义名称
        """
        config = config or {}
        instance = plugin_cls(config)
        display_name = name or instance.name or plugin_cls.__name__

        if isinstance(instance, DetectorPlugin):
            self._stock_plugins.append(instance)
        elif isinstance(instance, SectorDetectorPlugin):
            self._sector_plugins.append(instance)
        else:
            raise TypeError(f"Plugin must inherit DetectorPlugin or SectorDetectorPlugin: {plugin_cls}")

        self._plugin_info.append({
            "name": display_name,
            "class": plugin_cls.__name__,
            "type": "stock" if isinstance(instance, DetectorPlugin) else "sector",
            "config": config,
        })

    def register_defaults(self):
        """注册所有默认插件"""
        from .plugins import DEFAULT_STOCK_PLUGINS, DEFAULT_SECTOR_PLUGINS
        for cls in DEFAULT_STOCK_PLUGINS:
            self.register(cls)
        for cls in DEFAULT_SECTOR_PLUGINS:
            self.register(cls)

    def unregister(self, name: str):
        """按名称卸载插件"""
        self._stock_plugins = [p for p in self._stock_plugins if p.name != name]
        self._sector_plugins = [p for p in self._sector_plugins if p.name != name]
        self._plugin_info = [i for i in self._plugin_info if i["name"] != name]

    def clear(self):
        """清空所有插件"""
        self._stock_plugins.clear()
        self._sector_plugins.clear()
        self._plugin_info.clear()

    # ─── 查询 ──────────────────────────────────────────

    @property
    def stock_plugins(self) -> List[DetectorPlugin]:
        return self._stock_plugins.copy()

    @property
    def sector_plugins(self) -> List[SectorDetectorPlugin]:
        return self._sector_plugins.copy()

    def list_plugins(self) -> List[Dict]:
        """列出所有已注册插件的元数据"""
        return self._plugin_info.copy()

    def get_plugin(self, name: str) -> Optional[DetectorPlugin]:
        """按名称获取插件实例"""
        for p in self._stock_plugins + self._sector_plugins:
            if p.name == name:
                return p
        return None

    def __len__(self):
        return len(self._stock_plugins) + len(self._sector_plugins)
