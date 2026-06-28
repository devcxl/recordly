"""全局配置系统"""

import os
from dataclasses import dataclass, field

try:
    from PyQt5.QtCore import QSettings
    HAS_QT = True
except ImportError:
    HAS_QT = False
    # 降级：内存字典模拟 QSettings
    class QSettings:
        def __init__(self, *args, **kwargs): self._data = {}
        def value(self, key, default=None):
            return self._data.get(key, default)
        def setValue(self, key, value):
            self._data[key] = value
        def sync(self): pass


@dataclass
class AppConfig:
    recordings_dir: str = "~/Recordly/recordings"
    projects_dir: str = "~/Recordly/projects"
    default_fps: int = 30
    default_bitrate: str = "10M"
    language: str = "zh_CN"
    preview_quality: float = 0.5
    cursor_size: int = 32
    cursor_theme: str = "dark"
    trail_enabled: bool = True
    zoom_rect_ratio: float = 0.5

    @classmethod
    def load(cls) -> "AppConfig":
        s = QSettings("Recordly", "Recordly")
        cfg = cls()
        cfg.recordings_dir = s.value("recordings_dir", cls.recordings_dir)
        cfg.projects_dir = s.value("projects_dir", cls.projects_dir)
        cfg.default_fps = int(s.value("default_fps", cls.default_fps))
        cfg.default_bitrate = s.value("default_bitrate", cls.default_bitrate)
        cfg.language = s.value("language", cls.language)
        cfg.preview_quality = float(s.value("preview_quality", cls.preview_quality))
        cfg.cursor_size = int(s.value("cursor_size", cls.cursor_size))
        cfg.cursor_theme = s.value("cursor_theme", cls.cursor_theme)
        cfg.trail_enabled = s.value("trail_enabled", "true").lower() == "true"
        cfg.zoom_rect_ratio = float(s.value("zoom_rect_ratio", cls.zoom_rect_ratio))
        cfg.recordings_dir = os.path.expanduser(cfg.recordings_dir)
        cfg.projects_dir = os.path.expanduser(cfg.projects_dir)
        return cfg

    def save(self):
        s = QSettings("Recordly", "Recordly")
        s.setValue("recordings_dir", self.recordings_dir)
        s.setValue("projects_dir", self.projects_dir)
        s.setValue("default_fps", self.default_fps)
        s.setValue("default_bitrate", self.default_bitrate)
        s.setValue("language", self.language)
        s.setValue("preview_quality", self.preview_quality)
        s.setValue("cursor_size", self.cursor_size)
        s.setValue("cursor_theme", self.cursor_theme)
        s.setValue("trail_enabled", "true" if self.trail_enabled else "false")
        s.setValue("zoom_rect_ratio", self.zoom_rect_ratio)
