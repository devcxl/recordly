"""帧合成器 — 统一合成管线"""

import bisect
import json
import math
import os
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
    render_scale: float = 1.0
    render_timestamp: float | None = None
    reference_fps: float = 60.0


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
        self._manual_zoom_clips: list | None = None
        self._camera = None
        self._effects: dict[str, Effect] = {}
        self._frame_index = 0
        self._preview_quality = 0.5
        self._base_time = 0.0
        self._frame_times: list[float] = []
        self._clips: list | None = None
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

    # ── 输入 ──────────────────────────────────────────────

    def load_frames(self, frames: list[CapturedFrame]):
        self._close_frames_data()
        self._frames = list(frames)
        if frames:
            self._base_time = frames[0].timestamp
            self._frame_times = [
                frame.timestamp - self._base_time for frame in frames
            ]
            try:
                self.width = frames[0].data.shape[1]
                self.height = frames[0].data.shape[0]
            except RuntimeError:
                # 首帧解码失败时保留已有尺寸，避免闪退
                pass
        else:
            self._frame_times = []

    def load_video(self, video_path: str, fps: float) -> int:
        """从 mp4/视频文件解码帧到 compositor。返回帧数。"""
        import cv2
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise FileNotFoundError(f"无法打开视频文件: {video_path}")

        frames: list[CapturedFrame] = []
        index = 0
        frame_interval = 1.0 / fps if fps > 0 else 1.0 / 30
        while True:
            ret, frame_bgr = cap.read()
            if not ret:
                break
            timestamp = index * frame_interval
            frames.append(CapturedFrame(
                data=frame_bgr, timestamp=timestamp, index=index,
            ))
            index += 1
        cap.release()

        if frames:
            self.load_frames(frames)
        return len(frames)

    def load_frames_data(self, store_path: str, frame_count: int, fps: float,
                         duration: float = 0.0,
                         cache_max_bytes: int = 256 * 1024 * 1024) -> int:
        """从 CompressedFrameStore 文件加载帧。返回帧数。"""
        import json
        # 读取帧偏移索引
        idx_path = store_path.rsplit(".", 1)[0] + ".idx"
        if os.path.exists(idx_path):
            with open(idx_path) as f:
                offsets = json.load(f)
        else:
            offsets = []
            for i in range(frame_count):
                offsets.append([0, 0])  # fallback

        # 保持文件句柄打开 + LRU 缓存（与 CompressedFrameStore 一致）
        import cv2
        import numpy as np
        from collections import OrderedDict
        import threading
        fh = open(store_path, "rb")
        cache: OrderedDict[int, np.ndarray] = OrderedDict()
        cache_nbytes = 0
        cache_lock = threading.Lock()
        read_lock = threading.Lock()
        inflight: dict[int, threading.Event] = {}

        def loader(_i):
            nonlocal cache_nbytes
            while True:
                with cache_lock:
                    cached = cache.pop(_i, None)
                    if cached is not None:
                        cache[_i] = cached
                        return cached
                    ready = inflight.get(_i)
                    if ready is None:
                        ready = threading.Event()
                        inflight[_i] = ready
                        break
                ready.wait()

            try:
                off, length = offsets[_i]
                with read_lock:
                    fh.seek(off)
                    payload = fh.read(length)
                if not payload:
                    raise RuntimeError(
                        f"帧 {_i}: 偏移 {off} 处读取到空数据")
                arr = np.frombuffer(payload, dtype=np.uint8)
                frame_bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                if frame_bgr is None:
                    raise RuntimeError(
                        f"帧 {_i}: JPEG 解码失败 "
                        f"(offset={off}, len={length})")
                rgb = np.ascontiguousarray(frame_bgr[:, :, ::-1])
            except Exception:
                with cache_lock:
                    inflight.pop(_i).set()
                raise

            with cache_lock:
                cache[_i] = rgb
                cache_nbytes += rgb.nbytes
                while cache_nbytes > cache_max_bytes and len(cache) > 1:
                    _, evicted = cache.popitem(last=False)
                    cache_nbytes -= evicted.nbytes
                inflight.pop(_i).set()
            return rgb

        actual_count = max(frame_count, len(offsets))
        frames: list = []
        frame_interval = (
            duration / actual_count if duration > 0 and actual_count > 0
            else 1.0 / fps if fps > 0 else 1.0 / 30
        )
        for i in range(actual_count):
            timestamp = i * frame_interval
            from core.screen_capture import CapturedFrame
            frames.append(CapturedFrame(
                data=None, timestamp=timestamp, index=i,
                _loader=loader,
            ))
        if frames:
            self.fps = fps
            self.load_frames(frames)
            self._frames_data_handle = fh
        else:
            fh.close()
        return len(frames)

    def _close_frames_data(self):
        if self._frames_data_handle is not None:
            self._frames_data_handle.close()
            self._frames_data_handle = None

    def close(self):
        self._close_frames_data()

    @property
    def source_duration(self) -> float:
        if not self._frame_times:
            return 0.0
        if len(self._frame_times) == 1:
            return 1 / self.fps
        intervals = [
            end - start
            for start, end in zip(self._frame_times, self._frame_times[1:])
            if end > start
        ]
        tail = float(np.median(intervals)) if intervals else 1 / self.fps
        return self._frame_times[-1] + tail

    def load_cursor_events(self, events: list, clicks: list):
        self._cursor_events = events or []
        self._click_events = []
        for e in clicks or []:
            self._click_events.append((e.x, e.y, e.timestamp - self._base_time))

    def set_monitor_offset(self, left: int, top: int):
        """设置显示器在屏幕坐标系中的偏移量"""
        self._monitor_left = left
        self._monitor_top = top

    def set_cursor(self, x: int, y: int, state: str = "idle"):
        self._cursor_x = max(0, min(x, self.width))
        self._cursor_y = max(0, min(y, self.height))
        self._cursor_state = state

    def add_click(self, x: int, y: int, ts: float):
        self._click_events.append((x, y, ts))

    def set_zoom(self, rect: tuple | None):
        self._zoom_rect = rect

    def load_camera(self, camera):
        self._camera = camera

    def load_manual_zoom_clips(self, clips: list):
        self._manual_zoom_clips = sorted(clips or [], key=lambda c: c.start)

    def load_clips(self, clips: list):
        """加载时间线 video clip 列表（用于速度感知渲染）"""
        self._clips = sorted(clips or [], key=lambda c: c.start)

    def set_crop(self, crop):
        from core.project import CropRegion
        self._crop_region = crop

    def register_effect(self, name: str, effect: Effect):
        self._effects[name] = effect

    def unregister_effect(self, name: str):
        self._effects.pop(name, None)

    # ── 合成 ──────────────────────────────────────────────

    def _interpolate_cursor(self, ts: float) -> tuple[int, int]:
        """根据帧时间戳插值出当前帧的鼠标位置（减去显示器偏移得到帧内坐标）"""
        if not self._cursor_events:
            return self._cursor_x, self._cursor_y
        events = self._cursor_events
        target = self._base_time + ts
        if target <= events[0].timestamp:
            x, y = events[0].x, events[0].y
        elif target >= events[-1].timestamp:
            x, y = events[-1].x, events[-1].y
        else:
            # 二分查找目标时间戳
            lo, hi = 0, len(events) - 1
            while lo < hi:
                mid = (lo + hi) // 2
                if events[mid].timestamp < target:
                    lo = mid + 1
                else:
                    hi = mid
            i = lo
            e0, e1 = events[i - 1], events[i]
            if e1.timestamp == e0.timestamp:
                x, y = e1.x, e1.y
            else:
                t = (target - e0.timestamp) / (e1.timestamp - e0.timestamp)
                x = int(e0.x + (e1.x - e0.x) * t)
                y = int(e0.y + (e1.y - e0.y) * t)
        return x - self._monitor_left, y - self._monitor_top

    def _interpolate_cursor_raw(self, rel_ts: float) -> tuple[int, int]:
        """按相对时间插值光标位置（用于 keyframe 生成）"""
        target = self._base_time + rel_ts
        events = self._cursor_events
        if not events:
            return self._cursor_x, self._cursor_y
        if target <= events[0].timestamp:
            x, y = events[0].x, events[0].y
        elif target >= events[-1].timestamp:
            x, y = events[-1].x, events[-1].y
        else:
            for i in range(1, len(events)):
                if events[i].timestamp >= target:
                    e0, e1 = events[i - 1], events[i]
                    if e1.timestamp == e0.timestamp:
                        x, y = e1.x, e1.y
                    else:
                        t = (target - e0.timestamp) / (e1.timestamp - e0.timestamp)
                        x = int(e0.x + (e1.x - e0.x) * t)
                        y = int(e0.y + (e1.y - e0.y) * t)
                    break
            else:
                x, y = events[-1].x, events[-1].y
        return x - self._monitor_left, y - self._monitor_top

    def _get_zoom_at(self, ts: float,
                     source_ts: float | None = None) -> tuple | None:
        if self._manual_zoom_clips is not None:
            if not self._manual_zoom_clips:
                return None
            starts = [c.start for c in self._manual_zoom_clips]
            i = bisect.bisect_right(starts, ts) - 1
            if i >= 0:
                c = self._manual_zoom_clips[i]
                if ts <= c.end and c.rect:
                    target = tuple(c.rect)
                    duration = max(0.0, c.end - c.start)
                    transition = min(
                        max(0.0, getattr(c, "transition_duration", 0.4)),
                        duration / 2,
                    )
                    if transition <= 0:
                        return target

                    full = (0, 0, self.width, self.height)
                    previous = full
                    if i > 0:
                        prev_clip = self._manual_zoom_clips[i - 1]
                        if (prev_clip.rect
                                and c.start - prev_clip.end <= 0.001):
                            previous = tuple(prev_clip.rect)

                    elapsed = ts - c.start
                    if elapsed < transition:
                        return self._interpolate_rect(
                            previous, target, elapsed / transition)

                    remaining = c.end - ts
                    if remaining < transition:
                        if i + 1 < len(self._manual_zoom_clips):
                            next_clip = self._manual_zoom_clips[i + 1]
                            if (next_clip.rect
                                    and next_clip.start - c.end <= 0.001):
                                # 相邻 Clip 的平移由下一个 Clip 入场过渡完成，
                                # 避免当前 Clip 先移动一次导致边界跳变。
                                return target
                        return self._interpolate_rect(
                            target, full,
                            1.0 - remaining / transition,
                        )
                    return target
            return None
        if not self._camera:
            return None
        w, h = self.width, self.height
        camera_ts = ts if source_ts is None else source_ts
        fx, fy, scale = self._camera.sample(camera_ts * 1000)
        zw = int(w / scale)
        zh = int(h / scale)
        zx = int(fx * w - zw / 2)
        zy = int(fy * h - zh / 2)
        zx = max(0, min(zx, w - zw))
        zy = max(0, min(zy, h - zh))
        return (zx, zy, zw, zh)

    @staticmethod
    def _interpolate_rect(start: tuple, end: tuple,
                          progress: float) -> tuple[int, int, int, int]:
        progress = max(0.0, min(1.0, progress))
        eased = 10 * progress ** 3 - 15 * progress ** 4 + 6 * progress ** 5
        return tuple(round(a + (b - a) * eased)
                     for a, b in zip(start, end))

    @staticmethod
    def _transform_point(x: int, y: int, width: int, height: int,
                         zoom: tuple | None = None,
                         crop_rect: tuple | None = None) -> tuple[int, int]:
        if zoom:
            zx, zy, zw, zh = zoom
            x = int((x - zx) * width / max(zw, 1))
            y = int((y - zy) * height / max(zh, 1))
        if crop_rect:
            crop_x, crop_y, crop_w, crop_h = crop_rect
            x = int((x - crop_x) * width / max(crop_w, 1))
            y = int((y - crop_y) * height / max(crop_h, 1))
        return x, y

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
            # 帧解码失败时用黑帧兜底，避免导出/回放过程中闪退
            import sys
            print(f"[compositor] 帧 {frame.index} 解码失败，使用黑帧兜底",
                  file=sys.stderr, flush=True)
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
                from core.project import CropRegion
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

    @property
    def total_output_frames(self) -> int:
        return self.total_output_frames_for(self.fps)

    def total_output_frames_for(self, render_fps: float) -> int:
        if render_fps <= 0:
            return 0
        if self._clips:
            duration = max(c.end for c in self._clips)
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
