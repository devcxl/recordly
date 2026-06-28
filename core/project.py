"""项目文件系统 — JSON 序列化"""

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional


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


@dataclass
class FrameStyle:
    background: str = "solid"      # solid / gradient / wallpaper
    bg_color: tuple = (26, 26, 26)
    padding: int = 40
    corner_radius: int = 16
    shadow: bool = True


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
        proj.frame_style = FrameStyle(**data.get("frame_style", {}))
        proj.filepath = path
        return proj
