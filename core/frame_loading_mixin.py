"""帧输入加载 — Compositor 的方法扩展。"""

import json
import os

import numpy as np

from core.screen_capture import CapturedFrame


class FrameLoadingMixin:
    """从帧列表、视频文件或 CompressedFrameStore 加载帧。"""

    # ── 输入 ──────────────────────────────────────────────

    def load_frames(self, frames: list[CapturedFrame]):
        self._close_frames_data()
        self._frames = list(frames)
        self.clear_preview_cache()
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
            # cv2 解码为 BGR，转 RGB 与 compositor 其余路径（mss BGRA→RGB）
            # 及 Image.fromarray(mode="RGB") 的色彩空间约定保持一致
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            frames.append(CapturedFrame(
                data=frame_rgb, timestamp=timestamp, index=index,
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
