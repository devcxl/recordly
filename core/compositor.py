"""帧合成器 — 统一合成管线"""

import bisect
import logging
import math
from abc import ABC, abstractmethod
from collections import OrderedDict
from dataclasses import dataclass
from typing import Generator

from PIL import Image

from core.cursor_zoom_mixin import CursorZoomMixin
from core.frame_loading_mixin import FrameLoadingMixin
from core.screen_capture import CapturedFrame

logger = logging.getLogger(__name__)


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
    render_scale: float = 1.0
    render_timestamp: float | None = None
    reference_fps: float = 60.0


class Effect(ABC):
    @abstractmethod
    def apply(self, frame: Image.Image,
              ctx: CompositorContext) -> Image.Image:
        ...


class Compositor(FrameLoadingMixin, CursorZoomMixin):
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
        self._manual_zoom_clips: list | None = None
        self._camera = None
        self._effects: dict[str, Effect] = {}
        self._frame_index = 0
        self._preview_quality = 0.5
        self._base_time = 0.0
        self._frame_times: list[float] = []
        self._clips: list | None = None
        self._timeline_duration: float | None = None
        self._preview_cache: OrderedDict[int, Image.Image] = OrderedDict()
        self._preview_cache_limit = 24
        self._crop_region = None  # CropRegion | None
        self._monitor_left = 0
        self._monitor_top = 0
        self._frames_data_handle = None

    @property
    def frames(self): return self._frames
    @frames.setter
    def frames(self, v):
        self._close_frames_data()
        self._frames = v

    @property
    def clips(self) -> list | None:
        """已加载的时间线 clip 列表（zoom 合成用），无则 None。"""
        return self._clips

    @property
    def cursor_events(self): return self._cursor_events
    @cursor_events.setter
    def cursor_events(self, v): self._cursor_events = v

    @property
    def click_events(self): return self._click_events
    @click_events.setter
    def click_events(self, v): self._click_events = v

    @property
    def frame_times(self): return self._frame_times
    @frame_times.setter
    def frame_times(self, v): self._frame_times = v

    @property
    def crop_region(self): return self._crop_region
    @crop_region.setter
    def crop_region(self, v): self._crop_region = v

    @property
    def monitor_left(self): return self._monitor_left
    @property
    def monitor_top(self): return self._monitor_top

    def load_camera(self, camera):
        self._camera = camera
        self.clear_preview_cache()

    def load_manual_zoom_clips(self, clips: list):
        self._manual_zoom_clips = sorted(clips or [], key=lambda c: c.start)
        self.clear_preview_cache()

    def load_clips(self, clips: list, timeline_duration: float | None = None):
        """加载时间线 video clip 列表（用于速度感知渲染）。
        timeline_duration: 时间线总时长（含 audio_extra 等非 video 轨道尾部），
        为 None 时退化为按 video clip 末点计算。"""
        self._clips = sorted(clips or [], key=lambda c: c.start)
        self._timeline_duration = timeline_duration
        self.clear_preview_cache()

    def set_crop(self, crop):
        self._crop_region = crop
        self.clear_preview_cache()

    def register_effect(self, name: str, effect: Effect):
        self._effects[name] = effect

    def unregister_effect(self, name: str):
        self._effects.pop(name, None)

    # ── 合成 ──────────────────────────────────────────────

    def prepare_frame(self, frame: CapturedFrame,
                      timeline_ts: float | None = None,
                      preview: bool = False,
                      output_size: tuple[int, int] | None = None,
                      output_mode: str | None = None,
                      frame_index: int | None = None
                      ) -> tuple[Image.Image, CompositorContext]:
        try:
            img = Image.fromarray(frame.data, mode="RGB")
        except RuntimeError:
            logger.warning("帧 %d 解码失败，使用黑帧兜底", frame.index)
            img = Image.new("RGB", (self.width, self.height), (0, 0, 0))
        source_ts = frame.timestamp - self._base_time
        if timeline_ts is None:
            timeline_ts = source_ts
        w, h = self.width, self.height
        target_w, target_h = output_size or (w, h)
        direct_resize = output_size is not None and self._crop_region is None

        cx, cy = self._interpolate_cursor(source_ts)

        zoom = self._get_zoom_at(timeline_ts, source_ts) or self._zoom_rect
        zoom_cx, zoom_cy = cx, cy
        if zoom:
            zx, zy, zw, zh = zoom
            zx = max(0, min(zx, w - zw))
            zy = max(0, min(zy, h - zh))
            zoom = (zx, zy, zw, zh)
            img = self._resize_crop(
                img, (zx, zy, zx + zw, zy + zh), preview,
                size=(target_w, target_h) if direct_resize else (w, h),
                zoom=True,
            )
            zoom_cx, zoom_cy = self._transform_point(
                cx, cy, w, h, zoom=zoom)

        # 裁剪（缩放之后、效果之前）
        crop_rect = None
        if self._crop_region is not None:
            cr = self._crop_region
            if cr.width < 1.0 or cr.height < 1.0:
                cx_c = int(cr.x * w)
                cy_c = int(cr.y * h)
                cw_c = max(2, int(cr.width * w))
                ch_c = max(2, int(cr.height * h))
                crop_rect = (cx_c, cy_c, cw_c, ch_c)
                img = self._resize_crop(
                    img, (cx_c, cy_c, cx_c + cw_c, cy_c + ch_c),
                    preview, size=(w, h),
                )
                zoom_cx, zoom_cy = self._transform_point(
                    zoom_cx, zoom_cy, w, h, crop_rect=crop_rect)

        if img.size != (target_w, target_h):
            img = img.resize(
                (target_w, target_h), self._resize_filter(preview))

        scale_x = target_w / max(w, 1)
        scale_y = target_h / max(h, 1)
        zoom_cx = round(zoom_cx * scale_x)
        zoom_cy = round(zoom_cy * scale_y)

        transformed_clicks = []
        for click_x, click_y, click_ts in self._click_events:
            point_x = click_x - self._monitor_left
            point_y = click_y - self._monitor_top
            point_x, point_y = self._transform_point(
                point_x, point_y, w, h, zoom=zoom,
                crop_rect=crop_rect)
            transformed_clicks.append((
                round(point_x * scale_x), round(point_y * scale_y), click_ts))

        if output_mode is None and img.mode != "RGBA":
            img = img.convert("RGBA")

        ctx = CompositorContext(
            frame=img,
            cursor_x=zoom_cx, cursor_y=zoom_cy,
            cursor_state=self._cursor_state,
            click_events=transformed_clicks,
            frame_index=(self._frame_index if frame_index is None
                         else frame_index),
            timestamp=source_ts,
            zoom_rect=zoom,
            width=target_w, height=target_h,
            raw_cursor_x=cx, raw_cursor_y=cy,
            render_scale=min(scale_x, scale_y),
            render_timestamp=timeline_ts,
            reference_fps=self.fps,
        )
        return img, ctx

    def apply_effects(self, img: Image.Image, ctx: CompositorContext,
                      output_mode: str | None = None) -> Image.Image:
        for name, effect in self._effects.items():
            img = effect.apply(img, ctx)
        if output_mode is not None and img.mode != output_mode:
            img = img.convert(output_mode)
        return img

    def compose(self, frame: CapturedFrame,
                timeline_ts: float | None = None,
                preview: bool = False,
                output_size: tuple[int, int] | None = None,
                output_mode: str | None = None) -> Image.Image:
        img, ctx = self.prepare_frame(
            frame, timeline_ts, preview, output_size, output_mode)
        img = self.apply_effects(img, ctx, output_mode)

        self._frame_index += 1
        return img

    def compose_index(self, idx: int) -> Image.Image | None:
        cached = self._preview_cache.get(idx)
        if cached is not None:
            self._preview_cache.move_to_end(idx)
            return cached
        frame = self._compose_index_uncached(idx)
        if frame is not None:
            self._preview_cache[idx] = frame
            while len(self._preview_cache) > self._preview_cache_limit:
                self._preview_cache.popitem(last=False)
        return frame

    def _compose_index_uncached(self, idx: int) -> Image.Image | None:
        if self._clips is not None:
            if 0 <= idx < self.total_output_frames:
                source_idx = self._source_index_at(idx / self.fps)
                if source_idx is None:
                    return Image.new("RGBA", (self.width, self.height),
                                     (0, 0, 0, 255))
                return self.compose(
                    self._frames[source_idx], idx / self.fps, preview=True)
            return None
        if 0 <= idx < len(self._frames):
            return self.compose(self._frames[idx], idx / self.fps, preview=True)
        return None

    def clear_preview_cache(self):
        """剪辑/参数变更后使预览缓存失效。"""
        self._preview_cache.clear()

    @property
    def total_output_frames(self) -> int:
        return self.total_output_frames_for(self.fps)

    def total_output_frames_for(self, render_fps: float) -> int:
        if render_fps <= 0:
            return 0
        if self._clips:
            duration = max(c.end for c in self._clips)
            if self._timeline_duration is not None:
                duration = max(duration, self._timeline_duration)
        else:
            duration = self.source_duration
            if duration <= 0 and self._frames:
                duration = len(self._frames) / self.fps
        return max(0, math.ceil(duration * render_fps))

    def _source_index_at(self, timeline_ts: float) -> int | None:
        """将时间线时刻映射到源帧；空洞返回 None。"""
        clip = next((
            candidate for candidate in reversed(self._clips)
            if candidate.start <= timeline_ts < candidate.end
        ), None)
        if clip is None:
            return None

        source_time = clip.source_start + (
            timeline_ts - clip.start) * max(clip.speed, 0.0001)
        if clip.source_end is not None:
            source_time = min(source_time, max(clip.source_start,
                                               clip.source_end - 1 / self.fps))
        if not self._frame_times or source_time < 0:
            return None
        position = bisect.bisect_left(self._frame_times, source_time)
        if position <= 0:
            return 0
        if position >= len(self._frame_times):
            return len(self._frame_times) - 1
        before = self._frame_times[position - 1]
        after = self._frame_times[position]
        return position - 1 if source_time - before <= after - source_time else position

    def iter_frame_meta(self, start: int = 0, end: int | None = None,
                        render_fps: float | None = None):
        """并行导出用的帧迭代器，返回 (序号, 原始帧或None, 时间线时间戳)。
        与 render_all 不同，不调用 compose()，由调用方在子线程中 compose。"""
        fps = render_fps or self.fps
        total = self.total_output_frames_for(fps)
        output_end = total if end is None else min(end, total)
        for output_idx in range(max(0, start), output_end):
            ts = output_idx / fps
            source_idx = (self._source_index_at(ts) if self._clips
                          else self._nearest_source_index(ts))
            if source_idx is None:
                yield output_idx, None, ts
            else:
                yield output_idx, self._frames[source_idx], ts

    def _nearest_source_index(self, source_time: float) -> int | None:
        if not self._frame_times or source_time < 0:
            return None
        position = bisect.bisect_left(self._frame_times, source_time)
        if position <= 0:
            return 0
        if position >= len(self._frame_times):
            return len(self._frame_times) - 1
        before = self._frame_times[position - 1]
        after = self._frame_times[position]
        return position - 1 if source_time - before <= after - source_time else position

    def render_all(self, start: int = 0, end: int = None
                   ) -> Generator[Image.Image, None, None]:
        if not self._clips:
            frames = self._frames[start:end]
            for offset, frame in enumerate(frames, start=start):
                yield self.compose(frame, offset / self.fps)
            return

        output_end = self.total_output_frames if end is None else min(
            end, self.total_output_frames)
        for output_idx in range(max(0, start), output_end):
            source_idx = self._source_index_at(output_idx / self.fps)
            if source_idx is None:
                yield Image.new("RGBA", (self.width, self.height),
                                (0, 0, 0, 255))
            else:
                yield self.compose(
                    self._frames[source_idx], output_idx / self.fps)

    def set_preview_quality(self, quality: float):
        self._preview_quality = max(0.1, min(1.0, quality))
        self.clear_preview_cache()

    def _resize_filter(self, preview: bool, zoom: bool = False):
        if zoom:
            return Image.BILINEAR
        if not preview:
            return Image.LANCZOS
        if self._preview_quality >= 0.75:
            return Image.BICUBIC
        return Image.BILINEAR

    def _resize_crop(self, image: Image.Image, box: tuple,
                     preview: bool, size: tuple[int, int] | None = None,
                     zoom: bool = False) -> Image.Image:
        return image.crop(box).resize(
            size or (self.width, self.height),
            self._resize_filter(preview, zoom=zoom))

    def get_preview_quality(self) -> float:
        return self._preview_quality
