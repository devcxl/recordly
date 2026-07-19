"""全局配置系统"""

import os
from dataclasses import dataclass, field

from core.shortcuts import ShortcutRegistry

try:
    from PyQt5.QtCore import QSettings
    from PyQt5.QtGui import QKeySequence
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


def _default_shortcuts() -> dict[str, str]:
    return ShortcutRegistry().bindings()


def _load_shortcut(value: object, default: str) -> str:
    if not isinstance(value, str) or not value:
        return default
    if not HAS_QT:
        return value

    portable_text = QKeySequence(
        value,
        QKeySequence.PortableText,
    ).toString(QKeySequence.PortableText)
    return portable_text or default


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
    cursor_style: str = "dot"
    trail_enabled: bool = True
    zoom_rect_ratio: float = 0.5
    shortcuts: dict[str, str] = field(default_factory=_default_shortcuts)

    def __post_init__(self):
        self.shortcuts = ShortcutRegistry(self.shortcuts).bindings()

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
        cfg.cursor_style = s.value("cursor_style", cls.cursor_style)
        cfg.trail_enabled = s.value("trail_enabled", "true").lower() == "true"
        cfg.zoom_rect_ratio = float(s.value("zoom_rect_ratio", cls.zoom_rect_ratio))
        for action in ShortcutRegistry().actions():
            value = s.value(f"shortcuts/{action.action_id}", None)
            cfg.shortcuts[action.action_id] = _load_shortcut(value, action.default_keys)
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
        s.setValue("cursor_style", self.cursor_style)
        s.setValue("trail_enabled", "true" if self.trail_enabled else "false")
        s.setValue("zoom_rect_ratio", self.zoom_rect_ratio)
        for action in ShortcutRegistry().actions():
            portable_text = _load_shortcut(
                self.shortcuts.get(action.action_id, action.default_keys),
                action.default_keys,
            )
            self.shortcuts[action.action_id] = portable_text
            s.setValue(
                f"shortcuts/{action.action_id}",
                portable_text,
            )
        s.sync()
