"""项目文件系统 — JSON 序列化"""

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

from core.frame_style import FrameStyle


@dataclass
class Track:
    type: str = "video"        # "video" / "audio" / "zoom" / "text" / "cursor"
    start: float = 0.0
    end: float = 0.0
    speed: float = 1.0
    content: str = ""
    rect: list[int] | None = None  # [x, y, w, h] for zoom
    x: int = 0
    y: int = 0
    font_size: int = 24
    color: str = "white"


@dataclass
class CursorSettings:
    smooth: bool = True
    trail: bool = False
    ripple: bool = True
    sway: bool = False
    blur: int = 0
    style: str = "macos-dark"


# FrameStyle 定义统一在 core/frame_style.py (commit 1: dedup) ✅
# 迁移说明：旧版 FrameStyle.bg_color 为 tuple (R,G,B)，新版为 str "#RRGGBB"


@dataclass
class SourceInfo:
    video: str = ""
    audio_mic: str = ""
    audio_system: str = ""
    duration: float = 0.0
    fps: int = 30
    width: int = 1920
    height: int = 1080


class Project:
    """Recordly 项目文件模型"""

    VERSION = "1.0"

    def __init__(self):
        self.version = self.VERSION
        self.created_at = datetime.now().isoformat()
        self.source: Optional[SourceInfo] = None
        self.timeline: list[Track] = []
        self.cursor = CursorSettings()
        self.frame_style = FrameStyle()
        self.filepath: str = ""

    def save(self, path: str):
        data = {
            "version": self.version,
            "created_at": self.created_at,
            "source": asdict(self.source) if self.source else None,
            "timeline": [asdict(t) for t in self.timeline],
            "cursor": asdict(self.cursor),
            "frame_style": asdict(self.frame_style),
        }
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        self.filepath = path

    @classmethod
    def load(cls, path: str) -> "Project":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        proj = cls()
        proj.version = data.get("version", "1.0")
        proj.created_at = data.get("created_at", "")
        if data.get("source"):
            proj.source = SourceInfo(**data["source"])
        proj.timeline = [Track(**t) for t in data.get("timeline", [])]
        proj.cursor = CursorSettings(**data.get("cursor", {}))
        proj.frame_style = _load_frame_style(data.get("frame_style", {}))
        proj.filepath = path
        return proj


def _load_frame_style(data: dict) -> FrameStyle:
    """兼容旧版 FrameStyle，处理 bg_color 从 tuple 到 str 的迁移"""
    bg_color = data.get("bg_color")
    if isinstance(bg_color, (list, tuple)) and len(bg_color) == 3:
        data["bg_color"] = f"#{bg_color[0]:02x}{bg_color[1]:02x}{bg_color[2]:02x}"
    return FrameStyle(**data)
