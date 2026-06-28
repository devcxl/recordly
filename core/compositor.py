"""帧合成器 — 统一合成管线"""

from PIL import Image, ImageDraw
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Generator, Callable
import numpy as np
from core.screen_capture import CapturedFrame


@dataclass
class CompositorContext:
    frame: Image.Image
    cursor_x: int
    cursor_y: int
    cursor_state: str        # "idle" / "click" / "drag"
    click_events: list
    frame_index: int
    timestamp: float
    zoom_rect: tuple | None  # (x, y, w, h)
    width: int
    height: int


class Effect(ABC):
    """效果插件接口 — 所有效果继承此类"""

    @abstractmethod
    def apply(self, frame: Image.Image,
              ctx: CompositorContext) -> Image.Image:
        ...


class Compositor:
    """统一合成管线：预览与导出共用此合成器"""

    def __init__(self, width: int, height: int, fps: int = 30):
        self.width = width
        self.height = height
        self.fps = fps
        self._frames: list[CapturedFrame] = []
        self._cursor_x = width // 2
        self._cursor_y = height // 2
        self._cursor_state = "idle"
        self._click_events: list[tuple[int, int, float]] = []
        self._zoom_rect: tuple | None = None
        self._effects: dict[str, Effect] = {}
        self._frame_index = 0
        self._preview_quality = 0.5
        self._base_time = 0.0

    # ── 输入 ──────────────────────────────────────────────

    def load_frames(self, frames: list[CapturedFrame]):
        self._frames = list(frames)
        if frames:
            self._base_time = frames[0].timestamp
            self.width = frames[0].data.shape[1]
            self.height = frames[0].data.shape[0]

    def set_cursor(self, x: int, y: int, state: str = "idle"):
        self._cursor_x = max(0, min(x, self.width))
        self._cursor_y = max(0, min(y, self.height))
        self._cursor_state = state

    def add_click(self, x: int, y: int, ts: float):
        self._click_events.append((x, y, ts))

    def set_zoom(self, rect: tuple | None):
        self._zoom_rect = rect

    def register_effect(self, name: str, effect: Effect):
        self._effects[name] = effect

    def unregister_effect(self, name: str):
        self._effects.pop(name, None)

    # ── 合成 ──────────────────────────────────────────────

    def compose(self, frame: CapturedFrame) -> Image.Image:
        """合成单帧"""
        # numpy → PIL
        img = Image.fromarray(frame.data, mode="RGB")
        ts = frame.timestamp - self._base_time

        # zoom/pan
        if self._zoom_rect:
            x, y, w, h = self._zoom_rect
            img = img.crop((x, y, x + w, y + h))
            img = img.resize((self.width, self.height), Image.LANCZOS)

        if img.mode != "RGBA":
            img = img.convert("RGBA")

        ctx = CompositorContext(
            frame=img,
            cursor_x=self._cursor_x,
            cursor_y=self._cursor_y,
            cursor_state=self._cursor_state,
            click_events=self._click_events,
            frame_index=self._frame_index,
            timestamp=ts,
            zoom_rect=self._zoom_rect,
            width=self.width,
            height=self.height,
        )

        for name, effect in self._effects.items():
            img = effect.apply(img, ctx)

        self._frame_index += 1
        return img

    def compose_index(self, idx: int) -> Image.Image | None:
        """按帧索引合成"""
        if 0 <= idx < len(self._frames):
            return self.compose(self._frames[idx])
        return None

    # ── 导出迭代器 ─────────────────────────────────────────

    def render_all(self, start: int = 0, end: int = None
                   ) -> Generator[Image.Image, None, None]:
        """逐帧合成生成器，用于导出"""
        frames = self._frames[start:end]
        for f in frames:
            yield self.compose(f)

    # ── 预览控制 ──────────────────────────────────────────

    def set_preview_quality(self, quality: float):
        self._preview_quality = max(0.1, min(1.0, quality))

    def get_preview_quality(self) -> float:
        return self._preview_quality
