"""项目文件系统 — JSON 序列化"""

import json
import os
import re
import tempfile
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, Literal
from uuid import uuid4

from core.frame_style import FrameStyle

# ── 速度选项 ──────────────────────────────────────────────
SPEED_OPTIONS = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0]

# ── 宽高比预设 ────────────────────────────────────────────
ASPECT_RATIO_PRESETS = [
    "native", "16:9", "9:16", "1:1", "4:3", "4:5", "16:10", "10:16",
]
AspectRatio = str  # 预设值之一 或 "W:H" 自定义

# ── 缩放深度 ────────────────────────────────────────────
ZoomDepth = int  # 1-6
ZOOM_DEPTH_SCALES = {1: 1.25, 2: 1.5, 3: 1.8, 4: 2.2, 5: 3.5, 6: 5.0}
DEFAULT_ZOOM_DEPTH = 3


@dataclass
class Clip:
    id: str = ""
    type: str = "video"
    start: float = 0.0
    end: float = 0.0
    source_start: float = 0.0
    source_end: float | None = None
    source_path: str = ""
    speed: float = 1.0
    volume: float = 1.0
    content: str = ""
    rect: list[int] | None = None
    x: int = 0
    y: int = 0
    font_size: int = 24
    color: str = "white"
    transition_duration: float = 0.4


@dataclass
class Track:
    type: str = "video"
    name: str = ""
    clips: list[Clip] = field(default_factory=list)

    def __post_init__(self):
        self.clips = [
            Clip(**c) if isinstance(c, dict) else c
            for c in self.clips
        ]


# ── 标注数据模型 ───────────────────────────────────────────

AnnotationType = Literal["text", "image", "figure", "blur"]
ArrowDirection = Literal[
    "up", "down", "left", "right",
    "up-right", "up-left", "down-right", "down-left",
]


@dataclass
class FigureData:
    arrow_direction: ArrowDirection = "right"
    color: str = "#ff0000"
    stroke_width: int = 3


@dataclass
class AnnotationRegion:
    id: str = ""
    type: AnnotationType = "text"
    start_ms: float = 0.0
    end_ms: float = 0.0
    content: str = ""          # 文本内容 或 图片 data URL
    x: float = 50.0            # 百分比 0-100
    y: float = 50.0            # 百分比 0-100
    width: float = 30.0        # 百分比 1-200
    height: float = 10.0       # 百分比 1-200
    font_size: int = 24
    color: str = "#ffffff"
    bg_color: str = "transparent"
    font_family: str = "sans-serif"
    bold: bool = False
    italic: bool = False
    underline: bool = False
    text_align: str = "left"
    z_index: int = 0
    figure_data: FigureData | None = None
    blur_intensity: int = 50   # 1-100
    blur_color: str = "#000000"


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
class CropRegion:
    """裁剪区域，归一化 0-1 坐标"""
    x: float = 0.0
    y: float = 0.0
    width: float = 1.0
    height: float = 1.0


# ── 额外音频数据模型 ───────────────────────────────────────

@dataclass
class AudioRegion:
    id: str = ""
    start_ms: float = 0.0
    end_ms: float = 0.0
    source_start_ms: float = 0.0
    source_end_ms: float | None = None
    audio_path: str = ""
    volume: float = 1.0       # 0-1
    name: str = ""


def sync_audio_regions_from_clips(
        clips: list[Clip], regions: list[AudioRegion]) -> list[AudioRegion]:
    """以时间线音频 Clip 为唯一事实源，同步导出区域。"""
    existing = {region.id: region for region in regions}
    synced = []
    for clip in clips:
        if not clip.id:
            clip.id = str(uuid4())
        region = existing.get(clip.id)
        if region is None:
            region = AudioRegion(id=clip.id)

        source_end = clip.source_end
        if source_end is None:
            source_end = clip.source_start + (
                clip.end - clip.start) * max(clip.speed, 0.0001)

        region.start_ms = round(clip.start * 1000)
        region.end_ms = round(clip.end * 1000)
        region.source_start_ms = round(clip.source_start * 1000)
        region.source_end_ms = round(source_end * 1000)
        region.audio_path = clip.source_path or region.audio_path
        region.volume = clip.volume
        region.name = clip.content or os.path.basename(region.audio_path)
        synced.append(region)
    return synced


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

    VERSION = "1.0.3"

    def __init__(self):
        self.version = self.VERSION
        self.created_at = datetime.now().isoformat()
        self.name: str = ""
        self.modified_at: str = ""
        self.duration: float = 0.0
        self.thumbnail_path: str = ""
        self.source: Optional[SourceInfo] = None
        self.timeline: list[Track] = []
        self.cursor = CursorSettings()
        self.frame_style = FrameStyle()
        self.filepath: str = ""
        self.annotations: list[AnnotationRegion] = []
        self.audio_regions: list[AudioRegion] = []
        self.crop_region: Optional[CropRegion] = None
        self.aspect_ratio: AspectRatio = "native"
        # 录制原始数据
        self.cursor_events: list = []          # [[x, y, timestamp], ...]
        self.click_events: list = []           # [[x, y, timestamp], ...]
        self.monitor_offset: list = [0, 0]     # [left, top]

    def save(self, path: str):
        """原子保存 project.json：写临时文件 → os.replace 原子替换。
        写入失败时原 project.json 不受影响。"""
        frame_style_dict = asdict(self.frame_style)
        bg = self.frame_style.bg_color
        if isinstance(bg, tuple) and len(bg) == 3:
            frame_style_dict["bg_color"] = f"#{bg[0]:02x}{bg[1]:02x}{bg[2]:02x}"

        data = {
            "version": self.version,
            "created_at": self.created_at,
            "name": self.name,
            "modified_at": datetime.now().isoformat(),
            "duration": self.duration,
            "thumbnail_path": self.thumbnail_path,
            "source": asdict(self.source) if self.source else None,
            "timeline": [asdict(t) for t in self.timeline],
            "cursor": asdict(self.cursor),
            "frame_style": frame_style_dict,
            "annotations": [asdict(a) for a in self.annotations],
            "audio_regions": [asdict(a) for a in self.audio_regions],
            "crop_region": asdict(self.crop_region) if self.crop_region else None,
            "aspect_ratio": self.aspect_ratio,
            "cursor_events": self.cursor_events,
            "click_events": self.click_events,
            "monitor_offset": self.monitor_offset,
            "frame_count": getattr(self, "_frame_count", 0),
        }
        dir_path = os.path.dirname(path) or "."
        os.makedirs(dir_path, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=dir_path, prefix=".project-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
        self.filepath = path

    @classmethod
    def load(cls, path: str) -> "Project":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        _validate_schema(data)

        proj = cls()
        proj.version = data.get("version", "1.0")
        proj.created_at = data.get("created_at", "")
        proj.name = data.get("name", "")
        proj.modified_at = data.get("modified_at", "")
        proj.duration = data.get("duration", 0.0)
        proj.thumbnail_path = data.get("thumbnail_path", "")
        if data.get("source"):
            proj.source = SourceInfo(**data["source"])
        proj.timeline = [Track(**t) for t in data.get("timeline", [])]
        cursor_data = data.get("cursor")
        proj.cursor = CursorSettings(**cursor_data) if isinstance(cursor_data, dict) else CursorSettings()
        proj.frame_style = _load_frame_style(data.get("frame_style", {}))
        proj.filepath = path
        proj.annotations = [AnnotationRegion(**a) for a in data.get("annotations", [])]
        proj.audio_regions = [AudioRegion(**a) for a in data.get("audio_regions", [])]
        if data.get("crop_region"):
            proj.crop_region = CropRegion(**data["crop_region"])
        proj.aspect_ratio = data.get("aspect_ratio", "native")
        proj.cursor_events = data.get("cursor_events", [])
        proj.click_events = data.get("click_events", [])
        proj.monitor_offset = data.get("monitor_offset", [0, 0])
        proj._frame_count = data.get("frame_count", 0)
        return proj


_HEX_COLOR_RE = re.compile(r'^#[0-9A-Fa-f]{6}$')

_KNOWN_TOP_KEYS = {
    "version", "created_at", "name", "modified_at", "duration",
    "thumbnail_path", "source", "timeline", "cursor", "frame_style",
    "annotations", "audio_regions", "crop_region", "aspect_ratio",
    "cursor_events", "click_events", "monitor_offset", "frame_count",
}

_KNOWN_CURSOR_KEYS = {"smooth", "trail", "ripple", "sway", "blur", "style"}

_KNOWN_FRAMESTYLE_KEYS = {
    "background", "bg_color", "bg_gradient", "bg_wallpaper",
    "padding", "corner_radius", "shadow", "shadow_offset",
    "shadow_blur", "shadow_opacity",
}


def _validate_schema(data: dict):
    unknown_top = set(data.keys()) - _KNOWN_TOP_KEYS
    if unknown_top:
        raise ValueError(
            f"project.json 包含未知字段: {', '.join(sorted(unknown_top))}。"
            f"项目格式不兼容，请使用支持的 Recordly 版本打开。"
        )

    cursor_data = data.get("cursor")
    if isinstance(cursor_data, dict):
        unknown_cursor = set(cursor_data.keys()) - _KNOWN_CURSOR_KEYS
        if unknown_cursor:
            raise ValueError(
                f"project.json cursor 字段包含未知键: {', '.join(sorted(unknown_cursor))}"
            )

    frame_data = data.get("frame_style")
    if isinstance(frame_data, dict):
        unknown_frame = set(frame_data.keys()) - _KNOWN_FRAMESTYLE_KEYS
        if unknown_frame:
            raise ValueError(
                f"project.json frame_style 字段包含未知键: {', '.join(sorted(unknown_frame))}"
            )


def _load_frame_style(data: dict) -> FrameStyle:
    """从 JSON 数据加载 FrameStyle。bg_color 编码: JSON #RRGGBB → 运行时 tuple"""
    data = dict(data)
    bg_color = data.get("bg_color")
    if isinstance(bg_color, str):
        if not _HEX_COLOR_RE.match(bg_color):
            raise ValueError(f"无效的 bg_color 格式: '{bg_color}'，需要 #RRGGBB")
        r = int(bg_color[1:3], 16)
        g = int(bg_color[3:5], 16)
        b = int(bg_color[5:7], 16)
        data["bg_color"] = (r, g, b)
    elif isinstance(bg_color, (list, tuple)):
        data["bg_color"] = tuple(bg_color)
    else:
        data.pop("bg_color", None)
    return FrameStyle(**data)
