"""帧合成器 — 统一合成管线"""

import bisect
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
    cursor_state: str
    click_events: list
    frame_index: int
    timestamp: float
    zoom_rect: tuple | None
    width: int
    height: int
    raw_cursor_x: int = 0
    raw_cursor_y: int = 0


class Effect(ABC):
    @abstractmethod
    def apply(self, frame: Image.Image,
              ctx: CompositorContext) -> Image.Image:
        ...


class Compositor:
    def __init__(self, width: int, height: int, fps: int = 30):
        self.width = width
        self.height = height
        self.fps = fps
        self._frames: list[CapturedFrame] = []
        self._cursor_events = []
        self._cursor_x = width // 2
        self._cursor_y = height // 2
        self._cursor_state = "idle"
        self._click_events: list[tuple[int, int, float]] = []
        self._zoom_rect: tuple | None = None
        self._zoom_keyframes: list[tuple[float, int, int, int, int]] = []
        self._manual_zoom_clips: list = []
        self._camera = None
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

    def load_cursor_events(self, events: list, clicks: list):
        self._cursor_events = events or []
        self._click_events = []
        for e in clicks or []:
            self._click_events.append((e.x, e.y, e.timestamp - self._base_time))

    def set_cursor(self, x: int, y: int, state: str = "idle"):
        self._cursor_x = max(0, min(x, self.width))
        self._cursor_y = max(0, min(y, self.height))
        self._cursor_state = state

    def add_click(self, x: int, y: int, ts: float):
        self._click_events.append((x, y, ts))

    def set_zoom(self, rect: tuple | None):
        self._zoom_rect = rect

    def load_camera(self, camera):
        """加载智能镜头系统，替代旧 keyframe 方案"""
        self._camera = camera

    def load_manual_zoom_clips(self, clips: list):
        self._manual_zoom_clips = sorted(clips or [],
                                         key=lambda c: c.start)

    def register_effect(self, name: str, effect: Effect):
        self._effects[name] = effect

    def unregister_effect(self, name: str):
        self._effects.pop(name, None)

    # ── 合成 ──────────────────────────────────────────────

    def _interpolate_cursor(self, ts: float) -> tuple[int, int]:
        """根据帧时间戳插值出当前帧的鼠标位置"""
        if not self._cursor_events:
            return self._cursor_x, self._cursor_y
        events = self._cursor_events
        target = self._base_time + ts
        if target <= events[0].timestamp:
            return events[0].x, events[0].y
        if target >= events[-1].timestamp:
            return events[-1].x, events[-1].y
        for i in range(1, len(events)):
            if events[i].timestamp >= target:
                e0, e1 = events[i - 1], events[i]
                if e1.timestamp == e0.timestamp:
                    return e1.x, e1.y
                t = (target - e0.timestamp) / (e1.timestamp - e0.timestamp)
                return int(e0.x + (e1.x - e0.x) * t), int(e0.y + (e1.y - e0.y) * t)
        return events[-1].x, events[-1].y

    def _interpolate_cursor_raw(self, rel_ts: float) -> tuple[int, int]:
        """按相对时间插值光标位置（用于 keyframe 生成）"""
        target = self._base_time + rel_ts
        events = self._cursor_events
        if not events:
            return self._cursor_x, self._cursor_y
        if target <= events[0].timestamp:
            return events[0].x, events[0].y
        if target >= events[-1].timestamp:
            return events[-1].x, events[-1].y
        for i in range(1, len(events)):
            if events[i].timestamp >= target:
                e0, e1 = events[i - 1], events[i]
                if e1.timestamp == e0.timestamp:
                    return e1.x, e1.y
                t = (target - e0.timestamp) / (e1.timestamp - e0.timestamp)
                return int(e0.x + (e1.x - e0.x) * t), int(e0.y + (e1.y - e0.y) * t)
        return events[-1].x, events[-1].y

    def _get_zoom_at(self, ts: float) -> tuple | None:
        if self._manual_zoom_clips:
            starts = [c.start for c in self._manual_zoom_clips]
            i = bisect.bisect_right(starts, ts) - 1
            if i >= 0:
                c = self._manual_zoom_clips[i]
                if ts <= c.end and c.rect:
                    return tuple(c.rect)
        if not self._camera:
            return None
        w, h = self.width, self.height
        fx, fy, scale = self._camera.sample(ts * 1000)
        zw = int(w / scale)
        zh = int(h / scale)
        zx = int(fx * w - zw / 2)
        zy = int(fy * h - zh / 2)
        zx = max(0, min(zx, w - zw))
        zy = max(0, min(zy, h - zh))
        return (zx, zy, zw, zh)

    def compose(self, frame: CapturedFrame) -> Image.Image:
        img = Image.fromarray(frame.data, mode="RGB")
        ts = frame.timestamp - self._base_time
        w, h = self.width, self.height

        cx, cy = self._interpolate_cursor(ts)

        zoom = self._get_zoom_at(ts) or self._zoom_rect
        zoom_cx, zoom_cy = cx, cy
        if zoom:
            zx, zy, zw, zh = zoom
            # 保持视频宽高比
            target_ratio = w / h
            if zw / zh > target_ratio:
                new_zw = int(zh * target_ratio)
                zx += (zw - new_zw) // 2
                zw = new_zw
            elif zw / zh < target_ratio:
                new_zh = int(zw / target_ratio)
                zy += (zh - new_zh) // 2
                zh = new_zh
            zx = max(0, min(zx, w - zw))
            zy = max(0, min(zy, h - zh))
            zoom = (zx, zy, zw, zh)
            img = img.crop((zx, zy, zx + zw, zy + zh))
            img = img.resize((w, h), Image.LANCZOS)
            zoom_cx = int((cx - zx) * w / max(zw, 1))
            zoom_cy = int((cy - zy) * h / max(zh, 1))

        if img.mode != "RGBA":
            img = img.convert("RGBA")

        ctx = CompositorContext(
            frame=img,
            cursor_x=zoom_cx, cursor_y=zoom_cy,
            cursor_state=self._cursor_state,
            click_events=self._click_events,
            frame_index=self._frame_index,
            timestamp=ts,
            zoom_rect=zoom,
            width=w, height=h,
            raw_cursor_x=cx, raw_cursor_y=cy,
        )

        for name, effect in self._effects.items():
            img = effect.apply(img, ctx)

        self._frame_index += 1
        return img

    def compose_index(self, idx: int) -> Image.Image | None:
        if 0 <= idx < len(self._frames):
            return self.compose(self._frames[idx])
        return None

    def render_all(self, start: int = 0, end: int = None
                   ) -> Generator[Image.Image, None, None]:
        frames = self._frames[start:end]
        for f in frames:
            yield self.compose(f)

    def set_preview_quality(self, quality: float):
        self._preview_quality = max(0.1, min(1.0, quality))

    def get_preview_quality(self) -> float:
        return self._preview_quality
