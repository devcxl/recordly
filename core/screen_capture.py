"""屏幕录制引擎 — 基于 mss"""

import mss
import numpy as np
import cv2
import os
import tempfile
import atexit
from collections import OrderedDict
from threading import Thread, Event, Lock
import time
from typing import Callable


class CapturedFrame:
    def __init__(self, data: np.ndarray | None, timestamp: float, index: int,
                 _loader: Callable[[int], np.ndarray] | None = None):
        self._data = data
        self.timestamp = timestamp
        self.index = index
        self._loader = _loader

    @property
    def data(self) -> np.ndarray:
        if self._data is not None:
            return self._data
        if self._loader is None:
            raise RuntimeError("录制帧没有可用数据")
        return self._loader(self.index)


class _CompressedFrameStore:
    """单文件 JPEG 帧仓库，按需解码并缓存最近访问的帧。"""

    def __init__(self, jpeg_quality: int = 95, cache_size: int = 12,
                 store_path: str | None = None):
        if store_path:
            self.path = store_path
            os.makedirs(os.path.dirname(store_path), exist_ok=True)
            if os.path.exists(store_path):
                self._file = open(store_path, "r+b")
            else:
                self._file = open(store_path, "w+b")
        else:
            handle = tempfile.NamedTemporaryFile(
                prefix="recordly-", suffix=".frames", delete=False)
            self.path = handle.name
            self._file = handle
        self._quality = jpeg_quality
        self._cache_size = cache_size
        self._offsets: list[tuple[int, int]] = []
        self._cache: OrderedDict[int, np.ndarray] = OrderedDict()
        self._lock = Lock()
        if store_path is None:
            # 临时文件退出时自动清理；项目文件不注册
            atexit.register(self.cleanup)

    @property
    def frame_count(self) -> int:
        return len(self._offsets)

    def append(self, rgb: np.ndarray) -> int:
        result = cv2.imencode(
            ".jpg", np.ascontiguousarray(rgb[:, :, ::-1]),
            [cv2.IMWRITE_JPEG_QUALITY, self._quality],
        )
        if not result:
            raise RuntimeError("录制帧压缩失败")
        success, encoded = result
        if not success:
            raise RuntimeError("录制帧压缩失败")
        payload = encoded.tobytes()
        with self._lock:
            offset = self._file.tell()
            self._file.write(payload)
            self._offsets.append((offset, len(payload)))
            return len(self._offsets) - 1

    def read(self, index: int) -> np.ndarray:
        with self._lock:
            cached = self._cache.pop(index, None)
            if cached is not None:
                self._cache[index] = cached
                return cached
            offset, length = self._offsets[index]
            self._file.flush()
            self._file.seek(offset)
            payload = self._file.read(length)
        bgr = cv2.imdecode(np.frombuffer(payload, dtype=np.uint8), cv2.IMREAD_COLOR)
        if bgr is None:
            raise RuntimeError(f"无法解码录制帧 {index}")
        rgb = np.ascontiguousarray(bgr[:, :, ::-1])
        with self._lock:
            self._cache[index] = rgb
            while len(self._cache) > self._cache_size:
                self._cache.popitem(last=False)
        return rgb

    def cleanup(self):
        with self._lock:
            handle = self._file
            self._file = None
            self._cache.clear()
        if handle is not None:
            try:
                handle.close()
            except Exception:
                pass
        try:
            os.remove(self.path)
        except OSError:
            pass


class ScreenCapture(Thread):
    """基于 mss 的跨平台屏幕录制"""

    def __init__(self, monitor_id: int = 1, target_fps: int = 30,
                 store_path: str | None = None):
        super().__init__(daemon=True)
        self.monitor_id = monitor_id
        self.interval = 1.0 / target_fps
        self._quit = Event()
        self._store_path = store_path
        self._store: _CompressedFrameStore | None = None
        self._timestamps: list[float] = []
        self._indices: list[int] = []
        self._latest_frame: CapturedFrame | None = None
        self._frame_index = 0
        self._monitor_left = 0
        self._monitor_top = 0
        self._error: BaseException | None = None

    @property
    def monitor_offset(self) -> tuple[int, int]:
        """显示器在屏幕坐标系中的偏移 (left, top)"""
        return (self._monitor_left, self._monitor_top)

    @property
    def error(self) -> BaseException | None:
        """返回后台采集异常，由录制控制器在主线程处理。"""
        return self._error

    def run(self):
        try:
            with mss.mss() as sct:
                monitor = sct.monitors[self.monitor_id]
                self._monitor_left = monitor["left"]
                self._monitor_top = monitor["top"]
                while not self._quit.is_set():
                    t0 = time.perf_counter()
                    raw = sct.grab(monitor)
                    # mss 返回 BGRA, 转 RGB
                    arr = np.array(raw, dtype=np.uint8)
                    rgb = arr[:, :, :3][:, :, ::-1]
                    self._store_frame(rgb, t0, self._frame_index)
                    self._frame_index += 1
                    elapsed = time.perf_counter() - t0
                    sleep_time = self.interval - elapsed
                    if sleep_time > 0:
                        time.sleep(sleep_time)
        except BaseException as exc:
            self._error = exc
            self._quit.set()

    def stop(self):
        self._quit.set()
        if self.ident is not None:
            self.join(timeout=5)

    @property
    def latest_frame(self) -> CapturedFrame | None:
        return self._latest_frame

    @property
    def frame_meta(self) -> tuple[list[float], list[int]]:
        """返回 (timestamps, indices) 用于保存帧元数据"""
        return (self._timestamps.copy(), self._indices.copy())

    @property
    def all_frames(self) -> list[CapturedFrame]:
        if self._store is None:
            return []
        return [
            CapturedFrame(
                data=None, timestamp=timestamp, index=index,
                _loader=self._store.read,
            )
            for timestamp, index in zip(self._timestamps, self._indices)
        ]

    def _store_frame(self, data: np.ndarray,
                     timestamp: float, index: int):
        if self._store is None:
            self._store = _CompressedFrameStore(store_path=self._store_path)
        self._store.append(data)
        self._timestamps.append(timestamp)
        self._indices.append(index)
        self._latest_frame = CapturedFrame(data, timestamp, index)

    def clear(self):
        if self._store is not None:
            self._store.cleanup()
        self._store = None
        self._timestamps.clear()
        self._indices.clear()
        self._latest_frame = None
        self._frame_index = 0
        self._error = None
        self._quit.clear()
